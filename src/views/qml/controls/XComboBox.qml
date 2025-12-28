// 自定义下拉框组件
import QtQuick
import QtQuick.Controls
import "../theme"

ComboBox {
    id: root

    implicitWidth: 200
    implicitHeight: 36

    // 背景
    background: Rectangle {
        radius: Theme.radiusSm
        color: root.enabled ? Theme.background : Theme.backgroundSecondary
        border.width: 1
        border.color: root.pressed || root.popup.visible ? Theme.primary : (root.hovered ? Theme.primary : Theme.border)

        Behavior on border.color {
            ColorAnimation { duration: Theme.animationFast }
        }
    }

    // 显示内容
    contentItem: Text {
        leftPadding: Theme.spacingMd
        rightPadding: root.indicator.width + Theme.spacingMd
        text: root.displayText
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSizeSm
        color: root.enabled ? Theme.textPrimary : Theme.textPlaceholder
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    // 下拉箭头
    indicator: Item {
        x: root.width - width - Theme.spacingSm
        y: (root.height - height) / 2
        width: 24
        height: 24

        Text {
            anchors.centerIn: parent
            text: root.popup.visible ? "▲" : "▼"
            font.pixelSize: 8
            color: Theme.textSecondary
        }
    }

    // 弹出菜单
    popup: Popup {
        y: root.height + 4
        width: root.width
        implicitHeight: contentItem.implicitHeight + 8
        padding: 4

        background: Rectangle {
            color: Theme.background
            radius: Theme.radiusSm
            border.width: 1
            border.color: Theme.border

            // 阴影效果
            layer.enabled: true
            layer.effect: Item {
                Rectangle {
                    anchors.fill: parent
                    anchors.margins: -4
                    color: "transparent"
                    radius: Theme.radiusSm + 4
                }
            }
        }

        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: root.popup.visible ? root.delegateModel : null
            currentIndex: root.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }
    }

    // 列表项
    delegate: ItemDelegate {
        width: root.width - 8
        height: 32

        background: Rectangle {
            radius: Theme.radiusSm - 2
            color: {
                if (pressed) return Theme.primaryPressed
                if (hovered || highlighted) return Theme.backgroundHover
                return "transparent"
            }

            Behavior on color {
                ColorAnimation { duration: Theme.animationFast }
            }
        }

        contentItem: Text {
            leftPadding: Theme.spacingSm
            text: root.textRole ? (modelData[root.textRole] ?? modelData) : modelData
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSm
            color: root.currentIndex === index ? Theme.primary : Theme.textPrimary
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }

        highlighted: root.highlightedIndex === index
    }
}
