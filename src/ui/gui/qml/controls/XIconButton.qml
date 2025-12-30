// 图标按钮
import QtQuick
import "../theme"

Rectangle {
    id: root

    property string icon: ""
    property bool flat: false
    property color hoverColor: flat ? Theme.backgroundHover : Theme.primaryHover
    property color pressedColor: flat ? Theme.backgroundHover : Theme.primaryPressed
    property color normalColor: flat ? "transparent" : Theme.primary
    property color iconColor: flat ? Theme.textSecondary : "white"
    property color iconHoverColor: iconColor

    signal clicked()

    implicitWidth: 36
    implicitHeight: 36
    radius: Theme.radiusSm
    color: mouseArea.pressed ? pressedColor : (mouseArea.containsMouse ? hoverColor : normalColor)

    Behavior on color {
        ColorAnimation { duration: Theme.animationFast }
    }

    Text {
        anchors.centerIn: parent
        text: root.icon
        font.pixelSize: Theme.fontSizeLg
        font.weight: Font.Bold
        color: mouseArea.containsMouse ? root.iconHoverColor : root.iconColor
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
