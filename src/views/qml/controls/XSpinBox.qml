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
        radius: Theme.radiusSm
        color: Theme.background
        border.width: 1
        border.color: root.activeFocus ? Theme.primary : Theme.border

        Behavior on border.color {
            ColorAnimation { duration: Theme.animationFast }
        }
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

        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            color: "transparent"
            z: -1
        }
    }

    // 减号按钮
    down.indicator: Rectangle {
        x: 0
        height: root.height
        width: 32
        radius: Theme.radiusSm
        color: root.down.pressed ? Theme.backgroundHover : (root.down.hovered ? Theme.backgroundSecondary : "transparent")

        // 左侧圆角遮罩
        Rectangle {
            anchors.right: parent.right
            width: Theme.radiusSm
            height: parent.height
            color: parent.color
        }

        Text {
            anchors.centerIn: parent
            text: "−"
            font.pixelSize: Theme.fontSizeLg
            font.weight: Font.Medium
            color: root.enabled ? Theme.textSecondary : Theme.textPlaceholder
        }

        // 右侧分隔线
        Rectangle {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: 1
            height: parent.height - 12
            color: Theme.divider
        }

        Behavior on color {
            ColorAnimation { duration: Theme.animationFast }
        }
    }

    // 加号按钮
    up.indicator: Rectangle {
        x: root.width - width
        height: root.height
        width: 32
        radius: Theme.radiusSm
        color: root.up.pressed ? Theme.backgroundHover : (root.up.hovered ? Theme.backgroundSecondary : "transparent")

        // 右侧圆角遮罩
        Rectangle {
            anchors.left: parent.left
            width: Theme.radiusSm
            height: parent.height
            color: parent.color
        }

        Text {
            anchors.centerIn: parent
            text: "+"
            font.pixelSize: Theme.fontSizeLg
            font.weight: Font.Medium
            color: root.enabled ? Theme.textSecondary : Theme.textPlaceholder
        }

        // 左侧分隔线
        Rectangle {
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: 1
            height: parent.height - 12
            color: Theme.divider
        }

        Behavior on color {
            ColorAnimation { duration: Theme.animationFast }
        }
    }
}
