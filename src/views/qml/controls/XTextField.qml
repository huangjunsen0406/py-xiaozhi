// 输入框
import QtQuick
import QtQuick.Controls
import "../theme"

TextField {
    id: root

    implicitWidth: 200
    implicitHeight: 36

    font.family: Theme.fontFamily
    font.pixelSize: Theme.fontSizeMd
    color: Theme.textPrimary
    placeholderTextColor: Theme.textPlaceholder

    background: Rectangle {
        radius: Theme.radiusSm
        color: Theme.background
        border.width: 1
        border.color: root.activeFocus ? Theme.primary : Theme.border

        Behavior on border.color {
            ColorAnimation { duration: Theme.animationFast }
        }
    }

    leftPadding: Theme.spacingMd
    rightPadding: Theme.spacingMd
}
