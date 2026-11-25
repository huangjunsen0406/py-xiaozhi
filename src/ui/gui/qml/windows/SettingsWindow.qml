// 设置窗口 - 参照旧 PyQt5 实现
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"
import "settings"

AppWindow {
    id: root

    width: 740
    height: 560
    minimumWidth: 640
    minimumHeight: 460
    title: i18n.s["settings.title"]
    visible: false
    onClosing: settingsModel.discard()

    // Tab 配置
    readonly property var tabConfig: [
        { key: "settings.tab.system", component: "SystemOptionsTab.qml" },
        { key: "settings.tab.mcp", component: "McpToolsTab.qml" },
        { key: "settings.tab.wake_word", component: "WakeWordTab.qml" },
        { key: "settings.tab.camera", component: "CameraTab.qml" },
        { key: "settings.tab.audio", component: "AudioDeviceTab.qml" },
        { key: "settings.tab.shortcuts", component: "ShortcutsTab.qml" }
    ]

    // 直接使用 ColumnLayout，不需要额外的 Rectangle 层
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

            // 自定义标题栏 - 平台自适应
            TitleBar {
                Layout.fillWidth: true
                title: i18n.s["settings.title"]
                showMaximize: true
                onMinimizeClicked: root.showMinimized()
                onMaximizeClicked: {
                    if (root.visibility === Window.FullScreen || root.visibility === Window.Maximized) {
                        root.showNormal()
                    } else {
                        root.showMaximized()
                    }
                }
                onCloseClicked: root.close()
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
                        Layout.preferredWidth: 168
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
                                            text: i18n.s[modelData.key]
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

                            // MCP 工具
                            McpToolsTab {}

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
                Layout.preferredHeight: Math.max(60, statusText.implicitHeight + 24)
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
                        property bool isError: false
                        font.pixelSize: Theme.fontSizeSm
                        color: isError ? Theme.error : Theme.textPlaceholder
                        wrapMode: Text.Wrap

                        Connections {
                            target: settingsModel
                            function onStatusReset() {
                                statusText.isError = false
                                statusText.text = ""
                                statusTimer.stop()
                            }
                            function onStatusMessage(msg) {
                                if (!statusText.isError) {
                                    statusText.text = msg
                                    statusTimer.restart()
                                }
                            }
                            function onErrorOccurred(msg) {
                                statusText.isError = true
                                statusText.text = msg
                                statusTimer.stop()
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
                        Layout.preferredWidth: Math.max(84, resetText.implicitWidth + 24)
                        Layout.preferredHeight: 34
                        text: i18n.s["common.reset"]

                        background: Rectangle {
                            color: resetBtn.pressed ? Theme.errorLight : (resetBtn.hovered ? Theme.errorLight : "transparent")
                            border.color: Theme.error
                            border.width: 1
                            radius: Theme.radiusSm
                        }

                        contentItem: Text {
                            id: resetText
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
                        Layout.preferredWidth: Math.max(84, cancelText.implicitWidth + 24)
                        Layout.preferredHeight: 34
                        text: i18n.s["common.cancel"]

                        background: Rectangle {
                            color: cancelBtn.pressed ? Theme.divider : (cancelBtn.hovered ? Theme.backgroundHover : Theme.backgroundSecondary)
                            radius: Theme.radiusSm
                            border.width: 1
                            border.color: Theme.border
                        }

                        contentItem: Text {
                            id: cancelText
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
                        Layout.preferredWidth: Math.max(84, saveText.implicitWidth + 24)
                        Layout.preferredHeight: 34
                        text: i18n.s["common.save"]

                        background: Rectangle {
                            color: saveBtn.pressed ? Theme.primaryPressed : (saveBtn.hovered ? Theme.primaryHover : Theme.primary)
                            radius: Theme.radiusSm
                        }

                        contentItem: Text {
                            id: saveText
                            text: saveBtn.text
                            font.pixelSize: Theme.fontSizeSm
                            color: "white"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        onClicked: {
                            // 先抢焦点，让当前 TextField 触发 editingFinished 写回模型
                            saveBtn.forceActiveFocus()
                            if (settingsModel.save()) {
                                root.close()
                            }
                        }
                    }
            }
        }
    }
}
