#!/bin/sh
# Installs the vlc-ui launcher for the current user:
#   ~/.local/bin/vlc-ui                         (symlink to the launcher)
#   ~/.local/share/applications/vlc-ui.desktop  (application menu entry)
# .desktop files do not expand "~" or relative paths, so absolute paths are written here.
# Remove with: ./install-desktop.sh --uninstall
set -e

SELF=$(readlink -f "$0")
DIR=$(dirname "$SELF")
BIN_DIR="$HOME/.local/bin"
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP="$APPS_DIR/vlc-ui.desktop"

if [ "$1" = "--uninstall" ]; then
    rm -f "$BIN_DIR/vlc-ui" "$DESKTOP"
    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS_DIR" || true
    echo "Removed $BIN_DIR/vlc-ui and $DESKTOP"
    exit 0
fi

chmod +x "$DIR/vlc-ui"
mkdir -p "$BIN_DIR" "$APPS_DIR"
ln -sf "$DIR/vlc-ui" "$BIN_DIR/vlc-ui"

cat > "$DESKTOP" <<DESKTOP_ENTRY
[Desktop Entry]
Type=Application
Name=VLC UI
Comment=Modern VLC interface built with PySide6/QML and libVLC
Exec=$DIR/vlc-ui
Icon=$DIR/assets/icons/vlc_icon.svg
Terminal=false
Categories=AudioVideo;Player;Video;
DESKTOP_ENTRY

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS_DIR" || true

echo "Installed. Launch from the application menu or run: vlc-ui"
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "Note: $BIN_DIR is not in your PATH (fish: fish_add_path $BIN_DIR)" ;;
esac
