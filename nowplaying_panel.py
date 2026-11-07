"""Panel inside the video frame for audio streams: cover art, song, artist and album.

It is a plain Qt widget (not QML) on purpose: the frame is a native window that libVLC
draws into, and a plain child widget is only visible while there is no video, which is
exactly when this panel is wanted.
"""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

MAX_COVER = 380       # largest cover edge, in pixels
MIN_COVER = 100       # below this the cover is hidden and only the text remains
TEXT_BLOCK = 130      # height kept free for the text under the cover
COVER_RADIUS = 12


class NowPlayingPanel(QWidget):
    def __init__(self, parent, theme):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        # The panel must not stop the window from being resized smaller
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._cover = None
        self._cover_url = ""

        color = QColor(theme["text"])
        dim = QColor(color)
        dim.setAlphaF(0.7)

        self.cover_label = QLabel()
        self.song_label = self._label(theme, 22, True, color)
        self.artist_label = self._label(theme, 16, False, color)
        self.album_label = self._label(theme, 13, False, dim)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setStyleSheet("background: transparent")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(6)
        layout.addStretch(1)
        layout.addWidget(self.cover_label, 0, Qt.AlignHCenter)
        layout.addSpacing(10)
        for label in (self.song_label, self.artist_label, self.album_label):
            layout.addWidget(label)
        layout.addStretch(1)
        self.hide()

    @staticmethod
    def _label(theme, pixel_size, bold, color):
        label = QLabel()
        font = QFont(theme["fontFamily"])
        font.setPixelSize(pixel_size)
        font.setBold(bold)
        label.setFont(font)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"background: transparent; color: rgba({color.red()}, {color.green()}, "
                            f"{color.blue()}, {color.alphaF():.2f})")
        return label

    def set_info(self, info):
        """Shows the song described by `info` (see nowplaying.read_song); empty text hides the panel."""
        if not info.get("text"):
            self.clear()
            return
        url = info.get("cover", "")
        if url != self._cover_url:  # a different cover: do not keep showing the old one
            self._cover = None
            self._cover_url = url
        self.song_label.setText(info.get("song") or info["text"])
        self.artist_label.setText(info.get("artist", ""))
        self.album_label.setText(" \u00b7 ".join(p for p in (info.get("album", ""), info.get("year", "")) if p))
        for label in (self.artist_label, self.album_label):
            label.setVisible(bool(label.text()))
        self._update_cover()
        self.show()

    def set_cover(self, url, data):
        """Sets the cover for `url`; ignored if the song has changed in the meantime."""
        if url != self._cover_url:
            return
        pixmap = QPixmap()
        self._cover = pixmap if data and pixmap.loadFromData(data) else None
        self._update_cover()

    def cover_pixmap(self):
        return self._cover

    def clear(self):
        self._cover = None
        self._cover_url = ""
        self.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_cover()

    def _update_cover(self):
        size = int(min(self.width() * 0.6, self.height() - TEXT_BLOCK, MAX_COVER))
        if self._cover is None or size < MIN_COVER:
            self.cover_label.hide()
            return
        ratio = self.devicePixelRatioF()
        edge = int(size * ratio)
        scaled = self._cover.scaled(edge, edge, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        rounded = QPixmap(edge, edge)
        rounded.fill(Qt.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, edge, edge), COVER_RADIUS * ratio, COVER_RADIUS * ratio)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, scaled)
        painter.end()
        rounded.setDevicePixelRatio(ratio)
        self.cover_label.setPixmap(rounded)
        self.cover_label.setFixedSize(size, size)
        self.cover_label.show()
