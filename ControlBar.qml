import QtQuick

Rectangle {
    id: root
    color: Theme.bg
    implicitHeight: Theme.barHeight

    // The design is 1920px wide. Everything on the right side is positioned
    // from the right edge, so the bar adapts to narrower windows.
    function rx(d) { return root.width - (1920 - d) }

    function fmt(ms) {
        var s = Math.max(0, Math.floor(ms / 1000))
        var h = Math.floor(s / 3600)
        var m = Math.floor((s % 3600) / 60)
        var sec = s % 60
        return [h, m, sec].map(function (n) { return n < 10 ? "0" + n : n }).join(":")
    }

    component Icon: Image {
        id: ic
        signal clicked()
        opacity: hh.hovered ? 1.0 : 0.75
        HoverHandler { id: hh; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: ic.clicked() }
    }

    // previous / play-pause / next (centers at x = 35.5 / 85 / 135.5)
    Icon {
        x: 35.5 - width / 2
        y: (root.height - height) / 2
        source: "assets/icons/player_prev_button.svg"
    }

    Item {
        x: 58; y: 13; width: 54; height: 28
        Image {
            anchors.centerIn: parent
            source: "assets/icons/player_play_button.svg"
            visible: !player.playing
        }
        Image {
            anchors.centerIn: parent
            source: "assets/icons/player_pause_button.svg"
            visible: player.playing
        }
        HoverHandler { cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: player.togglePlay() }
    }

    Icon {
        x: 135.5 - width / 2
        y: (root.height - height) / 2
        source: "assets/icons/player_next_button.svg"
    }

    // current time
    Text {
        x: 177
        anchors.verticalCenter: parent.verticalCenter
        text: root.fmt(player.timeMs)
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSize
    }

    // seek bar: 28px track, played part inset by 2px, 8px handle
    Item {
        id: seek
        x: 254
        y: 13
        width: root.rx(1492) - 254
        height: 28

        Rectangle { anchors.fill: parent; radius: Theme.radius; color: Theme.track }

        Rectangle {
            id: playedRect
            x: 2; y: 2
            height: 24
            width: Math.max(8, (seek.width - 4) * player.position)
            radius: 4
            color: Theme.played
            visible: !player.live
        }
        Rectangle {
            visible: !player.live
            x: playedRect.x + playedRect.width - width
            y: 2
            width: 8; height: 24
            radius: 4
            color: Theme.accent
        }

        // streams: connection status, or station / now playing, instead of the progress
        Text {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            text: player.statusText !== "" ? player.statusText : (player.live ? player.title : "")
            visible: text !== ""
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSize
        }

        MouseArea {
            anchors.fill: parent
            enabled: !player.live
            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
            function seekTo(mx) {
                player.seek(Math.max(0, Math.min(1, (mx - 2) / (seek.width - 4))))
            }
            onPressed: (m) => seekTo(m.x)
            onPositionChanged: (m) => { if (pressed) seekTo(m.x) }
        }
    }

    // total time
    Text {
        x: root.rx(1506)
        anchors.verticalCenter: parent.verticalCenter
        text: player.live ? "LIVE" : root.fmt(player.lengthMs)
        color: player.live ? Theme.accent : Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSize
    }

    // volume
    Icon { x: root.rx(1596); y: 15; source: "assets/icons/player_volume_button.svg" }

    Item {
        id: vol
        x: root.rx(1628)
        y: 13
        width: 89
        height: 28
        property real level: Math.max(0, Math.min(1, player.volume / 100))

        Image { source: "assets/icons/player_volumebar_button.svg" }
        Item {
            width: 1.5 + 86 * vol.level
            height: vol.height
            clip: true
            Image { source: "assets/icons/player_volumebar_progress_full.svg" }
        }
        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            function setLevel(mx) {
                player.setVolume(Math.round(100 * Math.max(0, Math.min(1, (mx - 1.5) / 86))))
            }
            onPressed: (m) => setLevel(m.x)
            onPositionChanged: (m) => { if (pressed) setLevel(m.x) }
        }
    }

    // right-hand icons
    Icon { x: root.rx(1739); y: 15; source: "assets/icons/player_equalizer_button.svg" }
    Icon { x: root.rx(1781); y: 15; source: "assets/icons/player_subtitles_button.svg" }
    Icon { x: root.rx(1823); y: 15; source: "assets/icons/player_mediasettings_button.svg" }
    Icon { x: root.rx(1870); y: 11; source: "assets/icons/player_tabsmenu_button.svg" }
}