#!/usr/bin/env python3
"""Shows what an internet radio stream publishes as "now playing".

Usage:
    python tools/icy_probe.py URL [--seconds 30] [--vlc]

1. Opens the stream asking for in-stream metadata (ICY, used by Shoutcast and Icecast),
   prints the response headers and every StreamTitle it receives.
2. Tries the usual Shoutcast/Icecast status pages of the server (no audio needed).
3. With --vlc, plays the stream muted through python-vlc and prints what libVLC reports,
   which is exactly what vlc-ui reads.

Only the Python standard library is needed (python-vlc only for --vlc).
"""
import argparse
import re
import socket
import ssl
import sys
import time
from urllib.parse import urlsplit, urljoin

AGENT = "vlc-ui-icy-probe/1.0"


def decode(raw):
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def open_stream(url, want_meta=True, redirects=5):
    """Returns (socket, status_line, headers dict with lowercase keys, final_url)."""
    for _ in range(redirects + 1):
        parts = urlsplit(url)
        port = parts.port or (443 if parts.scheme == "https" else 80)
        sock = socket.create_connection((parts.hostname, port), timeout=10)
        if parts.scheme == "https":
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=parts.hostname)
        path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        request = (f"GET {path} HTTP/1.0\r\nHost: {parts.netloc}\r\nUser-Agent: {AGENT}\r\n"
                   f"Accept: */*\r\n" + ("Icy-MetaData: 1\r\n" if want_meta else "") + "Connection: close\r\n\r\n")
        sock.sendall(request.encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = sock.recv(1)
            if not chunk:
                break
            head += chunk
        lines = decode(head).split("\r\n")
        status = lines[0]
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        code = status.split(" ")[1] if " " in status else ""
        if code in ("301", "302", "303", "307", "308") and "location" in headers:
            sock.close()
            url = urljoin(url, headers["location"])
            print(f"  redirected to {url}")
            continue
        return sock, status, headers, url
    raise RuntimeError("too many redirects")


def read_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(min(8192, n - len(data)))
        if not chunk:
            raise EOFError("stream closed")
        data += chunk
    return data


def probe_icy(url, seconds):
    print("== 1. In-stream metadata (ICY) ==")
    sock, status, headers, final_url = open_stream(url)
    print(f"  status: {status}")
    for key in ("server", "content-type", "icy-name", "icy-genre", "icy-br", "icy-url", "icy-metaint"):
        if key in headers:
            print(f"  {key}: {headers[key]}")
    metaint = int(headers.get("icy-metaint", "0") or 0)
    if not metaint:
        print("  -> this server did NOT send icy-metaint: there is no in-stream metadata.")
        sock.close()
        return final_url
    print(f"  -> metadata block every {metaint} bytes. Listening for {seconds}s...")
    end = time.time() + seconds
    last = None
    seen_block = False
    sock.settimeout(15)
    try:
        while time.time() < end:
            read_exact(sock, metaint)
            length = read_exact(sock, 1)[0] * 16
            if length == 0:
                continue  # a zero-length block means "no change since the last one"
            block = decode(read_exact(sock, length).rstrip(b"\x00"))
            seen_block = True
            match = re.search(r"StreamTitle='(.*?)';", block, re.S)
            title = match.group(1) if match else ""
            if title != last:
                print(f"  [{time.strftime('%H:%M:%S')}] StreamTitle = {title!r}")
                last = title
    except (EOFError, socket.timeout) as exc:
        print(f"  stream ended: {exc}")
    finally:
        sock.close()
    if not seen_block:
        print("  -> no metadata block arrived in this time. Try a longer --seconds: many servers only send one when the song changes.")
    elif last == "":
        print("  -> the server sends metadata blocks but the title is empty (nothing published as now playing).")
    return final_url


def probe_pages(url):
    print("\n== 2. Server status pages (no audio) ==")
    parts = urlsplit(url)
    root = f"{parts.scheme}://{parts.netloc}"
    for path in ("/currentsong?sid=1", "/7.html", "/stats?sid=1&json=1", "/status-json.xsl"):
        try:
            sock, status, headers, _ = open_stream(root + path, want_meta=False)
            sock.settimeout(8)
            body = b""
            try:
                while len(body) < 600:
                    chunk = sock.recv(600)
                    if not chunk:
                        break
                    body += chunk
            except socket.timeout:
                pass
            sock.close()
            text = decode(body).strip().replace("\n", " ")[:200]
            print(f"  {path}: {status}  {text!r}")
        except Exception as exc:
            print(f"  {path}: failed ({exc})")


def probe_vlc(url, seconds):
    print("\n== 3. What libVLC reports (what vlc-ui reads) ==")
    try:
        import vlc
    except Exception as exc:
        print(f"  python-vlc not available: {exc}")
        return
    instance = vlc.Instance("--quiet")
    player = instance.media_player_new()
    media = instance.media_new(url)
    player.set_media(media)
    player.audio_set_volume(0)
    player.play()
    end = time.time() + seconds
    last = None
    while time.time() < end:
        time.sleep(1)
        values = {
            "state": str(player.get_state()),
            "Title": media.get_meta(vlc.Meta.Title),
            "NowPlaying": media.get_meta(vlc.Meta.NowPlaying),
            "Artist": media.get_meta(vlc.Meta.Artist),
        }
        if values != last:
            print(f"  [{time.strftime('%H:%M:%S')}] {values}")
            last = values
    player.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url")
    parser.add_argument("--seconds", type=int, default=30, help="how long to listen (default 30)")
    parser.add_argument("--vlc", action="store_true", help="also check what libVLC reports")
    args = parser.parse_args()
    final_url = probe_icy(args.url, args.seconds)
    probe_pages(final_url)
    if args.vlc:
        probe_vlc(args.url, args.seconds)


if __name__ == "__main__":
    sys.exit(main())
