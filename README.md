# vlc-ui

A from-scratch redesign of the VLC media player interface, built with **Python**, **PySide6 (Qt Quick / QML)** and **libVLC**.

The playback engine is VLC's own [libVLC](https://www.videolan.org/vlc/libvlc.html), accessed through the [python-vlc](https://github.com/oaubert/python-vlc) bindings. Everything you see on screen is a new interface, written in QML and based on a community design made in Figma.

> **Status:** work in progress. The top bar, the control bar and basic playback work. Playlist, sidebar and menus are not implemented yet (see [Roadmap](#roadmap)).

## Design credit

The visual design is the work of **[@juxtopposed](https://www.youtube.com/@juxtopposed)**, who redesigned the whole VLC interface in Figma and published the project as open source on the Figma Community:

- Figma file: [VLC Redesign (Community)](https://www.youtube.com/redirect?event=video_description&redir_token=QUZZTVljRW0xRjFhSE1VN0xUbnFWTkh0Rnk5ZXxBSTVJdTV0NkYyZGxuMF9Vd1RTZ1FRTl9aQWtSZ0hJLWs1WWN1VmtqNWxMSnVmVEpTd2pET0VBMGk0YTlDYVVTcEdFMWFCZUxKR2hWdWI3WGthYXd2cG5QcmhhUFQwM2VkWGhx&q=https%3A%2F%2Fwww.figma.com%2Fcommunity%2Ffile%2F1691465999134370980&v=ERFeOgqk324)
- Video that inspired this project: [watch on YouTube](https://www.youtube.com/watch?v=ERFeOgqk324)
- Channel: [youtube.com/@juxtopposed](https://www.youtube.com/@juxtopposed)

All credit for the layout, colors, icons and visual identity goes to her. This repository only implements her design as a working player. Please check the license of the Figma file before redistributing the design assets.

## How this project was made

This project was created with the help of **Claude** (by Anthropic) and was **entirely reviewed by me**, the author. The code was written, tested and adjusted step by step against the Figma design, and I read and ran every part of it before publishing.

## Features

- Frameless window with a custom title bar (drag to move, double-click to maximize, minimize, maximize, fullscreen and close buttons)
- Open media from the folder button in the top bar
- Play / pause, seek bar with played-time fill and handle, current and total time
- Volume control with the gradient wedge from the design
- Rounded video canvas, colors and spacing taken from the Figma frame
- Layout based on the original 1920px design: the right side of the control bar is anchored to the window edge, so it adapts to smaller windows

## Platform notes

This project was developed on **Linux** and tested on **Ubuntu with Wayland**.

> **Important (Wayland):** libVLC embeds the video into a native window using an X11 window ID, so the app must run through XWayland. On Wayland I had to start it with `QT_QPA_PLATFORM=xcb`. Without it, the video opens in a **separate window** instead of inside the player.

For example, in fish:

```fish
set -x QT_QPA_PLATFORM xcb
python main.py
```

Windows and macOS instructions are at the end of this document and are **untested**.

## Requirements

- Python 3.10 or newer
- [VLC](https://www.videolan.org/vlc/) installed on the system (the Python package only calls the installed libVLC library)
- Python packages: `PySide6` and `python-vlc`
- [Inter](https://rsms.me/inter/) font (optional, used by the design; Qt falls back to another font if it is missing)

### Ubuntu / Debian

```bash
sudo apt install vlc libvlc-dev python3-venv fonts-inter libxcb-cursor0
```

`libxcb-cursor0` is needed by recent Qt versions to load the `xcb` platform plugin.

## Installation and running (Linux)

Clone the repository and create a virtual environment.

**bash / zsh:**

```bash
git clone <repository-url> vlc-ui
cd vlc-ui
python3 -m venv .venv
source .venv/bin/activate
pip install PySide6 python-vlc
```

**fish:**

```fish
git clone <repository-url> vlc-ui
cd vlc-ui
python3 -m venv .venv
source .venv/bin/activate.fish
pip install PySide6 python-vlc
```

Run the player:

```bash
# X11 session
python main.py

# Wayland session (required, see "Platform notes")
QT_QPA_PLATFORM=xcb python main.py
```

In fish, use `env QT_QPA_PLATFORM=xcb python main.py` or `set -x QT_QPA_PLATFORM xcb` before running.

To leave the virtual environment, run `deactivate`.

## Usage

- Click the **folder icon** (or the folder label) in the top bar to open a media file.
- Drag the top bar to move the window; double-click it to maximize.
- Click the seek bar to jump to a position, and click or drag on the volume wedge to change the volume.

## Project structure

```
vlc-ui/
├── main.py          # Qt window, libVLC player and Python <-> QML controllers
├── Theme.qml        # Design tokens (colors, sizes, font), registered as a singleton
├── qmldir           # Exposes Theme.qml to the other QML files
├── TopBar.qml       # Custom title bar
├── ControlBar.qml   # Playback controls
└── assets/
    └── icons/       # SVG icons exported from the Figma design
```

### How it works

- The video is rendered by libVLC into a native `QFrame` (`set_xwindow`).
- The top bar and the control bar are `QQuickWidget`s that load QML files.
- `PlayerController` exposes the playback state (position, time, length, volume, playing) to QML and receives actions such as play/pause, seek and volume.
- `WindowController` handles window actions (move, minimize, maximize, fullscreen, close, open media).
- The controls sit *below* the video instead of over it, which avoids the compositing conflict between libVLC's native video window and QML overlays.

## Roadmap

- [ ] Previous / next buttons and a playlist
- [ ] Left sidebar and the "more options" menu
- [ ] Equalizer, subtitles and media settings menus
- [ ] Window resizing from the edges (frameless window)
- [ ] Overlay controls on top of the video (libVLC video callbacks or libmpv)
- [ ] Windows and macOS support

## Troubleshooting

| Problem | Fix |
| --- | --- |
| The video opens in a separate window | Run with `QT_QPA_PLATFORM=xcb` (Wayland) |
| `Could not load the Qt platform plugin "xcb"` | `sudo apt install libxcb-cursor0` |
| `module "Theme" is not installed` | Keep `qmldir` next to the QML files and do not `import Theme` in them |
| An icon does not show up | Check that its file name matches the path in the QML and that it exists in `assets/icons/` |
| `python-vlc` cannot find libVLC | Make sure VLC is installed with the same architecture as Python (64-bit with 64-bit) |

## Credits and licenses

- **Design:** [@juxtopposed](https://www.youtube.com/@juxtopposed), [VLC Redesign (Community)](https://www.figma.com/design/yCqO5zTKEyENr3b54gMfmS/VLC-Redesign--Community-). Check the license of the Figma file for the design and icon assets.
- **Playback engine:** [libVLC](https://www.videolan.org/vlc/libvlc.html), part of the [VLC media player](https://www.videolan.org/vlc/) by [VideoLAN](https://www.videolan.org/). libVLC is licensed under the LGPL 2.1 or later.
- **Python bindings:** [python-vlc](https://github.com/oaubert/python-vlc) by Olivier Aubert, licensed under the LGPL 2.1 or later.
- **UI toolkit:** [Qt for Python (PySide6)](https://doc.qt.io/qtforpython-6/), licensed under the LGPL / GPL / commercial licenses.
- **Font:** [Inter](https://rsms.me/inter/), licensed under the SIL Open Font License.
- **AI assistance:** built with the help of [Claude](https://www.anthropic.com/claude) by Anthropic and fully reviewed by the author.

This is an independent, community project and is **not affiliated with or endorsed by VideoLAN**. "VLC" and the VLC cone are trademarks of VideoLAN.

The license for this repository's own code has not been chosen yet. Add a `LICENSE` file before reusing it.

---

## Windows and macOS (untested)

I developed and tested this project only on Linux, so the steps below are a starting point rather than a verified guide.

The current `main.py` embeds the video with `set_xwindow`, which only exists on X11. On Windows and macOS, replace that call in `open_media` with a platform-specific one:

```python
import sys

wid = int(self.video.winId())
if sys.platform.startswith("linux"):
    self.mp.set_xwindow(wid)
elif sys.platform == "win32":
    self.mp.set_hwnd(wid)
elif sys.platform == "darwin":
    self.mp.set_nsobject(wid)
```

### Windows

1. Install [Python 3.10+](https://www.python.org/downloads/) and [VLC](https://www.videolan.org/vlc/) (64-bit with 64-bit).
2. In PowerShell:

```powershell
git clone <repository-url> vlc-ui
cd vlc-ui
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install PySide6 python-vlc
python main.py
```

If PowerShell blocks the activation script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once. No `QT_QPA_PLATFORM` variable is needed.

### macOS

1. Install Python 3.10+ and [VLC](https://www.videolan.org/vlc/) (the app in `/Applications`).
2. In Terminal:

```bash
git clone <repository-url> vlc-ui
cd vlc-ui
python3 -m venv .venv
source .venv/bin/activate
pip install PySide6 python-vlc
python main.py
```

If `python-vlc` cannot find libVLC, point it to the VLC app's library:

```bash
export PYTHON_VLC_LIB_PATH="/Applications/VLC.app/Contents/MacOS/lib/libvlc.dylib"
```
