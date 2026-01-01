// 自定义标题栏
import QtQuick
import QtQuick.Layouts
import "../theme"

Rectangle {
    id: root

    height: Theme.titleBarHeight
    color: "transparent"

    property string title: ""
    property bool showMinimize: true
    property bool showClose: true

    signal minimizeClicked()
    signal closeClicked()

    // 拖拽区域
    MouseArea {
        id: dragArea
        anchors.fill: parent
        anchors.rightMargin: buttonRow.width + Theme.spacingMd

        property point startPos

        onPressed: (mouse) => {
            startPos = Qt.point(mouse.x, mouse.y)
        }

        onPositionChanged: (mouse) => {
            if (pressed) {
                let delta = Qt.point(mouse.x - startPos.x, mouse.y - startPos.y)
                let win = Window.window
                if (win) {
                    win.x += delta.x
                    win.y += delta.y
                }
            }
        }

        onDoubleClicked: {
            let win = Window.window
            if (win) {
                if (win.visibility === Window.Maximized) {
                    win.showNormal()
                } else {
                    win.showMaximized()
                }
            }
        }
    }

    // 标题文字
    Text {
        anchors.left: parent.left
        anchors.leftMargin: Theme.spacingLg
        anchors.verticalCenter: parent.verticalCenter
        text: root.title
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSizeMd
        font.weight: Font.Medium
        color: Theme.textPrimary
    }

    // 按钮区域
    Row {
        id: buttonRow
        anchors.right: parent.right
        anchors.rightMargin: Theme.spacingSm
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.spacingXs

        // 最小化按钮
        Rectangle {
            visible: root.showMinimize
            width: 32
            height: 32
            radius: Theme.radiusSm
            color: minimizeArea.containsMouse ? Theme.backgroundHover : "transparent"

            Text {
                anchors.centerIn: parent
                text: "−"
                font.pixelSize: Theme.fontSizeLg
                color: Theme.textSecondary
            }

            MouseArea {
                id: minimizeArea
                anchors.fill: parent
                hoverEnabled: true
                onClicked: root.minimizeClicked()
            }
        }

        // 关闭按钮
        Rectangle {
            visible: root.showClose
            width: 32
            height: 32
            radius: Theme.radiusSm
            color: closeArea.containsMouse ? (closeArea.pressed ? Theme.error : Theme.errorHover) : "transparent"

            Text {
                anchors.centerIn: parent
                text: "×"
                font.pixelSize: Theme.fontSizeXl
                font.weight: Font.Bold
                color: closeArea.containsMouse ? "white" : Theme.textSecondary
            }

            MouseArea {
                id: closeArea
                anchors.fill: parent
                hoverEnabled: true
                onClicked: root.closeClicked()
            }
        }
    }
}
