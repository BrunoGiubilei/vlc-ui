import os
import sys
from pathlib import Path

import vlc
from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, QUrl, Qt, QRectF
from PySide6.QtGui import QIcon, QKeySequence, QPainterPath, QRegion, QShortcut
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QFrame,
                               QFileDialog, QInputDialog, QLineEdit, QMenu,
                               QMessageBox, QSystemTrayIcon)

from nowplaying import NowPlayingSource, find_source, load_sources
from mpris import EMPTY_STATE, MprisService, cache_cover
from nowplaying_panel import NowPlayingPanel
from theme import load_theme

HERE = Path(__file__).parent
# Colors, font and sizes come from Theme.qml, so Python and QML always agree
THEME = load_theme(HERE / "Theme.qml")

STREAM_SCHEMES = {"http", "https", "rtsp", "rtmp", "mms", "mmsh", "udp", "rtp", "ftp"}


def normalize_stream_url(text):
    """Returns a playable stream URL, or None if the text is not a valid one.

    Text without a scheme is treated as http, for example "radio.example.com/live".
    """
    text = text.strip()
    if not text or any(c.isspace() for c in text):
        return None
    if "://" not in text:
        text = "http://" + text
    url = QUrl(text)
    if not url.isValid() or url.scheme().lower() not in STREAM_SCHEMES or not url.host():
        return None
    return text


class PlayerController(QObject):
    tick = Signal()

    def __init__(self, mp):
        super().__init__()
        self.mp = mp
        self._stream = False
        self._media = None
        self._now_text = ""
        t = QTimer(self)
        t.timeout.connect(self.tick)
        t.start(200)

    def set_stream(self, stream, media=None):
        # True for a network stream, False for a local file. The media is kept so the
        # stream metadata can be read without asking libVLC for it on every tick.
        self._stream = stream
        self._media = media
        self._now_text = ""

    def set_now_playing(self, text):
        # Song reported by a station's own API (see nowplaying.py); it wins over ICY metadata
        self._now_text = text

    @Property(float, notify=tick)
    def position(self):
        return max(0.0, self.mp.get_position())

    @Property(int, notify=tick)
    def timeMs(self):
        return max(0, self.mp.get_time())

    @Property(int, notify=tick)
    def lengthMs(self):
        return max(0, self.mp.get_length())

    @Property(bool, notify=tick)
    def playing(self):
        return bool(self.mp.is_playing())

    @Property(int, notify=tick)
    def volume(self):
        return max(0, self.mp.audio_get_volume())

    @Property(bool, notify=tick)
    def live(self):
        # A stream is live once it plays but has no known length or cannot seek
        if not self._stream:
            return False
        if self.mp.get_state() not in (vlc.State.Playing, vlc.State.Paused):
            return False
        return self.mp.get_length() <= 0 or not self.mp.is_seekable()

    @Property(str, notify=tick)
    def statusText(self):
        # Connection status of a stream; empty for local files and while playing normally
        if not self._stream:
            return ""
        state = self.mp.get_state()
        if state == vlc.State.Opening:
            return "Connecting..."
        if state == vlc.State.Buffering:
            return "Buffering..."
        if state == vlc.State.Error:
            return "Could not play this stream"
        if state == vlc.State.Ended:
            return "Stream ended"
        return ""

    @Property(str, notify=tick)
    def title(self):
        # Station name and now-playing text of a stream (ICY metadata), when available
        if not self._stream:
            return ""
        if self._now_text:
            return self._now_text
        media = self._media
        if media is None:
            return ""
        station = media.get_meta(vlc.Meta.Title) or ""
        now = media.get_meta(vlc.Meta.NowPlaying) or ""
        if station and now and station != now:
            return f"{station} \u2014 {now}"
        return now or station

    @Slot()
    def togglePlay(self):
        self.mp.pause()

    @Slot(float)
    def seek(self, pos):
        self.mp.set_position(pos)

    @Slot(int)
    def setVolume(self, v):
        self.mp.audio_set_volume(v)


class WindowController(QObject):
    folderChanged = Signal()

    def __init__(self, window):
        super().__init__()
        self.window = window
        self._folder = ""

    @Property(str, notify=folderChanged)
    def folder(self):
        return self._folder

    def set_folder(self, name):
        self._folder = name
        self.folderChanged.emit()

    @Slot()
    def startMove(self):
        handle = self.window.windowHandle()
        if handle:
            handle.startSystemMove()

    @Slot()
    def minimize(self):
        self.window.showMinimized()

    @Slot()
    def toggleMaximize(self):
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()

    @Slot()
    def toggleFullscreen(self):
        if self.window.isFullScreen():
            self.window.showNormal()
        else:
            self.window.showFullScreen()

    @Slot()
    def closeWindow(self):
        self.window.close()

    @Slot()
    def openMedia(self):
        self.window.open_media()

    @Slot()
    def openUrl(self):
        self.window.open_url_dialog()


