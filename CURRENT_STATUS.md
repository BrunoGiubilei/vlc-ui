# Current status

> This file is updated after every change to the project. Newest entries go at the top of the [changelog](#changelog).

**Last updated:** 2026-11-03 (system tray added)
**Stage:** work in progress. Playback of local files works. Playlist, sidebar and menus do not exist yet.
**Test environment:** Ubuntu, Wayland, run through XWayland (`QT_QPA_PLATFORM=xcb`), fish shell.

## Working

- Frameless window with custom top bar: drag to move, double-click to maximize, minimize, maximize, fullscreen and close buttons
- Open a local media file from the folder button or the folder label in the top bar (`QFileDialog`)
- Open a network stream (online radio and similar) with `Ctrl+N`, or a URL / file passed on the command line. The control bar shows connection status, station and now-playing text, and `LIVE` instead of the total time
- Song title from a station's own API (`nowplaying.py` + `nowplaying.json`), used for Antena 1 whose stream only carries filler; other streams keep using the ICY metadata
- Cover art, song, artist and "Album · year" in the empty video area for stations with a source in `nowplaying.json`; a desktop notification (with the cover) for each new song while the window is hidden; the tray tooltip shows what is playing
- System tray: closing the window hides it and playback continues; tray icon with Show/Hide, Play/Pause, Open network stream and Quit; left click shows/hides, middle click plays/pauses. Without a tray, closing quits as before
- Run without activating the venv: `vlc-ui` launcher, `install-desktop.sh` and the default `QT_QPA_PLATFORM=xcb` in `main.py`
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

Both items the owner put first are now implemented. Item 1 was tested here only with a stubbed libVLC (logic and rendering), so it still needs a test with a real stream on the owner's machine.

### 1. URL streaming: implemented, needs a real-stream test

How it works: see `ARCHITECTURE.md`, section 4.4.
- Entry points: `Ctrl+N` (URL dialog, pre-filled from the clipboard), `win.openUrl()` for a future QML button, and a URL on the command line (`vlc-ui https://...`). A file path on the command line also works now.
- Accepted schemes: http, https, rtsp, rtmp, mms, mmsh, udp, rtp, ftp. Text without a scheme is treated as `http://`.
- `PlayerController` has `live`, `statusText` and `title`. In `ControlBar.qml` a live stream hides the progress, shows status or station / now playing in the seek bar, shows `LIVE` as the total time and disables seeking.
- The top bar label shows the stream host.

To verify on a real stream (not possible in the sandbox):
- A direct stream URL (for example an Icecast/Shoutcast `.mp3` or `.aac` URL) plays and shows `LIVE`.
- The station and now-playing text appear and update (ICY metadata, read with `get_meta`; best effort). If they do not, run `python tools/icy_probe.py URL --vlc`: it shows whether the station sends a title at all and what libVLC reports, which tells a station limitation from an app bug.
- "Connecting..." / "Buffering..." show up and a dead URL ends in "Could not play this stream".
- A video stream still shows the picture inside the frame.

Not done:
- Playlist URLs (`.m3u`, `.pls`): the player uses a plain `MediaPlayer`, which does not expand playlists. Many radios publish these, so it is the likely next fix (parse the playlist and play the first entry, or use a media list player).
- Song title for Antena 1 (`https://antenaone.crossradio.com.br/stream`): implemented and confirmed working by the owner on the real stream (2026-11-06). The stream's ICY metadata only carries filler (`'ANTENA 1 - ANTENA 1'`), so the player polls the station's own endpoint (`https://www.antena1.com.br/api/v1/aovivo/getCurrentSongInfo/antena_1`) every 10 s, as configured in `nowplaying.json`. Verified here against a fake server with the real response shape (cache-buster parameter, fallback to the exact URL, change detection, failures, replacing and stopping sources); the real endpoint was not reachable from the sandbox. To check on the owner's machine: the bar shows "Artist - Song" and it changes with the song; if it stays on filler, the `FYC` parameter may be required to keep its original value (the code already falls back to the exact URL) or the endpoint changed. Endpoints like this are not public APIs and can change without notice.
- The API answer also has more than is used today: `album`, `year`, `cover` (image URL, 1000x1000), `lyrics` and `lyricsTranslation` (HTML), `artistShortBio` (HTML, truncated), `itunes` (link), `time` (when the song started) and `songId` / slugs. Only artist and song are used. Ideas, in the order they seem worth doing:
  1. ~~Song change notification and tray tooltip~~ done (2026-11-06).
  2. ~~Cover art and "Album, year" in the canvas for audio streams~~ done (2026-11-06).
  3. MPRIS (D-Bus): song, artist and cover in the desktop's media widget and lock screen, and the keyboard media keys for play/pause. Fits the tray / background use.
  4. Lyrics (with the Portuguese translation) in a panel. Needs a place in the interface; fits the planned sidebar. The text is HTML with `<br>` and is third-party content served by the station's site.
  5. History of songs played in this session, and a button to open the song in iTunes.
- Other stations need their own entry in `nowplaying.json` (see the README).
- There is no visible button for "Open network stream" yet; the design has no icon for it. Decide whether it goes in the "more options" menu.
- Radio has no video: the canvas stays empty, as it does for audio files.
- Reconnect after the stream drops.

### 2. Run as a standalone program: implemented (first step)

Tested by the owner. `main.py` sets `QT_QPA_PLATFORM=xcb` by default on Linux (an existing value wins); `vlc-ui` is the launcher; `install-desktop.sh` installs the `~/.local/bin/vlc-ui` symlink and the `.desktop` entry (`--uninstall` removes both).

Not done:
- The window may not group under the right icon in the dock on some desktops; if so, set the application/desktop file name in Qt and add `StartupWMClass` to the `.desktop` file.
- Compiled executable (PyInstaller or `pyside6-deploy`) and AppImage/Flatpak. QML files and `assets/icons/` would have to be bundled, and libVLC would still come from the system VLC install. Only worth it if the launcher is not enough.

## Cover, notification and tooltip: implemented, needs a test on the real station

Tested here against a fake station API with real-shaped data and generated cover images (download once per album, missing cover, a new album replacing the old cover, notification only while hidden, tooltip, small and narrow windows). To check on the owner's machine with Antena 1:
- The cover, song, artist and "Album · year" appear in the video area and change with the song.
- Hide the window in the tray and wait for the next song: a notification with the cover should appear (how it looks depends on the desktop; some ignore the icon).
- The tray tooltip shows the song.
- Shrinking the window hides the cover first and keeps the text.

Not done:
- ICY-only stations get the tooltip but no panel and no notification (there is no cover for them).
- Notifications are not configurable (always on while hidden).
- The cover is not shown while a real video plays (libVLC's window covers the frame).

## System tray: implemented, needs a test on the owner's desktop

Logic tested here with a stubbed libVLC and a patched tray (hide on close, show/hide toggle, restore from minimized keeping the maximized state, menu labels, one-time message, quit, close without a tray). A real tray was not available in the sandbox, so please check:
- The tray icon appears on your desktop (GNOME needs the AppIndicator extension; KDE, XFCE and Cinnamon show it by default).
- Closing the window keeps a radio stream playing, and Show brings the window back.
- A **video** keeps playing after hide and show. libVLC draws into the window's X11 id; if the picture does not come back after showing, the fix is to pause the video output while hidden or re-attach with `set_xwindow` on show.
- Quit really ends the process (check with `pgrep -f main.py`).

Not done:
- Single instance: running `vlc-ui` again opens a second player instead of showing the one in the tray.
- Minimize still minimizes normally (it does not go to the tray). Easy to change if wanted.
- Option to start hidden in the tray.
- The tooltip is static ("VLC UI"); it could show the station or title.

## Roadmap

- Single instance (a second `vlc-ui` shows the running window)
- Open-network-stream button / menu entry and playlist URLs (`.m3u`, `.pls`)
- Previous / next buttons and a playlist
- Left sidebar and the "more options" menu
- Equalizer, subtitles and media settings menus
- Window resizing from the edges (frameless window)
- Overlay controls on top of the video (libVLC video callbacks or libmpv)
- Windows and macOS support

## Known issues and technical debt

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
| `nowplaying_panel.py` | Cover, song, artist and album widget inside the video frame |
| `theme.py` | Reads the design tokens of `Theme.qml` for Python widgets |
| `nowplaying.py` / `nowplaying.json` | Song titles from a station's own web API: polling thread, and the list of stations |
| `tools/icy_probe.py` | Diagnostic: shows the ICY metadata, status pages and (with `--vlc`) the libVLC metadata of a radio URL |
| `install-desktop.sh` | Installs/removes the `~/.local/bin/vlc-ui` symlink and the `.desktop` menu entry |

## Changelog

### 2026-11-06 (cover, notification and tooltip)
- New `nowplaying_panel.py` (`NowPlayingPanel`: cover with rounded corners, song, artist, "Album · year"; hides the cover when there is no room) and `theme.py` (`load_theme` reads `Theme.qml`).
- `nowplaying.py`: `read_song` returns a dict (text, artist, song, album, year, cover); `fetch_cover` (size limit, http/https only); `NowPlayingSource` emits `updated(dict)` and `cover_loaded(dict)`, downloading the cover once per album. `nowplaying.json`: album, year and cover fields for Antena 1.
- `main.py`: `THEME`, the panel inside the video frame, `_on_cover`, `notify_song` (only while the window is hidden or minimized, cover as icon), `sync_tray_tooltip`. Window colors, bar heights, canvas margin and radius now come from `Theme.qml`, which removes the two "Known deviations" about duplicated values.
- Fixed while testing: the panel's size requirements kept the window from shrinking below ~590 px of height; it now ignores the layout's minimum size.
- Docs updated (README, `ARCHITECTURE.md`, `STYLE_GUIDE.md`). Tested with a fake station API and stubbed libVLC; not yet tested on the real station.

### 2026-11-06 (confirmation)
- The owner confirmed that the song title from the Antena 1 API shows correctly in the player, running from the application menu. Possible uses of the other fields in the API answer were listed under the stream notes. No code changes.

### 2026-11-06 (song title from the station's API)
- Added `nowplaying.py` (`load_sources`, `find_source`, `dig`, `read_song`, `NowPlayingSource`) and `nowplaying.json` with the Antena 1 endpoint the owner found in the station's web player.
- `main.py`: `PlayerController.set_now_playing` and `title` prefers it; `Window` starts and stops a `NowPlayingSource` when a stream matching an entry is opened (`_play(..., url)`), ignores late answers from replaced sources, and stops the source on quit.
- README (new "Song titles for radios" section, project structure), `ARCHITECTURE.md` (class diagram, module table, sequence diagram) and `STYLE_GUIDE.md` (network and thread rules) updated.
- Tested against a fake station API with the real response shape: pure functions, the polling thread, and integration with `Window` (stubbed libVLC). Not yet tested against the real endpoint.

### 2026-11-06 (findings, no code changes)
- Ran `tools/icy_probe.py` on the Antena 1 stream (HTTP 200, `audio/aacp`, 96 kbps, `icy-metaint: 16384`, `icy-name: ANTENA1 | 94,7 FM`): the only title received was the station filler, not the song. See the stream notes above.

### 2026-11-03 (now-playing diagnostics)
- Added `tools/icy_probe.py` (standard library only): connects like a player asking for ICY metadata, prints the headers and every `StreamTitle`, probes the usual Shoutcast/Icecast status pages, and with `--vlc` prints what libVLC reports. Tested against local fake Shoutcast servers (`ICY 200 OK` and HTTP replies, a redirect, Latin-1 text, a stream without metadata).
- `main.py`: `PlayerController.set_stream(stream, media)` keeps the media object, and `title` reads it directly instead of calling `get_media()` on every tick.
- `README.md` troubleshooting row and the project files table updated.

### 2026-11-03 (system tray)
- `main.py`: new `TrayIcon` class (menu: Show/Hide, Play/Pause, Open network stream, Quit; left click toggles the window, middle click plays/pauses). `Window` gets `closeEvent`, `show_window`, `toggle_visible`, `quit_app`; closing hides the window when a tray is available, otherwise quits. `setQuitOnLastWindowClosed(False)`.
- `README.md`, `ARCHITECTURE.md` (class diagram, responsibilities, closing/tray sequence diagram) updated.
- Tested with a stubbed libVLC and a patched tray. Not yet tested on a real desktop tray.

### 2026-11-03
- URL streaming. `main.py`: `STREAM_SCHEMES` and `normalize_stream_url`; `PlayerController` gets `set_stream`, `live`, `statusText`, `title`; `WindowController.openUrl`; `Window` gets `play_path`, `open_url_dialog`, `open_url`, `open_argument`, `_play` and the `Ctrl+N` shortcut; a URL or file on the command line is opened at start-up.
- `ControlBar.qml`: stream state (status / station text in the seek bar, `LIVE` total time, no seeking, no progress fill).
- `README.md`: features, usage, how it works, install-as-application section and roadmap updated. `ARCHITECTURE.md`: class diagrams updated and a stream sequence diagram added; the planned `StreamController` was dropped because streaming lives in the existing classes.
- Tested with a stubbed libVLC (URL validation, controller state, QML rendering of live / connecting / file states). Not yet tested with a real stream.

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
