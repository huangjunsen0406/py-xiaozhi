// 系统选项设置页
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../theme"
import "../../controls"

ScrollView {
    id: root
    clip: true

    ColumnLayout {
        width: root.availableWidth
        spacing: Theme.spacingLg

        // 页面标题
        Text {
            text: "系统选项"
            font.pixelSize: Theme.fontSizeXl
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        // 基本信息区域
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            // 区域标题
            Text {
                text: "基本信息"
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            // 表单项
            GridLayout {
                Layout.fillWidth: true
                columns: 2
                rowSpacing: Theme.spacingMd
                columnSpacing: Theme.spacingLg

                Text {
                    text: "客户端 ID"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                TextField {
                    id: clientIdField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.clientId : ""
                    onEditingFinished: if (settingsModel) settingsModel.clientId = text
                    placeholderText: "自动生成"
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: clientIdField.activeFocus ? Theme.primary : "transparent"
                    }
                }

                Text {
                    text: "设备 ID"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                TextField {
                    id: deviceIdField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.deviceId : ""
                    onEditingFinished: if (settingsModel) settingsModel.deviceId = text
                    placeholderText: "自动生成"
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: deviceIdField.activeFocus ? Theme.primary : "transparent"
                    }
                }

            }
        }

        // 分隔线
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }

        // 回声消除区域
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: "回声消除"
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                rowSpacing: Theme.spacingMd
                columnSpacing: Theme.spacingLg

                Text {
                    text: "启用"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                XSwitch {
                    id: aecEnabledSwitch
                    checked: settingsModel ? settingsModel.aecEnabled : false
                    onToggled: if (settingsModel) settingsModel.aecEnabled = checked
                }

                Text {
                    text: "媒体并行播放"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                    opacity: aecEnabledSwitch.checked ? 1 : 0.45
                }
                XSwitch {
                    enabled: aecEnabledSwitch.checked
                    opacity: aecEnabledSwitch.checked ? 1 : 0.45
                    checked: settingsModel ? settingsModel.aecMediaParallel : true
                    onToggled: if (settingsModel) settingsModel.aecMediaParallel = checked
                }

                Text {
                    text: "延迟补偿帧数"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                    opacity: aecEnabledSwitch.checked ? 1 : 0.45
                }
                XSpinBox {
                    Layout.preferredWidth: 120
                    enabled: aecEnabledSwitch.checked
                    opacity: aecEnabledSwitch.checked ? 1 : 0.45
                    from: 0
                    to: 20
                    value: settingsModel ? settingsModel.aecFrameDelay : 3
                    onValueModified: if (settingsModel) settingsModel.aecFrameDelay = value
                    font.pixelSize: Theme.fontSizeSm
                }

                Text {
                    text: "噪声抑制预处理"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                    opacity: aecEnabledSwitch.checked ? 1 : 0.45
                }
                XSwitch {
                    enabled: aecEnabledSwitch.checked
                    opacity: aecEnabledSwitch.checked ? 1 : 0.45
                    checked: settingsModel ? settingsModel.aecEnablePreprocess : true
                    onToggled: if (settingsModel) settingsModel.aecEnablePreprocess = checked
                }
            }

            Text {
                Layout.fillWidth: true
                text: "消除本应用 TTS/音乐的回声，启用后进入实时对话模式；音乐并行=TTS 播放时音乐闪避不暂停；延迟补偿=40ms+N×协议帧长，蓝牙设备可适当调大。修改后重启生效。"
                font.pixelSize: Theme.fontSizeXs
                color: Theme.textSecondary
                wrapMode: Text.WordWrap
            }
        }

        // 分隔线
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }

        // 网络配置区域
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: "网络配置"
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                rowSpacing: Theme.spacingMd
                columnSpacing: Theme.spacingLg

                Text {
                    text: "WebSocket URL"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                TextField {
                    id: wsUrlField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.websocketUrl : ""
                    onEditingFinished: if (settingsModel) settingsModel.websocketUrl = text
                    placeholderText: "wss://..."
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: wsUrlField.activeFocus ? Theme.primary : "transparent"
                    }
                }

                Text {
                    text: "访问令牌"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                XTextField {
                    id: wsTokenField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.websocketToken : ""
                    onEditingFinished: if (settingsModel) settingsModel.websocketToken = text
                    isPassword: true
                }

                Text {
                    text: "OTA 版本 URL"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                TextField {
                    id: otaUrlField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.otaUrl : ""
                    onEditingFinished: if (settingsModel) settingsModel.otaUrl = text
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: otaUrlField.activeFocus ? Theme.primary : "transparent"
                    }
                }

                Text {
                    text: "授权 URL"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                TextField {
                    id: authUrlField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.authorizationUrl : ""
                    onEditingFinished: if (settingsModel) settingsModel.authorizationUrl = text
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: authUrlField.activeFocus ? Theme.primary : "transparent"
                    }
                }

                Text {
                    text: "激活版本"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                XComboBox {
                    id: activationCombo
                    Layout.preferredWidth: 120
                    model: ["v1", "v2"]
                    currentIndex: settingsModel && settingsModel.activationVersion === "v2" ? 1 : 0
                    onActivated: function(index) {
                        if (settingsModel) settingsModel.activationVersion = index === 1 ? "v2" : "v1"
                    }
                    font.pixelSize: Theme.fontSizeSm
                }
            }
        }

        // 分隔线
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }

        // MQTT 配置区域
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: "MQTT 配置"
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                rowSpacing: Theme.spacingMd
                columnSpacing: Theme.spacingLg

                Text {
                    text: "服务端点"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                TextField {
                    id: mqttEndpointField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.mqttEndpoint : ""
                    onEditingFinished: if (settingsModel) settingsModel.mqttEndpoint = text
                    placeholderText: "mqtt.example.com"
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: mqttEndpointField.activeFocus ? Theme.primary : "transparent"
                    }
                }

                Text {
                    text: "客户端 ID"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                TextField {
                    id: mqttClientIdField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.mqttClientId : ""
                    onEditingFinished: if (settingsModel) settingsModel.mqttClientId = text
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: mqttClientIdField.activeFocus ? Theme.primary : "transparent"
                    }
                }

                Text {
                    text: "用户名"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                TextField {
                    id: mqttUsernameField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.mqttUsername : ""
                    onEditingFinished: if (settingsModel) settingsModel.mqttUsername = text
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: mqttUsernameField.activeFocus ? Theme.primary : "transparent"
                    }
                }

                Text {
                    text: "密码"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                XTextField {
                    id: mqttPasswordField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.mqttPassword : ""
                    onEditingFinished: if (settingsModel) settingsModel.mqttPassword = text
                    isPassword: true
                }

                Text {
                    text: "发布主题"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                TextField {
                    id: mqttPubField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.mqttPublishTopic : ""
                    onEditingFinished: if (settingsModel) settingsModel.mqttPublishTopic = text
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: mqttPubField.activeFocus ? Theme.primary : "transparent"
                    }
                }

                Text {
                    text: "订阅主题"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                TextField {
                    id: mqttSubField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.mqttSubscribeTopic : ""
                    onEditingFinished: if (settingsModel) settingsModel.mqttSubscribeTopic = text
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: mqttSubField.activeFocus ? Theme.primary : "transparent"
                    }
                }
            }
        }

        // 分隔线
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }

        // 可写目录（缓存 / 日志 / 音乐等）
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: "数据目录"
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingSm

                TextField {
                    Layout.fillWidth: true
                    readOnly: true
                    text: settingsModel ? settingsModel.userDataDir : ""
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.width: 1
                        border.color: Theme.divider
                    }
                }

                Button {
                    text: "打开目录"
                    font.pixelSize: Theme.fontSizeSm
                    Layout.preferredWidth: 84
                    Layout.preferredHeight: 32
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: parent.pressed ? Theme.backgroundHover : Theme.backgroundSecondary
                        border.width: 1
                        border.color: Theme.divider
                    }
                    contentItem: Text {
                        text: parent.text
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.textPrimary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        if (settingsModel) settingsModel.openUserDataDir()
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                text: "配置、日志、唤醒词与外挂插件均存放在此目录；如需整体迁移，可在启动前设置环境变量 XIAOZHI_DATA_DIR。"
                font.pixelSize: Theme.fontSizeXs
                color: Theme.textSecondary
                wrapMode: Text.WordWrap
            }
        }

        Item { Layout.fillHeight: true }
    }
}
