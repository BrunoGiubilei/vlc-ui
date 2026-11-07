# Style guide

Conventions for `vlc-ui`. They describe what the code already does, plus a few rules for new code so the project stays consistent. When a rule and the code disagree, the code is listed under [Known deviations](#known-deviations) and should be fixed when touched.

See [ARCHITECTURE.md](ARCHITECTURE.md) for how the pieces fit together.

## 1. General

- **Language:** code, comments, identifiers, commit messages and docs are in English.
- **Indentation:** 4 spaces in Python and QML. No tabs.
- **Comments explain why**, not what. Good examples already in the code: the X11 note on `set_xwindow`, and the explanation of `rx(d)`.
- **Design first:** the Figma design by @juxtopposed is the source of truth for colors, spacing, sizes and icons. Do not invent values; take them from the design and put them in `Theme.qml`.

## 2. Python

### 2.1 Naming

| Kind | Style | Examples |
|------|-------|----------|
| Classes | `PascalCase` | `PlayerController`, `RoundedFrame` |
| Python-only functions and methods | `snake_case` | `open_media`, `set_folder`, `make_quick` |
| Anything **exposed to QML** (properties, slots, signals) | `camelCase` | `timeMs`, `togglePlay`, `setVolume`, `folderChanged` |
| Module constants | `UPPER_CASE` | `HERE` |
| Context property names | short, lowercase | `win`, `player` |

The split matters: if a QML file can see a name, it is `camelCase`. If only Python can see it, it is `snake_case`. `WindowController.set_folder` is `snake_case` because only `Window` calls it, while `folder` (the property QML reads) is not.

### 2.2 Imports

- Standard library first, then third-party (`vlc`, `PySide6`), then local modules.
- Import only the Qt classes that are used, by module (`PySide6.QtCore`, `PySide6.QtGui`, `PySide6.QtQuickWidgets`, `PySide6.QtWidgets`).
- Paths are built from `HERE = Path(__file__).parent` with `pathlib`, never from the current working directory. The app must work no matter where it is launched from.

### 2.3 Controllers (Python <-> QML bridge)

- A controller is a `QObject` with a narrow job (see the responsibilities table in `ARCHITECTURE.md`). One controller per area: playback, window, and later playlist and stream.
- **Read-only state** uses `@Property(type, notify=signal)`. Always give the type and a notify signal.
- **Polled playback state** shares the single `tick` signal of `PlayerController`.
- **Actions** use `@Slot(...)` with explicit argument types: `@Slot()`, `@Slot(float)`, `@Slot(int)`.
- **State owned by Python and pushed to QML** (like the folder name) uses a private field plus a dedicated `...Changed` signal, and a `snake_case` setter that emits it.
- Properties return safe values. libVLC returns `-1` when it does not know a value yet, so use `max(0, ...)` as the existing properties do.
- Controllers do not import or reference QML items. QML does not import Python modules. The only bridge is the context property.
- Controllers that need the window receive it in `__init__` and use its public methods (`open_media`, `showMaximized`, ...). They do not reach into its layout.

### 2.4 Widgets and QML hosts

- Every QML area is created with `make_quick(ctx_name, ctrl, qml, height)`. Do not build `QQuickWidget`s by hand elsewhere.
- Use `QQuickWidget.SizeRootObjectToView` and a fixed height set from the matching `Theme` token.
- Native video stays in a widget, never in QML (see `ARCHITECTURE.md`, section 6).

### 2.5 Network access and background threads

- Anything that waits on the network runs in a background thread; the interface thread never blocks on it. See `NowPlayingSource`.
- A thread reports back only through a Qt `Signal`; it never touches widgets or controllers directly. The receiver in `Window` checks that the answer still belongs to the current source.
- Optional dependencies (like `dbus-fast`) are imported inside `try/except ImportError`; the feature turns itself off with one clear message on stderr and the player keeps working.
- A service that lives on another bus or thread (MPRIS) keeps its own copy of the state it publishes; the `Window` pushes that state, and the service sends requests back as a Qt `Signal`. It never calls the player directly.
- Data that differs per station (endpoints, JSON fields) lives in `nowplaying.json`, not in the code.
- Network failures are expected: catch them, keep the last good value for a short time, and do not show stale data forever.

### 2.6 Plain widgets inside the video frame

- Anything drawn over the video area (like `NowPlayingPanel`) is a plain Qt widget, never a `QQuickWidget`: the frame is a native window and plain widgets are the safe choice there. Such a widget is only visible while libVLC has no video, because libVLC draws its own window on top.
- A widget inside the frame must not raise the window's minimum size: use `QSizePolicy.Ignored` and size its content from the space it is given.

### 2.7 libVLC

- One `vlc.Instance` and one `MediaPlayer`, owned by `Window`.
- Platform-specific embedding (`set_xwindow`) lives in one place (`Window.open_media`). If Windows or macOS support is added, extend that spot with a platform switch instead of scattering checks.
- Do not set `QT_QPA_PLATFORM` in documentation examples without saying why (Wayland, XWayland). See the README, "Platform notes".

## 3. QML

### 3.1 Files and imports

- Each visual area is one QML file named in `PascalCase` (`TopBar.qml`, `ControlBar.qml`).
- Import only `QtQuick` (add other modules only when needed).
- **Do not write `import Theme`.** `Theme.qml` is a singleton registered in `qmldir`, which sits next to the QML files and is found through the import path that `make_quick` adds. Adding the import causes `module "Theme" is not installed`.
- New QML files that other files use by name must be listed in `qmldir`.
- Root item of an area is a `Rectangle` with `id: root`, `color` from `Theme`, and `implicitHeight` from the matching `Theme` token.

### 3.2 Theme and design tokens

- Colors, font family, font size, bar heights and radii come from `Theme`. No hard-coded hex colors or magic sizes in `TopBar.qml` or `ControlBar.qml`.
- Python widgets get the same values from `THEME = load_theme(HERE / "Theme.qml")` (`theme.py`), for example `THEME["canvas"]` or `THEME["barHeight"]`. Do not copy a color or size into Python.
- If the design needs a new value, add it to `Theme.qml` as `readonly property` with a descriptive name, then use it.
- Token names describe the role, not the value (`track`, `played`, `accent`), so a palette change does not rename anything.
- Current tokens: `chrome`, `bg`, `canvas`, `track`, `played`, `accent`, `text`, `title`, `fontFamily`, `fontSize`, `topBarHeight`, `barHeight`, `radius`, `canvasRadius`, `canvasMargin`.
- Text always sets `font.family: Theme.fontFamily` and `font.pixelSize: Theme.fontSize` (unless the design calls for another size, in which case add a token).

### 3.3 Positioning

- The layout follows the Figma frame with **absolute coordinates** copied from the design (`x: 143; y: 8`). Add a short comment when the numbers come from a specific design measurement.
- Left-side elements use plain `x`. Right-side elements in the control bar use `root.rx(d)`, where `d` is the x position in the 1920 px design. This keeps them anchored to the right edge.
- In the top bar, right-side buttons are positioned from `root.width` (`root.width - 36`, ...), 12 px apart.
- Center things with `anchors.verticalCenter` / `anchors.centerIn` or `(root.height - height) / 2`, not with guessed offsets.

### 3.4 Interaction

- Clickable icons use the inline `component Icon: Image` pattern: hover raises opacity from `0.75` to `1.0`, `HoverHandler` gives the pointing-hand cursor, `TapHandler` emits `clicked()`. Reuse it; do not copy-paste variants.
- Use `HoverHandler`, `TapHandler` and `DragHandler` for simple interaction.
- Use `MouseArea` only for press-and-drag sliders (seek bar, volume), where it needs `onPressed` plus `onPositionChanged` while `pressed`.
- Clamp slider math to `0..1` before calling a controller, as the seek and volume handlers do.
- QML calls controllers by their context name: `win.openMedia()`, `player.togglePlay()`. QML does not compute playback state; it displays what the controller reports.
- Time is formatted with the shared `fmt(ms)` helper in `ControlBar.qml` (`HH:MM:SS`). Reuse it for any new time display.

### 3.5 Icons

- SVGs exported from Figma live in `assets/icons/`, referenced by relative path (`assets/icons/player_play_button.svg`).
- Naming: playback controls use `player_<name>_button.svg` (`player_prev_button`, `player_volumebar_button`); window and menu buttons use `<name>_button.svg` (`minimize_button`, `folder_button`); other icons keep the Figma layer name in `snake_case` (`more_options`, `separator_menu`).
- Names are lowercase `snake_case`. The file name in QML must match exactly, including case.
- Export icons at the size they have in the design. Do not scale them in QML to fix a wrong export; re-export instead.

## 4. Platform notes for contributors

- Develop and test on Wayland with `QT_QPA_PLATFORM=xcb` (XWayland). The video only embeds through X11.
- fish shell: `set -x QT_QPA_PLATFORM xcb`, or `env QT_QPA_PLATFORM=xcb python main.py`. bash/zsh: `QT_QPA_PLATFORM=xcb python main.py`.
- Run from any directory; paths must not depend on the working directory.
- Recent Qt needs `libxcb-cursor0` for the `xcb` plugin.

## 5. Adding things (checklists)

**New UI element in an existing bar**
1. Add the token(s) to `Theme.qml` if the design introduces new values.
2. Export the icon to `assets/icons/` using the naming above.
3. Position it with the Figma coordinates; use `rx(d)` on the right side of the control bar.
4. Reuse `Icon` for clickable icons.
5. Wire it to a controller slot instead of putting logic in QML.

**New controller property or action**
1. Add `@Property` (with a notify signal) or `@Slot` with types; `camelCase` name.
2. Use `max(0, ...)` or another safe default for values libVLC may not know yet.
3. Use it from QML through the context property.
4. Update the class diagram in `ARCHITECTURE.md`.

**Any change**
- Update `CURRENT_STATUS.md` (what changed, what is next).

## Known deviations

These exist in the current code and should be cleaned up when the surrounding code is touched.

| Where | Deviation | Fix |
|-------|-----------|-----|
| `main.py` bottom | The application starts at module level, with no `if __name__ == "__main__":` guard | Wrap start-up in a `main()` function |
| `main.py` | Everything is in a single file | Split controllers into modules when the playlist and stream controllers are added |
