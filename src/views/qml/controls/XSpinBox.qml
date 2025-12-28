// 自定义数值调节组件
import QtQuick
import QtQuick.Controls
import "../theme"

SpinBox {
    id: root

    implicitWidth: 120
    implicitHeight: 36

    editable: true

    // 背景
    background: Rectangle {
        radius: Theme.radiusMd
        color: Theme.background
        border.width: 1
        border.color: root.activeFocus ? Theme.primary : Theme.border
    }

    // 数值显示
    contentItem: TextInput {
        z: 2
        text: root.textFromValue(root.value, root.locale)
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSizeSm
        color: root.enabled ? Theme.textPrimary : Theme.textPlaceholder
        selectionColor: Theme.primary
        selectedTextColor: "white"
        horizontalAlignment: Qt.AlignHCenter
        verticalAlignment: Qt.AlignVCenter
        readOnly: !root.editable
        validator: root.validator
        inputMethodHints: Qt.ImhFormattedNumbersOnly
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 36
        anchors.rightMargin: 36
    }

    // 减号按钮
    down.indicator: Item {
        x: 0
        width: 36
        height: root.height

        Rectangle {
            anchors.fill: parent
            anchors.margins: 4
            anchors.rightMargin: 2
            radius: Theme.radiusSm
            color: root.down.pressed ? Theme.backgroundHover : (root.down.hovered ? Theme.backgroundSecondary : "transparent")
        }

        Text {
            anchors.centerIn: parent
            text: "−"
            font.pixelSize: 16
            font.weight: Font.Medium
            color: root.enabled ? Theme.textSecondary : Theme.textPlaceholder
        }
    }

    // 加号按钮
    up.indicator: Item {
        x: root.width - width
        width: 36
        height: root.height

        Rectangle {
            anchors.fill: parent
            anchors.margins: 4
            anchors.leftMargin: 2
            radius: Theme.radiusSm
            color: root.up.pressed ? Theme.backgroundHover : (root.up.hovered ? Theme.backgroundSecondary : "transparent")
        }

        Text {
            anchors.centerIn: parent
            text: "+"
            font.pixelSize: 16
            font.weight: Font.Medium
            color: root.enabled ? Theme.textSecondary : Theme.textPlaceholder
        }
    }
}
