// 按钮组件
import QtQuick
import QtQuick.Controls
import "../theme"

Button {
    id: root

    property string variant: "primary"  // "primary", "secondary", "text"

    implicitWidth: Math.max(80, contentItem.implicitWidth + Theme.spacingLg * 2)
    implicitHeight: 36

    background: Rectangle {
        radius: Theme.radiusSm
        color: {
            if (!root.enabled) return Theme.backgroundSecondary
            if (root.variant === "text") return root.pressed ? Theme.backgroundHover : "transparent"
            if (root.variant === "secondary") return root.pressed ? Theme.backgroundHover : Theme.backgroundSecondary
            return root.pressed ? Theme.primaryPressed : (root.hovered ? Theme.primaryHover : Theme.primary)
        }
        border.width: root.variant === "secondary" ? 1 : 0
        border.color: Theme.border

        Behavior on color {
            ColorAnimation { duration: Theme.animationFast }
        }
    }

    contentItem: Text {
        text: root.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSizeMd
        color: {
            if (!root.enabled) return Theme.textPlaceholder
            if (root.variant === "primary") return "white"
            return Theme.textPrimary
        }
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
