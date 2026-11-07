"""MPRIS: lets the desktop see and control the player over D-Bus.

Status bars and shells (waybar, quickshell and others), `playerctl`, lock screens and the
keyboard media keys all talk to media players through the MPRIS interface. This module
publishes the player on the session bus as `org.mpris.MediaPlayer2.vlc_ui`.

The service runs in a background thread with its own asyncio loop (dbus-fast). It never
touches the player: the interface sends commands to the Qt thread through the `command`
signal, and the Window pushes the current state with `update()`.

dbus-fast is optional. Without it, or without a session bus, the player just runs
without MPRIS.
"""
import asyncio
import hashlib
import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal

try:
    from dbus_fast import NameFlag, RequestNameReply, Variant
    from dbus_fast.aio import MessageBus
    from dbus_fast.service import PropertyAccess, ServiceInterface, dbus_property, method, signal
except ImportError:  # pragma: no cover - depends on the environment
    MessageBus = None

BUS_NAME = "org.mpris.MediaPlayer2.vlc_ui"
OBJECT_PATH = "/org/mpris/MediaPlayer2"
NO_TRACK = "/org/mpris/MediaPlayer2/TrackList/NoTrack"

EMPTY_STATE = {
    "status": "Stopped",    # Playing, Paused or Stopped
    "has_media": False,
    "title": "",
    "artist": "",
    "album": "",
    "art_url": "",          # file:// URL of the cover
    "uri": "",              # what is being played (file:// or http://)
    "length_us": 0,
    "position_us": 0,
    "volume": 1.0,          # 1.0 is 100%
    "can_seek": False,
    "track": 0,             # changes whenever the track changes
}


def cache_dir():
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "vlc-ui"


def cache_cover(data, key):
    """Saves a cover image for the desktop to load; returns its file:// URL (or "" on failure).

    Only the current cover is kept: older ones in the cache folder are removed.
    """
    try:
        folder = cache_dir()
        folder.mkdir(parents=True, exist_ok=True)
        extension = ".png" if data[:4] == b"\x89PNG" else ".jpg"
        path = folder / ("cover-" + hashlib.sha1(key.encode()).hexdigest()[:12] + extension)
        path.write_bytes(data)
        for old in folder.glob("cover-*"):
            if old != path:
                old.unlink(missing_ok=True)
        return path.as_uri()
    except OSError:
        return ""


def build_metadata(state):
    """The MPRIS Metadata dictionary for a state."""
    if not state["has_media"]:
        return {"mpris:trackid": Variant("o", NO_TRACK)}
    metadata = {
        "mpris:trackid": Variant("o", f"/org/vlc_ui/track/{state['track']}"),
        "xesam:title": Variant("s", state["title"]),
    }
    if state["artist"]:
        metadata["xesam:artist"] = Variant("as", [state["artist"]])
    if state["album"]:
        metadata["xesam:album"] = Variant("s", state["album"])
    if state["art_url"]:
        metadata["mpris:artUrl"] = Variant("s", state["art_url"])
    if state["uri"]:
        metadata["xesam:url"] = Variant("s", state["uri"])
    if state["length_us"] > 0:
        metadata["mpris:length"] = Variant("x", int(state["length_us"]))
    return metadata


def watched(state):
    """The part of a state that is announced with PropertiesChanged (not the position)."""
    return {
        "PlaybackStatus": state["status"],
        "Metadata": (state["has_media"], state["track"], state["title"], state["artist"], state["album"],
                     state["art_url"], state["uri"], state["length_us"]),
        "Volume": round(state["volume"], 2),
        "CanSeek": state["can_seek"],
        "CanPlay": state["has_media"],
        "CanPause": state["has_media"],
    }


