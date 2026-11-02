# Current status

> This file is updated after every change to the project. Newest entries go at the top of the [changelog](#changelog).

**Last updated:** 2026-11-02 (launcher, `.desktop` installer and `QT_QPA_PLATFORM` default added)
**Stage:** work in progress. Playback of local files works. Playlist, sidebar and menus do not exist yet.
**Test environment:** Ubuntu, Wayland, run through XWayland (`QT_QPA_PLATFORM=xcb`), fish shell.

## Working

- Frameless window with custom top bar: drag to move, double-click to maximize, minimize, maximize, fullscreen and close buttons
- Open a local media file from the folder button or the folder label in the top bar (`QFileDialog`)
- libVLC playback embedded in the rounded video frame (X11 `set_xwindow`)
- Play / pause
- Seek bar with played fill and handle; click or drag to seek
- Current time and total time (`HH:MM:SS`)
- Volume wedge from the design; click or drag to set the volume
- Layout adapts to narrower windows (right side of the control bar anchored to the window edge)

## Drawn but not wired

These elements exist in the QML (they match the design) but do nothing yet.

| Element | File | Needs |
|---------|------|-------|
| Previous / next buttons | `ControlBar.qml` | Playlist |
| Volume icon (mute) | `ControlBar.qml` | A `mute` slot in `PlayerController` |
| Equalizer, subtitles, media settings, tabs menu icons | `ControlBar.qml` | Their menus |
| VLC icon, "more options", left sidebar button | `TopBar.qml` | Menu and sidebar |

## Priority queue

The owner wants these two **before everything else on the roadmap**.

### 1. URL streaming (for example an online radio)

Goal: open a network URL (HTTP/HTTPS stream, radio, playlist URL) and play it.

Notes for the implementation:
- libVLC already plays URLs: `instance.media_new(url)` instead of a file path. The work is mostly UI and state.
- Needs an input for the URL (dialog or a small QML field) and an entry point in the top bar.
- Live streams have no real length: `get_length()` returns `-1`/`0` and `get_position()` is not meaningful. `PlayerController` needs an `isLive` property and the control bar needs a live state (hide or disable the seek bar, show "LIVE" instead of the total time).
- A radio has no video. The canvas will be empty, so it needs a placeholder (for example the stream title or an icon).
- Stream metadata (station and now-playing title) can be read from the media (`get_meta`) and its events; this is optional for a first version.
- Handle errors (invalid URL, no network, stream down) with a visible message instead of silence.
- Decide how the top bar label behaves: today it shows the parent folder name of the file; for a stream it should show the host or station name.

### 2. Run as a standalone program

**Status: first step done, waiting for a test on the owner's machine.**

Goal: start the player without activating the venv and exporting variables by hand. The old way was:

```fish
cd ~/Projetos/vlc-ui-git/ && source .venv/bin/activate.fish && set -x QT_QPA_PLATFORM xcb && python main.py
```

Done (option 1 below):
- `main.py` sets `QT_QPA_PLATFORM=xcb` by default on Linux, before `QApplication` is created. A value already set in the environment wins, so it can still be overridden (for example `QT_QPA_PLATFORM=wayland`).
- `vlc-ui`: launcher script. Finds the project folder even through a symlink, runs `.venv/bin/python main.py`, and prints a clear message if the venv is missing.
- `install-desktop.sh`: installs a symlink at `~/.local/bin/vlc-ui` and an application menu entry at `~/.local/share/applications/vlc-ui.desktop` with absolute paths (`.desktop` files do not expand `~`). `./install-desktop.sh --uninstall` removes both. Run it again if the project folder moves.

Usage:

```sh
cd ~/Projetos/vlc-ui-git/
./install-desktop.sh
vlc-ui                # or open "VLC UI" from the application menu
```

Not done yet:
- The player does not open files passed on the command line, so "Open with" and `MimeType` associations are not set up. Needs `sys.argv` handling in `main.py`.
- The window may not group under the right icon in the dock on some desktops; if so, set the application/desktop file name in Qt and add `StartupWMClass` to the `.desktop` file.
- Compiled executable (PyInstaller or `pyside6-deploy`) and AppImage/Flatpak: not started. QML files and `assets/icons/` would have to be bundled, and libVLC would still come from the system VLC install. Only worth it if the launcher is not enough.

Options considered, simplest first: 1) launcher script + `.desktop` (done), 2) compiled executable, 3) AppImage or Flatpak.

## Roadmap (after the priority queue)

- Previous / next buttons and a playlist
- Left sidebar and the "more options" menu
- Equalizer, subtitles and media settings menus
- Window resizing from the edges (frameless window)
- Overlay controls on top of the video (libVLC video callbacks or libmpv)
- Windows and macOS support

## Known issues and technical debt

- Hard-coded colors and sizes in `main.py` duplicate `Theme.qml` (see `STYLE_GUIDE.md`, "Known deviations").
- `main.py` starts the application at module level, with no `__main__` guard.
- Everything lives in `main.py`; controllers should be split into modules when playlist and stream controllers arrive.
- `PlayerController` reads libVLC on every property access after each 200 ms tick; fine for now, but worth reviewing if more properties are added.
- Video only embeds on X11 (`set_xwindow`); on Linux the app now forces `xcb` (XWayland) by default. Windows and macOS are untested.
- The control bar sits below the video; overlays on top of the video are blocked by the native video window.

## Project files

| File | Purpose |
|------|---------|
| `README.md` | Public description, install and run instructions, roadmap |
| `ARCHITECTURE.md` | Class diagrams and data flow |
| `STYLE_GUIDE.md` | Python and QML conventions of this project |
| `CURRENT_STATUS.md` | This file |
| `vlc-ui` | Launcher script (runs `main.py` with the project's `.venv`) |
| `install-desktop.sh` | Installs/removes the `~/.local/bin/vlc-ui` symlink and the `.desktop` menu entry |

## Changelog

### 2026-11-02 (later)
- `main.py`: added `import os` and a Linux-only default `QT_QPA_PLATFORM=xcb`, set before `QApplication` (existing value is respected).
- Added `vlc-ui` launcher script and `install-desktop.sh` (installs/removes the symlink and the `.desktop` entry).
- Priority item 2 (standalone program): first step done; not yet tested on the owner's machine. Class structure unchanged, so `ARCHITECTURE.md` needed no update.

### 2026-11-02
- Added `ARCHITECTURE.md` (class diagrams, QML structure, data flow, planned structure).
- Added `STYLE_GUIDE.md` (Python and QML conventions, checklists, known deviations).
- Added `CURRENT_STATUS.md` (this file).
- Roadmap changed: URL streaming and running as a standalone program are now the first two items, before the playlist and everything else.
- No code changes.