class RoundedFrame(QFrame):
    def __init__(self, radius=8):
        super().__init__()
        self.radius = radius

    def resizeEvent(self, e):
        super().resizeEvent(e)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self.radius, self.radius)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))


class TrayIcon(QSystemTrayIcon):
    """System tray icon: lets the player keep running with its window hidden."""

    def __init__(self, window, icon_path):
        super().__init__(QIcon(str(icon_path)), window)
        self.window = window
        self.setToolTip("VLC UI")

        menu = QMenu(window)
        self.toggle_action = menu.addAction("Hide", window.toggle_visible)
        self.play_action = menu.addAction("Play", window.player_ctrl.togglePlay)
        menu.addAction("Open network stream...", self.open_url)
        menu.addSeparator()
        menu.addAction("Quit", window.quit_app)
        menu.aboutToShow.connect(self.refresh_menu)
        self.setContextMenu(menu)
        self.activated.connect(self.on_activated)

    def refresh_menu(self):
        # The labels follow the current state each time the menu opens
        self.toggle_action.setText("Hide" if self.window.isVisible() else "Show")
        self.play_action.setText("Pause" if self.window.player_ctrl.playing else "Play")
        self.play_action.setEnabled(self.window.mp.get_media() is not None)

    def open_url(self):
        self.window.show_window()
        self.window.open_url_dialog()

    def on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.window.toggle_visible()
        elif reason == QSystemTrayIcon.MiddleClick:
            self.window.player_ctrl.togglePlay()


