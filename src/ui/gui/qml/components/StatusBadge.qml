// 状态徽章组件
import QtQuick
import "../theme"

Rectangle {
    id: root

    property string status: "offline"  // "online", "offline", "warning"
    property string text: ""

    implicitWidth: row.width + Theme.spacingMd * 2
    implicitHeight: 24
    radius: 12
    color: {
        switch (status) {
            case "online": return "#E8FFEA"
            case "warning": return "#FFF7E8"
            default: return "#FFECE8"
        }
    }

    Row {
        id: row
        anchors.centerIn: parent
        spacing: Theme.spacingXs

        Rectangle {
            width: 6
            height: 6
            radius: 3
            anchors.verticalCenter: parent.verticalCenter
            color: {
                switch (root.status) {
                    case "online": return Theme.success
                    case "warning": return Theme.warning
                    default: return Theme.error
                }
            }
        }

        Text {
            text: root.text
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeXs
            color: Theme.textSecondary
        }
    }
}
