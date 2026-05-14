// 主窗口 - 匹配原布局
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

AppWindow {
    id: root

    width: 420
    height: 520
    minimumWidth: 360
    minimumHeight: 420
    title: ""
    visible: true

    // 直接使用 ColumnLayout，不需要额外的 Rectangle 层
    // AppWindow 已经提供了带圆角的容器
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

            // 自定义标题栏 - 平台自适应
            TitleBar {
                Layout.fillWidth: true
                showMaximize: true
                onMinimizeClicked: root.showMinimized()
                onMaximizeClicked: {
                    if (root.visibility === Window.FullScreen || root.visibility === Window.Maximized) {
                        root.showNormal()
                    } else {
                        root.showMaximized()
                    }
                }
                onCloseClicked: {
                    if (eventBridge) eventBridge.onQuitRequest()
                }
            }

            // 状态卡片区域
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "transparent"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingMd
                    spacing: Theme.spacingMd

                    // 状态标签
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 40
                        color: Theme.primaryLight
                        radius: Theme.radiusMd

                        Text {
                            anchors.centerIn: parent
                            text: (mainModel && mainModel.statusText) ? mainModel.statusText : "待命"
                            font.pixelSize: Theme.fontSizeMd
                            font.weight: Font.Bold
                            color: Theme.primaryText
                        }
                    }

                    // 表情显示区域
                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: 80

                        property string currentEmotionUrl: (mainModel && mainModel.emotionUrl) ? mainModel.emotionUrl : ""

                        AnimatedImage {
                            anchors.centerIn: parent
                            width: Math.max(Math.min(parent.width, parent.height) * 0.7, 60)
                            height: width
                            source: parent.currentEmotionUrl
                            fillMode: Image.PreserveAspectFit
                            playing: true
                            visible: parent.currentEmotionUrl.length > 0 && parent.currentEmotionUrl.indexOf("file://") === 0
                        }

                        Text {
                            anchors.centerIn: parent
                            text: parent.currentEmotionUrl.indexOf("file://") !== 0 ? (parent.currentEmotionUrl || "😊") : ""
                            font.pixelSize: 80
                            visible: parent.currentEmotionUrl.indexOf("file://") !== 0
                        }
                    }

                    // TTS 文本显示区域
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 60
                        color: "transparent"

                        Text {
                            anchors.fill: parent
                            anchors.margins: 10
                            text: (mainModel && mainModel.ttsText) ? mainModel.ttsText : "待命"
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.textSecondary
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            wrapMode: Text.WordWrap
                        }
                    }
                }
            }

            // 按钮区域
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 72
                color: Theme.backgroundSecondary

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacingMd
                    anchors.rightMargin: Theme.spacingMd
                    anchors.bottomMargin: 10
                    spacing: Theme.spacingSm

                    // 手动模式按钮（点击切换录音）
                    Button {
                        id: manualBtn
                        Layout.preferredWidth: 100
                        Layout.fillWidth: true
                        Layout.maximumWidth: 140
                        Layout.preferredHeight: 38
                        text: (mainModel && mainModel.buttonText) ? mainModel.buttonText : "按住后说话"
                        visible: !(mainModel && mainModel.autoMode)

                        background: Rectangle {
                            color: manualBtn.pressed ? Theme.primaryPressed : (manualBtn.hovered ? Theme.primaryHover : Theme.primary)
                            radius: Theme.radiusMd
                        }

                        contentItem: Text {
                            text: manualBtn.text
                            font.pixelSize: Theme.fontSizeSm
                            color: "white"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        onClicked: if (eventBridge) eventBridge.onManualToggle()
                    }

                    // 自动模式按钮
                    Button {
                        id: autoBtn
                        Layout.preferredWidth: 100
                        Layout.fillWidth: true
                        Layout.maximumWidth: 140
                        Layout.preferredHeight: 38
                        text: (mainModel && mainModel.buttonText) ? mainModel.buttonText : "开始对话"
                        visible: mainModel && mainModel.autoMode

                        background: Rectangle {
                            color: autoBtn.pressed ? Theme.primaryPressed : (autoBtn.hovered ? Theme.primaryHover : Theme.primary)
                            radius: Theme.radiusMd
                        }

                        contentItem: Text {
                            text: autoBtn.text
                            font.pixelSize: Theme.fontSizeSm
                            color: "white"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        onClicked: if (eventBridge) eventBridge.onAutoStart()
                    }

                    // 打断对话
                    Button {
                        id: abortBtn
                        Layout.preferredWidth: 80
                        Layout.fillWidth: true
                        Layout.maximumWidth: 120
                        Layout.preferredHeight: 38
                        text: "打断对话"

                        background: Rectangle {
                            color: abortBtn.pressed ? Theme.divider : (abortBtn.hovered ? Theme.backgroundHover : Theme.backgroundSecondary)
                            radius: Theme.radiusMd
                            border.width: 1
                            border.color: Theme.border
                        }

                        contentItem: Text {
                            text: abortBtn.text
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.textPrimary
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        onClicked: if (eventBridge) eventBridge.onAbort()
                    }

                    // 输入 + 发送
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 120
                        Layout.preferredHeight: 38
                        spacing: Theme.spacingSm

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 38
                            color: Theme.background
                            radius: Theme.radiusMd
                            border.color: textInput.activeFocus ? Theme.primary : Theme.border
                            border.width: 1

                            TextInput {
                                id: textInput
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                verticalAlignment: TextInput.AlignVCenter
                                font.pixelSize: Theme.fontSizeSm
                                color: Theme.textPrimary
                                selectByMouse: true
                                clip: true

                                Text {
                                    anchors.fill: parent
                                    text: "输入文字..."
                                    font: textInput.font
                                    color: Theme.textPlaceholder
                                    verticalAlignment: Text.AlignVCenter
                                    visible: !textInput.text && !textInput.activeFocus
                                }

                                Keys.onReturnPressed: sendText()
                            }
                        }

                        Button {
                            id: sendBtn
                            Layout.preferredWidth: 60
                            Layout.maximumWidth: 84
                            Layout.preferredHeight: 38
                            text: "发送"

                            background: Rectangle {
                                color: sendBtn.pressed ? Theme.primaryPressed : (sendBtn.hovered ? Theme.primaryHover : Theme.primary)
                                radius: Theme.radiusMd
                            }

                            contentItem: Text {
                                text: sendBtn.text
                                font.pixelSize: Theme.fontSizeSm
                                color: "white"
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }

                            onClicked: sendText()
                        }
                    }

                    // 模式切换
                    Button {
                        id: modeBtn
                        Layout.preferredWidth: 80
                        Layout.fillWidth: true
                        Layout.maximumWidth: 120
                        Layout.preferredHeight: 38
                        text: (mainModel && mainModel.modeText) ? mainModel.modeText : "手动对话"

                        background: Rectangle {
                            color: modeBtn.pressed ? Theme.divider : (modeBtn.hovered ? Theme.backgroundHover : Theme.backgroundSecondary)
                            radius: Theme.radiusMd
                            border.width: 1
                            border.color: Theme.border
                        }

                        contentItem: Text {
                            text: modeBtn.text
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.textPrimary
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        onClicked: if (eventBridge) eventBridge.onAutoToggle()
                    }

                    // 参数设置
                    Button {
                        id: settingsBtn
                        Layout.preferredWidth: 80
                        Layout.fillWidth: true
                        Layout.maximumWidth: 120
                        Layout.preferredHeight: 38
                        text: "参数设置"

                        background: Rectangle {
                            color: settingsBtn.pressed ? Theme.divider : (settingsBtn.hovered ? Theme.backgroundHover : Theme.backgroundSecondary)
                            radius: Theme.radiusMd
                            border.width: 1
                            border.color: Theme.border
                        }

                        contentItem: Text {
                            text: settingsBtn.text
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.textPrimary
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        onClicked: if (eventBridge) eventBridge.onOpenSettings()
                    }
            }
        }
    }

    function sendText() {
        let text = textInput.text.trim()
        if (text.length > 0 && eventBridge) {
            eventBridge.onSendText(text)
            textInput.text = ""
        }
    }
}