if MessageBus is not None:

    class RootInterface(ServiceInterface):
        def __init__(self, service):
            super().__init__("org.mpris.MediaPlayer2")
            self._service = service

        @method()
        def Raise(self):
            self._service.command.emit("Raise", None)

        @method()
        def Quit(self):
            self._service.command.emit("Quit", None)

        @dbus_property(access=PropertyAccess.READ)
        def CanQuit(self) -> "b":
            return True

        @dbus_property(access=PropertyAccess.READ)
        def CanRaise(self) -> "b":
            return True

        @dbus_property(access=PropertyAccess.READ)
        def HasTrackList(self) -> "b":
            return False

        @dbus_property(access=PropertyAccess.READ)
        def Identity(self) -> "s":
            return "VLC UI"

        @dbus_property(access=PropertyAccess.READ)
        def DesktopEntry(self) -> "s":
            return "vlc-ui"

        @dbus_property(access=PropertyAccess.READ)
        def SupportedUriSchemes(self) -> "as":
            return ["file", "http", "https"]

        @dbus_property(access=PropertyAccess.READ)
        def SupportedMimeTypes(self) -> "as":
            return ["audio/mpeg", "audio/aac", "audio/ogg", "audio/flac", "video/mp4", "video/x-matroska"]

    class PlayerInterface(ServiceInterface):
        def __init__(self, service):
            super().__init__("org.mpris.MediaPlayer2.Player")
            self._service = service

        def _send(self, name, argument=None):
            self._service.command.emit(name, argument)

        @method()
        def Next(self):
            pass  # no playlist yet

        @method()
        def Previous(self):
            pass

        @method()
        def Pause(self):
            self._send("Pause")

        @method()
        def PlayPause(self):
            self._send("PlayPause")

        @method()
        def Stop(self):
            self._send("Stop")

        @method()
        def Play(self):
            self._send("Play")

        @method()
        def Seek(self, offset: "x"):
            self._send("Seek", offset)

        @method()
        def SetPosition(self, track_id: "o", position: "x"):
            self._send("SetPosition", position)

        @method()
        def OpenUri(self, uri: "s"):
            self._send("OpenUri", uri)

        @dbus_property(access=PropertyAccess.READ)
        def PlaybackStatus(self) -> "s":
            return self._service.state["status"]

        @dbus_property(access=PropertyAccess.READ)
        def Metadata(self) -> "a{sv}":
            return build_metadata(self._service.state)

        @dbus_property()
        def Volume(self) -> "d":
            return float(self._service.state["volume"])

        @Volume.setter
        def Volume(self, value: "d"):
            self._service.command.emit("SetVolume", float(value))

        @dbus_property(access=PropertyAccess.READ)
        def Position(self) -> "x":
            return int(self._service.state["position_us"])

        @dbus_property(access=PropertyAccess.READ)
        def Rate(self) -> "d":
            return 1.0

        @dbus_property(access=PropertyAccess.READ)
        def MinimumRate(self) -> "d":
            return 1.0

        @dbus_property(access=PropertyAccess.READ)
        def MaximumRate(self) -> "d":
            return 1.0

        @dbus_property(access=PropertyAccess.READ)
        def CanGoNext(self) -> "b":
            return False

        @dbus_property(access=PropertyAccess.READ)
        def CanGoPrevious(self) -> "b":
            return False

        @dbus_property(access=PropertyAccess.READ)
        def CanPlay(self) -> "b":
            return bool(self._service.state["has_media"])

        @dbus_property(access=PropertyAccess.READ)
        def CanPause(self) -> "b":
            return bool(self._service.state["has_media"])

        @dbus_property(access=PropertyAccess.READ)
        def CanSeek(self) -> "b":
            return bool(self._service.state["can_seek"])

        @dbus_property(access=PropertyAccess.READ)
        def CanControl(self) -> "b":
            return True


class MprisService(QObject):
    """Publishes the player on the session bus from a background thread."""

    # What the desktop asked for: "Play", "Pause", "PlayPause", "Stop", "Raise", "Quit",
    # "Seek" (offset in microseconds), "SetPosition" (microseconds), "SetVolume" (0..1),
    # "OpenUri" (text). The argument is None for the ones that take none.
    command = Signal(str, object)

    def __init__(self):
        super().__init__()
        self.state = dict(EMPTY_STATE)
        self.bus_name = ""
        self._loop = None
        self._stop = None
        self._player = None
        self._pending = None

    @property
    def available(self):
        return MessageBus is not None

    def start(self):
        if not sys.platform.startswith("linux"):
            return  # MPRIS is a Linux (D-Bus) interface
        if MessageBus is None:
            print("vlc-ui: dbus-fast is not installed, MPRIS is off (pip install dbus-fast)", file=sys.stderr)
            return
        threading.Thread(target=lambda: asyncio.run(self._main()), daemon=True).start()

    def stop(self):
        if self._loop is not None and self._stop is not None:
            try:
                self._loop.call_soon_threadsafe(self._stop.set)
            except RuntimeError:
                pass  # the loop is already closed

    def update(self, state):
        """Called from the Qt thread with the current state (see EMPTY_STATE)."""
        # The position is read on demand by clients, so it is set without any announcement
        self.state["position_us"] = state["position_us"]
        loop = self._loop
        if loop is None:
            self._pending = dict(state)
            return
        try:
            loop.call_soon_threadsafe(self._apply, dict(state))
        except RuntimeError:
            pass

    async def _main(self):
        self._loop = asyncio.get_running_loop()
        self._stop = asyncio.Event()
        try:
            bus = await MessageBus().connect()
        except Exception as exc:  # no session bus, or it is not reachable
            print(f"vlc-ui: MPRIS is off, could not reach the session bus: {exc}", file=sys.stderr)
            self._loop = None
            return
        self._player = PlayerInterface(self)
        bus.export(OBJECT_PATH, RootInterface(self))
        bus.export(OBJECT_PATH, self._player)
        reply = await bus.request_name(BUS_NAME, NameFlag.DO_NOT_QUEUE)
        self.bus_name = BUS_NAME
        if reply != RequestNameReply.PRIMARY_OWNER:
            # Another vlc-ui already owns the name: use the "instance" form the MPRIS spec describes
            self.bus_name = f"{BUS_NAME}.instance{os.getpid()}"
            await bus.request_name(self.bus_name)
        if self._pending is not None:
            self._apply(self._pending)
            self._pending = None
        await self._stop.wait()
        bus.disconnect()

    def _apply(self, new):
        old = self.state
        self.state = new
        if self._player is None:
            return
        before, after = watched(old), watched(new)
        changed = {name: value for name, value in after.items() if before[name] != value}
        if "Metadata" in changed:
            changed["Metadata"] = build_metadata(new)
        if changed:
            self._player.emit_properties_changed(changed)
