pragma Singleton
import QtQuick

QtObject {
    readonly property color chrome: "#1b1b1b"
    readonly property color bg: "#1b1b1b"
    readonly property color canvas: "#2d2b29"
    readonly property color track: "#090909"
    readonly property color played: "#371f06"
    readonly property color accent: "#d37918"
    readonly property color text: "#8f8f8f"
    readonly property color title: "#8f8f8f"

    readonly property string fontFamily: "Inter"
    readonly property int fontSize: 14

    readonly property int topBarHeight: 40
    readonly property int barHeight: 54
    readonly property int radius: 6
    readonly property int canvasRadius: 9
    readonly property int canvasMargin: 10
}