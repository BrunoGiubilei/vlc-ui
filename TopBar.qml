import QtQuick

Rectangle {
    id: root
    color: Theme.chrome
    implicitHeight: Theme.topBarHeight

    component Icon: Image {
        id: ic
        signal clicked()
        opacity: hh.hovered ? 1.0 : 0.75
        HoverHandler { id: hh; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: ic.clicked() }
    }

    // drag to move the window, double-click to maximize
    DragHandler {
        target: null
        onActiveChanged: if (active) win.startMove()
    }
    TapHandler { onDoubleTapped: win.toggleMaximize() }

    // left side (exact coordinates from the Figma design)
    Icon { x: 6;   y: 6; source: "assets/icons/vlc_icon.svg" }
    Icon { x: 51;  y: 6; source: "assets/icons/more_options.svg" }
    Icon { x: 89;  y: 6; source: "assets/icons/leftsidebar_menu_button.svg" }
    Image { x: 117; y: 8; source: "assets/icons/separator_menu.svg" }
    Icon { x: 143; y: 8; source: "assets/icons/folder_button.svg"; onClicked: win.openMedia() }

    Text {
        x: 173
        anchors.verticalCenter: parent.verticalCenter
        text: win.folder
        color: Theme.title
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSize
        HoverHandler { cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: win.openMedia() }
    }

    // centered title
    Text {
        anchors.centerIn: parent
        text: "VLC Media Player"
        color: Theme.title
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSize
    }

    // right side: four 24px icons, 12px apart, 12px from the edge
    Icon { x: root.width - 144; y: 8; source: "assets/icons/minimize_button.svg"; onClicked: win.minimize() }
    Icon { x: root.width - 108; y: 8; source: "assets/icons/maximize_button.svg"; onClicked: win.toggleMaximize() }
    Icon { x: root.width - 72;  y: 8; source: "assets/icons/fullscreen_button.svg"; onClicked: win.toggleFullscreen() }
    Icon { x: root.width - 36;  y: 8; source: "assets/icons/close_button.svg"; onClicked: win.closeWindow() }
}