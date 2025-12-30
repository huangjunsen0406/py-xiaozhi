// 自定义开关组件
import QtQuick
import QtQuick.Controls
import "../theme"

Switch {
    id: root

    // 尺寸
    property int trackWidth: 44
    property int trackHeight: 24
    property int thumbSize: trackHeight - 4

    implicitWidth: trackWidth + (text ? contentItem.implicitWidth + spacing : 0)
    implicitHeight: Math.max(trackHeight, contentItem.implicitHeight)

    indicator: Rectangle {
        implicitWidth: root.trackWidth
        implicitHeight: root.trackHeight
        x: root.leftPadding
        y: parent.height / 2 - height / 2
        radius: root.trackHeight / 2

        color: root.checked ? Theme.primary : Theme.border

        Behavior on color {
            ColorAnimation { duration: 200 }
        }

        // 滑块
        Rectangle {
            id: thumb
            width: root.thumbSize
            height: root.thumbSize
            radius: root.thumbSize / 2
            color: "white"

            x: root.checked ? parent.width - width - 2 : 2
            anchors.verticalCenter: parent.verticalCenter

            // hover/pressed 缩放效果
            scale: root.pressed ? 0.9 : (root.hovered ? 1.05 : 1)

            Behavior on x {
                NumberAnimation {
                    duration: 200
                    easing.type: Easing.OutBack
                    easing.overshoot: 1.2
                }
            }

            Behavior on scale {
                NumberAnimation {
                    duration: 100
                    easing.type: Easing.OutCubic
                }
            }

            // 轻微阴影
            Rectangle {
                z: -1
                anchors.centerIn: parent
                width: parent.width + 2
                height: parent.height + 2
                radius: width / 2
                color: "#15000000"
            }
        }
    }

    contentItem: Text {
        text: root.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSizeSm
        color: root.enabled ? Theme.textPrimary : Theme.textPlaceholder
        verticalAlignment: Text.AlignVCenter
        leftPadding: root.indicator.width + root.spacing
    }
}
