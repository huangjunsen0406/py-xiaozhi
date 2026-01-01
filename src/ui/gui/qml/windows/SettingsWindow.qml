// 设置窗口 - 参照旧 PyQt5 实现
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"
import "settings"

AppWindow {
    id: root

    width: 700
    height: 550
    minimumWidth: 600
    minimumHeight: 450
    title: "参数设置"
    visible: false

    // Tab 配置
    readonly property var tabConfig: [
        { name: "系统选项", component: "SystemOptionsTab.qml" },
        { name: "唤醒词", component: "WakeWordTab.qml" },
        { name: "摄像头", component: "CameraTab.qml" },
        { name: "音频设备", component: "AudioDeviceTab.qml" },
        { name: "快捷键", component: "ShortcutsTab.qml" }
    ]

    // 直接使用 ColumnLayout，不需要额外的 Rectangle 层
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

            // 自定义标题栏
            Rectangle {
                id: titleBar
                Layout.fillWidth: true
                Layout.preferredHeight: 44
                color: Theme.backgroundSecondary

                MouseArea {
                    anchors.fill: parent
                    property point startPos

                    onPressed: (mouse) => { startPos = Qt.point(mouse.x, mouse.y) }
                    onPositionChanged: (mouse) => {
                        if (pressed) {
                            root.x += mouse.x - startPos.x
                            root.y += mouse.y - startPos.y
                        }
                    }
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacingLg
                    anchors.rightMargin: Theme.spacingMd
                    spacing: Theme.spacingSm

                    Text {
                        text: "参数设置"
                        font.pixelSize: Theme.fontSizeLg
                        font.weight: Font.Bold
                        color: Theme.textPrimary
                    }

                    Item { Layout.fillWidth: true }

                    // 最小化按钮
                    Rectangle {
                        width: 28; height: 28; radius: Theme.radiusSm
                        color: btnMinMouse.pressed ? Theme.divider : (btnMinMouse.containsMouse ? Theme.backgroundHover : "transparent")

                        Text {
                            anchors.centerIn: parent
                            text: "–"
                            font.pixelSize: Theme.fontSizeLg
                            color: Theme.textSecondary
                        }

                        MouseArea {
                            id: btnMinMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: root.showMinimized()
                        }
                    }

                    // 最大化/还原按钮
                    Rectangle {
                        width: 28; height: 28; radius: Theme.radiusSm
                        color: btnMaxMouse.pressed ? Theme.divider : (btnMaxMouse.containsMouse ? Theme.backgroundHover : "transparent")

                        Text {
                            anchors.centerIn: parent
                            text: root.isMaximized ? "❐" : "□"
                            font.pixelSize: 14
                            color: Theme.textSecondary
                        }

                        MouseArea {
                            id: btnMaxMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: {
                                if (root.visibility === Window.FullScreen) {
                                    root.showNormal()
                                } else {
                                    root.showFullScreen()
                                }
                            }
                        }
                    }

                    // 关闭按钮
                    Rectangle {
                        width: 28; height: 28; radius: Theme.radiusSm
                        color: btnCloseMouse.pressed ? Theme.error : (btnCloseMouse.containsMouse ? Theme.errorHover : "transparent")

                        Text {
                            anchors.centerIn: parent
                            text: "×"
                            font.pixelSize: Theme.fontSizeLg
                            color: btnCloseMouse.containsMouse ? "white" : Theme.textPlaceholder
                        }

                        MouseArea {
                            id: btnCloseMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: root.close()
                        }
                    }
                }
            }

            // 内容区域
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: Theme.background

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 0
                    spacing: 0

                    // 左侧导航栏
                    Rectangle {
                        Layout.preferredWidth: 150
                        Layout.fillHeight: true
                        color: Theme.backgroundSecondary

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacingMd
                            spacing: Theme.spacingXs

                            Repeater {
                                model: tabConfig

                                delegate: Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 40
                                    radius: Theme.radiusMd
                                    color: tabBar.currentIndex === index ? Theme.primaryLight : (navMouse.containsMouse ? Theme.backgroundHover : "transparent")

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: Theme.spacingMd
                                        anchors.rightMargin: Theme.spacingMd
                                        spacing: Theme.spacingSm

                                        // 图标区域（可选）
                                        Rectangle {
                                            width: 4
                                            height: 20
                                            radius: 2
                                            color: tabBar.currentIndex === index ? Theme.primary : "transparent"
                                        }

                                        Text {
                                            Layout.fillWidth: true
                                            text: modelData.name
                                            font.pixelSize: Theme.fontSizeMd
                                            color: tabBar.currentIndex === index ? Theme.primary : Theme.textSecondary
                                            elide: Text.ElideRight
                                        }
                                    }

                                    MouseArea {
                                        id: navMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: tabBar.currentIndex = index
                                    }
                                }
                            }

                            Item { Layout.fillHeight: true }
                        }
                    }

                    // 分隔线
                    Rectangle {
                        Layout.preferredWidth: 1
                        Layout.fillHeight: true
                        color: Theme.border
                    }

                    // 右侧内容区
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: Theme.background

                        StackLayout {
                            id: tabBar
                            anchors.fill: parent
                            anchors.margins: Theme.spacingXl
                            currentIndex: 0

                            // 系统选项
                            SystemOptionsTab {}

                            // 唤醒词
                            WakeWordTab {}

                            // 摄像头
                            CameraTab {}

                            // 音频设备
                            AudioDeviceTab {}

                            // 快捷键
                            ShortcutsTab {}
                        }
                    }
                }
            }

            // 底部按钮栏
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 60
                color: Theme.backgroundSecondary

                // 顶部分隔线
                Rectangle {
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: 1
                    color: Theme.border
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacingXl
                    anchors.rightMargin: Theme.spacingXl
                    spacing: Theme.spacingMd

                    // 状态消息
                    Text {
                        id: statusText
                        Layout.fillWidth: true
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.textPlaceholder
                        elide: Text.ElideRight

                        Connections {
                            target: settingsModel
                            function onStatusMessage(msg) {
                                statusText.text = msg
                                statusTimer.restart()
                            }
                        }

                        Timer {
                            id: statusTimer
                            interval: 5000
                            onTriggered: statusText.text = ""
                        }
                    }

                    // 重置按钮
                    Button {
                        id: resetBtn
                        Layout.preferredWidth: 80
                        Layout.preferredHeight: 34
                        text: "重置"

                        background: Rectangle {
                            color: resetBtn.pressed ? Theme.errorLight : (resetBtn.hovered ? Theme.errorLight : "transparent")
                            border.color: Theme.error
                            border.width: 1
                            radius: Theme.radiusSm
                        }

                        contentItem: Text {
                            text: resetBtn.text
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.error
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        onClicked: {
                            settingsModel.reload()
                        }
                    }

                    // 取消按钮
                    Button {
                        id: cancelBtn
                        Layout.preferredWidth: 80
                        Layout.preferredHeight: 34
                        text: "取消"

                        background: Rectangle {
                            color: cancelBtn.pressed ? Theme.divider : (cancelBtn.hovered ? Theme.backgroundHover : Theme.backgroundSecondary)
                            radius: Theme.radiusSm
                            border.width: 1
                            border.color: Theme.border
                        }

                        contentItem: Text {
                            text: cancelBtn.text
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.textSecondary
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        onClicked: root.close()
                    }

                    // 保存按钮
                    Button {
                        id: saveBtn
                        Layout.preferredWidth: 80
                        Layout.preferredHeight: 34
                        text: "保存"

                        background: Rectangle {
                            color: saveBtn.pressed ? Theme.primaryPressed : (saveBtn.hovered ? Theme.primaryHover : Theme.primary)
                            radius: Theme.radiusSm
                        }

                        contentItem: Text {
                            text: saveBtn.text
                            font.pixelSize: Theme.fontSizeSm
                            color: "white"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        onClicked: {
                            settingsModel.save()
                            root.close()
                        }
                    }
            }
        }
    }
}
