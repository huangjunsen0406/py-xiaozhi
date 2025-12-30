// 卡片容器
import QtQuick
import "../theme"

Rectangle {
    id: root

    property bool hoverable: false

    implicitWidth: 200
    implicitHeight: 100
    radius: Theme.radiusMd
    color: hoverable && mouseArea.containsMouse ? Theme.backgroundHover : Theme.backgroundSecondary
    antialiasing: true

    default property alias content: contentItem.data

    Behavior on color {
        ColorAnimation { duration: Theme.animationFast }
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: root.hoverable
    }

    Item {
        id: contentItem
        anchors.fill: parent
        anchors.margins: Theme.spacingMd
    }
}
