// 自定义标题栏 - 平台自适应
import QtQuick
import QtQuick.Layouts
import "../theme"

Rectangle {
    id: root

    height: Theme.titleBarHeight
    color: Theme.backgroundSecondary  // 添加背景色

    property string title: ""
    property bool showMinimize: true
    property bool showMaximize: false  // 默认不显示最大化
    property bool showClose: true

    signal minimizeClicked()
    signal maximizeClicked()
    signal closeClicked()

    // 拖拽区域
    MouseArea {
        id: dragArea
        anchors.fill: parent
        // macOS: 左边留空给按钮，Windows: 右边留空给按钮
        anchors.leftMargin: Theme.titleButtonsOnLeft ? (macButtons.width + Theme.spacingLg) : 0
        anchors.rightMargin: Theme.titleButtonsOnLeft ? 0 : (winButtons.width + Theme.spacingMd)

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
                // macOS: 双击进入全屏，Windows: 双击最大化
                if (Theme.titleButtonsOnLeft) {
                    if (win.visibility === Window.FullScreen) {
                        win.showNormal()
                    } else {
                        win.showFullScreen()
                    }
                } else {
                    if (win.visibility === Window.Maximized) {
                        win.showNormal()
                    } else {
                        win.showMaximized()
                    }
                }
            }
        }
    }

    // ========== macOS 风格按钮 (左侧) ==========
    MacTitleBarButtons {
        id: macButtons
        visible: Theme.titleButtonsOnLeft
        anchors.left: parent.left
        anchors.leftMargin: Theme.spacingMd
        anchors.verticalCenter: parent.verticalCenter
        showMaximize: root.showMaximize

        onCloseClicked: root.closeClicked()
        onMinimizeClicked: root.minimizeClicked()
        onMaximizeClicked: {
            // macOS: 绿色按钮进入全屏模式
            let win = Window.window
            if (win) {
                if (win.visibility === Window.FullScreen) {
                    win.showNormal()
                } else {
                    win.showFullScreen()
                }
            }
        }
    }

    // 标题文字 - macOS 时居中，Windows 时左对齐
    Text {
        anchors.centerIn: Theme.titleButtonsOnLeft ? parent : undefined
        anchors.left: Theme.titleButtonsOnLeft ? undefined : parent.left
        anchors.leftMargin: Theme.titleButtonsOnLeft ? 0 : Theme.spacingLg
        anchors.verticalCenter: Theme.titleButtonsOnLeft ? undefined : parent.verticalCenter
        text: root.title
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSizeMd
        font.weight: Font.Medium
        color: Theme.textPrimary
    }

    // ========== Windows/Linux 风格按钮 (右侧) ==========
    Row {
        id: winButtons
        visible: !Theme.titleButtonsOnLeft
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

        // 最大化按钮
        Rectangle {
            visible: root.showMaximize
            width: 32
            height: 32
            radius: Theme.radiusSm
            color: maximizeArea.containsMouse ? Theme.backgroundHover : "transparent"

            Text {
                anchors.centerIn: parent
                text: "□"
                font.pixelSize: Theme.fontSizeMd
                color: Theme.textSecondary
            }

            MouseArea {
                id: maximizeArea
                anchors.fill: parent
                hoverEnabled: true
                onClicked: root.maximizeClicked()
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
