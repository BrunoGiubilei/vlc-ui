import os
import sys
from pathlib import Path

import vlc
from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, QUrl, Qt, QRectF
from PySide6.QtGui import QPainterPath, QRegion
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout,
                               QFrame, QFileDialog)

HERE = Path(__file__).parent


class PlayerController(QObject):
    tick = Signal()

    def __init__(self, mp):
        super().__init__()
        self.mp = mp
        t = QTimer(self)
        t.timeout.connect(self.tick)
        t.start(200)

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


class RoundedFrame(QFrame):
    def __init__(self, radius=8):
        super().__init__()
        self.radius = radius

    def resizeEvent(self, e):
        super().resizeEvent(e)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self.radius, self.radius)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))


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
        self.setStyleSheet("#root { background: #1b1b1b; }")

        self.instance = vlc.Instance()
        self.mp = self.instance.media_player_new()

        self.video = RoundedFrame(9)
        self.video.setStyleSheet("background:#2d2b29")

        self.player_ctrl = PlayerController(self.mp)
        self.win_ctrl = WindowController(self)

        self.top = make_quick("win", self.win_ctrl, "TopBar.qml", 40)
        self.bar = make_quick("player", self.player_ctrl, "ControlBar.qml", 54)

        # Canvas area: 10px side margins and 1px gap below the top bar (from the design)
        canvas = QWidget()
        cl = QVBoxLayout(canvas)
        cl.setContentsMargins(10, 1, 10, 0)
        cl.addWidget(self.video)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.top)
        lay.addWidget(canvas, 1)
        lay.addWidget(self.bar)
        self.resize(1100, 640)

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
        self.win_ctrl.set_folder(Path(path).parent.name)
        self.mp.set_media(self.instance.media_new(path))
        # Embeds libVLC video into the native frame; needs X11 (run with QT_QPA_PLATFORM=xcb on Wayland)
        self.mp.set_xwindow(int(self.video.winId()))
        self.mp.play()


# libVLC embeds the video through an X11 window id, so on Linux the app must run
# through XWayland. Set it before QApplication is created; an existing value wins.
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

app = QApplication(sys.argv)
w = Window()
w.show()
sys.exit(app.exec())