def make_quick(ctx_name, ctrl, qml, height):
    w = QQuickWidget()
    w.setResizeMode(QQuickWidget.SizeRootObjectToView)
    w.engine().addImportPath(str(HERE))
    w.rootContext().setContextProperty(ctx_name, ctrl)
    w.setSource(QUrl.fromLocalFile(str(HERE / qml)))
    w.setFixedHeight(height)
    return w


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setObjectName("root")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("#root { background: %s; }" % THEME["chrome"])

        self.instance = vlc.Instance()
        self.mp = self.instance.media_player_new()

        self.video = RoundedFrame(THEME["canvasRadius"])
        self.video.setStyleSheet("background:" + THEME["canvas"])

        # Cover, song and album over the empty video area (audio streams only)
        self.panel = NowPlayingPanel(self.video, THEME)
        fl = QVBoxLayout(self.video)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.addWidget(self.panel)

        self.player_ctrl = PlayerController(self.mp)
        self.win_ctrl = WindowController(self)

        self.top = make_quick("win", self.win_ctrl, "TopBar.qml", THEME["topBarHeight"])
        self.bar = make_quick("player", self.player_ctrl, "ControlBar.qml", THEME["barHeight"])

        # Canvas area: 10px side margins and 1px gap below the top bar (from the design)
        canvas = QWidget()
        cl = QVBoxLayout(canvas)
        cl.setContentsMargins(THEME["canvasMargin"], 1, THEME["canvasMargin"], 0)
        cl.addWidget(self.video)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.top)
        lay.addWidget(canvas, 1)
        lay.addWidget(self.bar)
        self.resize(1100, 640)

        # Same shortcut as VLC's "Open Network Stream"
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.open_url_dialog)

        # Closing the window sends the player to the system tray; "Quit" in the tray menu exits
        self._quitting = False
        self.sources = load_sources(HERE / "nowplaying.json")
        self._now_source = None
        self._tray_notified = False
        self._song_info = None
        self._tray_tip = "VLC UI"
        self.tray = TrayIcon(self, HERE / "assets" / "icons" / "vlc_icon.svg")
        self.tray.show()
        self.player_ctrl.tick.connect(self.on_tick)

        # MPRIS: what is playing shows in status bars / playerctl, and media keys work
        self._media_name = ""      # name and address of what is playing, for MPRIS
        self._media_uri = ""
        self._art_url = ""         # file:// URL of the current cover, for MPRIS
        self._track = 0
        self._track_key = None
        self._mpris_key = None
        self.mpris = MprisService()
        self.mpris.command.connect(self._on_mpris_command)
        self.mpris.start()

    def closeEvent(self, e):
        # Without a system tray there is nowhere to hide, so closing really quits
        if self._quitting or not QSystemTrayIcon.isSystemTrayAvailable():
            self.quit_app()
            e.accept()
            return
        e.ignore()
        self.hide()
        if not self._tray_notified:
            self._tray_notified = True
            self.tray.showMessage(
                "VLC UI",
                "Still running in the system tray. Use Quit in the tray menu to exit.",
                QSystemTrayIcon.Information,
                4000,
            )

    def show_window(self):
        # Also restores a minimized window, keeping it maximized if it was
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
        self.show()
        self.raise_()
        self.activateWindow()

    def toggle_visible(self):
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.show_window()

    def quit_app(self):
        self._quitting = True
        self.mpris.stop()
        self._stop_now_playing()
        self.mp.stop()
        QApplication.quit()

    def open_media(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open media",
            str(Path.home()),
            "Media (*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv *.m4v *.mpg *.mpeg "
            "*.mp3 *.flac *.ogg *.opus *.wav *.m4a);;All files (*)",
        )
        if not path:
            return
        self.play_path(path)

    def play_path(self, path):
        self.win_ctrl.set_folder(Path(path).parent.name)
        self._play(self.instance.media_new(path), stream=False, name=Path(path).stem, uri=Path(path).resolve().as_uri())

    def open_url_dialog(self):
        # Pre-fill with the clipboard when it holds a URL
        clip = QApplication.clipboard().text().strip()
        default = clip if "://" in clip and normalize_stream_url(clip) else ""
        text, ok = QInputDialog.getText(
            self,
            "Open network stream",
            "Stream URL (for example an online radio):",
            QLineEdit.Normal,
            default,
        )
        if ok:
            self.open_url(text)

    def open_url(self, text):
        url = normalize_stream_url(text)
        if url is None:
            QMessageBox.warning(
                self,
                "Open network stream",
                "Enter a valid stream URL, for example https://example.com/radio.mp3",
            )
            return
        self.win_ctrl.set_folder(QUrl(url).host())
        self._play(self.instance.media_new(url), stream=True, url=url, uri=url)

    def open_argument(self, arg):
        # A URL or a file path given on the command line
        if "://" in arg:
            self.open_url(arg)
        elif Path(arg).is_file():
            self.play_path(str(Path(arg).resolve()))

    def _play(self, media, stream, url=None, name="", uri=""):
        self._stop_now_playing()
        self._media_name = name
        self._media_uri = uri
        self.player_ctrl.set_stream(stream, media)
        self.mp.set_media(media)
        # Embeds libVLC video into the native frame; needs X11 (run with QT_QPA_PLATFORM=xcb on Wayland)
        self.mp.set_xwindow(int(self.video.winId()))
        self.mp.play()
        if stream and url:
            self._start_now_playing(url)

    def _start_now_playing(self, url):
        config = find_source(url, self.sources)
        if config is None:
            return
        source = NowPlayingSource(config)
        source.updated.connect(lambda info, s=source: self._on_now_playing(s, info))
        source.cover_loaded.connect(lambda result, s=source: self._on_cover(s, result))
        self._now_source = source
        source.start()

    def _stop_now_playing(self):
        if self._now_source is not None:
            self._now_source.stop()
            self._now_source = None
        self._song_info = None
        self._art_url = ""
        self.panel.clear()

    def _on_now_playing(self, source, info):
        # Ignore late answers from a source that has been replaced
        if source is not self._now_source:
            return
        if info.get("cover") != (self._song_info or {}).get("cover"):
            self._art_url = ""  # the previous cover no longer applies
        self._song_info = info
        self.player_ctrl.set_now_playing(info["text"])
        self.panel.set_info(info)

    def _on_cover(self, source, result):
        if source is not self._now_source:
            return
        self.panel.set_cover(result["url"], result["data"])
        if result["data"] and result["url"] == (self._song_info or {}).get("cover"):
            self._art_url = cache_cover(result["data"], result["url"])
        self.notify_song()

    def notify_song(self):
        # A desktop notification for the new song, only while the window is out of sight
        info = self._song_info
        if not info or not info["text"]:
            return
        if self.isVisible() and not self.isMinimized():
            return
        if not (QSystemTrayIcon.isSystemTrayAvailable() and QSystemTrayIcon.supportsMessages()):
            return
        cover = self.panel.cover_pixmap()
        album = " \u00b7 ".join(p for p in (info["album"], info["year"]) if p)
        self.tray.showMessage(
            info["song"] or info["text"],
            "\n".join(p for p in (info["artist"], album) if p),
            QIcon(cover) if cover is not None else QSystemTrayIcon.Information,
            5000,
        )

    def on_tick(self):
        title = self.player_ctrl.title
        self.sync_tray_tooltip(title)
        self.sync_mpris(title)

    def sync_tray_tooltip(self, title):
        # The tray tooltip shows what is playing (updated only when it changes)
        tip = f"{title}\nVLC UI" if title else "VLC UI"
        if tip != self._tray_tip:
            self._tray_tip = tip
            self.tray.setToolTip(tip)

    def mpris_state(self, title):
        pc = self.player_ctrl
        state = dict(EMPTY_STATE)
        has_media = bool(self._media_name or self._media_uri)
        vlc_state = self.mp.get_state()
        if not has_media:
            status = "Stopped"
        elif vlc_state in (vlc.State.Playing, vlc.State.Opening, vlc.State.Buffering):
            status = "Playing"
        elif vlc_state == vlc.State.Paused:
            status = "Paused"
        else:
            status = "Stopped"
        info = self._song_info or {}
        stream = bool(self._media_uri) and not self._media_name
        name = info.get("song") or (title if stream else self._media_name)
        length = 0 if pc.live else pc.lengthMs * 1000
        state.update(
            status=status,
            has_media=has_media,
            title=name or self._media_uri,
            artist=info.get("artist", ""),
            album=info.get("album", ""),
            art_url=self._art_url,
            uri=self._media_uri,
            length_us=length,
            position_us=0 if pc.live else pc.timeMs * 1000,
            volume=pc.volume / 100,
            can_seek=has_media and not pc.live and length > 0,
        )
        return state

    def sync_mpris(self, title):
        state = self.mpris_state(title)
        track_key = (state["uri"], state["title"], state["artist"], state["album"])
        if track_key != self._track_key:
            self._track_key = track_key
            self._track += 1
        state["track"] = self._track
        # The position changes all the time and is read on demand, so it is not part of the comparison
        key = {k: v for k, v in state.items() if k != "position_us"}
        if key == self._mpris_key:
            self.mpris.state["position_us"] = state["position_us"]
            return
        self._mpris_key = key
        self.mpris.update(state)

    def _on_mpris_command(self, name, argument):
        # Runs in the Qt thread: what the desktop (or a media key) asked for
        mp, pc = self.mp, self.player_ctrl
        state = mp.get_state()
        has_media = bool(self._media_name or self._media_uri)
        if name == "Raise":
            self.show_window()
        elif name == "Quit":
            self.quit_app()
        elif name == "OpenUri":
            self.open_uri(argument)
        elif name == "SetVolume":
            mp.audio_set_volume(int(max(0.0, min(argument, 2.0)) * 100))
        elif not has_media:
            return
        elif name == "PlayPause":
            if state in (vlc.State.Playing, vlc.State.Opening, vlc.State.Buffering, vlc.State.Paused):
                pc.togglePlay()
            else:
                mp.play()
        elif name == "Play":
            if state == vlc.State.Paused:
                mp.set_pause(0)
            elif state not in (vlc.State.Playing, vlc.State.Opening, vlc.State.Buffering):
                mp.play()
        elif name == "Pause":
            if state in (vlc.State.Playing, vlc.State.Buffering):
                mp.set_pause(1)
        elif name == "Stop":
            mp.stop()
        elif name in ("Seek", "SetPosition") and not pc.live and pc.lengthMs > 0:
            target_ms = pc.timeMs + argument / 1000 if name == "Seek" else argument / 1000
            pc.seek(max(0.0, min(target_ms / pc.lengthMs, 1.0)))

    def open_uri(self, uri):
        # A file:// or http(s):// address, for example from `playerctl open`
        url = QUrl(uri)
        if url.isLocalFile():
            self.play_path(url.toLocalFile())
        else:
            self.open_url(uri)


# libVLC embeds the video through an X11 window id, so on Linux the app must run
# through XWayland. Set it before QApplication is created; an existing value wins.
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

app = QApplication(sys.argv)
# The window can be hidden in the tray; dialogs closing must not quit the app
app.setQuitOnLastWindowClosed(False)
w = Window()
w.show()
args = app.arguments()[1:]
if args:
    QTimer.singleShot(0, lambda: w.open_argument(args[0]))
sys.exit(app.exec())