"""Now-playing sources: ask a radio station's own web API which song is on air.

Some stations do not publish the song inside the audio stream (ICY metadata) and only
expose it through an HTTP JSON endpoint used by their website. A source polls that
endpoint in a background thread and reports "Artist - Song" whenever it changes.

Stations are described in nowplaying.json (see the README).
"""
import json
import random
import sys
import threading
import urllib.request
from http.client import HTTPException
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from PySide6.QtCore import QObject, Signal

AGENT = "vlc-ui"
SEPARATOR = " \u2014 "
MAX_COVER_BYTES = 5 * 1024 * 1024
FIELD_NAMES = ("artist", "song", "album", "year", "cover")


def load_sources(path):
    """Reads the station list; a missing or broken file just means no sources."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        print(f"vlc-ui: could not read {path}: {exc}", file=sys.stderr)
        return []
    return [s for s in data.get("sources", []) if s.get("match") and s.get("url")]


def find_source(stream_url, sources):
    """Returns the first source whose "match" text appears in the stream URL."""
    for source in sources:
        if source["match"] in stream_url:
            return source
    return None


def dig(data, path):
    """Follows a dotted path ("data.artist", "items.0.title") through JSON data."""
    if not path:
        return None
    for key in path.split("."):
        if isinstance(data, dict):
            data = data.get(key)
        elif isinstance(data, list) and key.isdigit() and int(key) < len(data):
            data = data[int(key)]
        else:
            return None
    return data


def with_cache_buster(url, param):
    """Gives the query parameter a fresh random value, so no cache serves an old answer."""
    parts = urlsplit(url)
    query = [(k, str(random.randint(1000000, 9999999)) if k == param else v)
             for k, v in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit(parts._replace(query=urlencode(query)))


def fetch_json(url, timeout=8):
    request = urllib.request.Request(url, headers={
        "User-Agent": AGENT,
        "Accept": "application/json",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_cover(url, timeout=8):
    """Downloads a cover image; returns its bytes, or None if it is not available."""
    if urlsplit(url).scheme not in ("http", "https"):
        return None
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read(MAX_COVER_BYTES + 1)
    except (OSError, ValueError, HTTPException):
        return None
    return data if 0 < len(data) <= MAX_COVER_BYTES else None


def read_song(config):
    """Returns what the station's endpoint says is playing, or None if it is not available.

    The result is a dict with "text" ("Artist - Song") and the configured fields
    ("artist", "song", "album", "year", "cover"; "" when missing).

    With "cache_bust_param" the request uses a fresh random value for that parameter;
    if that fails, the URL exactly as configured is tried as well.
    """
    urls = []
    param = config.get("cache_bust_param")
    if param:
        urls.append(with_cache_buster(config["url"], param))
    urls.append(config["url"])
    for url in urls:
        try:
            data = fetch_json(url)
        except (OSError, ValueError, HTTPException):
            continue
        ok = config.get("ok")
        if ok and dig(data, ok.get("path")) != ok.get("equals"):
            continue
        fields = config.get("fields", {})
        info = {name: str(dig(data, fields.get(name)) or "").strip() for name in FIELD_NAMES}
        info["text"] = SEPARATOR.join(p for p in (info["artist"], info["song"]) if p)
        if info["text"]:
            return info
    return None


EMPTY_INFO = {name: "" for name in FIELD_NAMES + ("text",)}


class NowPlayingSource(QObject):
    """Polls one station's endpoint in a background thread."""

    updated = Signal(dict)       # read_song() result when the song changes; EMPTY_INFO when the station stops answering
    cover_loaded = Signal(dict)  # {"url": ..., "data": image bytes or None}, once per song change

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.interval = max(5, config.get("interval_seconds", 10))
        self._stop = threading.Event()

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stop.set()

    def _run(self):
        last = None
        failures = 0
        cover_url = None
        cover_data = None
        try:
            while not self._stop.is_set():
                info = read_song(self.config)
                if info is None:
                    failures += 1
                    # A few failures in a row: stop showing a song that may be outdated
                    info = EMPTY_INFO if failures >= 3 else None
                else:
                    failures = 0
                if info is not None and info["text"] != last and not self._stop.is_set():
                    last = info["text"]
                    self.updated.emit(info)
                    if info["text"]:
                        url = info["cover"]
                        if url != cover_url:  # same album as the last song: reuse the image
                            cover_data = fetch_cover(url) if url else None
                            cover_url = url if cover_data else None
                        if not self._stop.is_set():
                            self.cover_loaded.emit({"url": url, "data": cover_data})
                self._stop.wait(self.interval)
        except RuntimeError:
            return  # the Qt object is gone (the app is exiting)
