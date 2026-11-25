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
            text: i18n.s["settings.system.title"]
            font.pixelSize: Theme.fontSizeXl
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        // 界面与语言（免重启即时生效）
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: i18n.s["settings.system.appearance"]
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
                    text: i18n.s["settings.system.language"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
                }
                XComboBox {
                    id: languageCombo
                    Layout.preferredWidth: 200
                    textRole: "label"
                    model: i18n.languageOptions
                    currentIndex: {
                        var lang = settingsModel ? settingsModel.language : "auto"
                        var opts = i18n.languageOptions
                        for (var i = 0; i < opts.length; i++) {
                            if (opts[i].value === lang) return i
                        }
                        return 0
                    }
                    onActivated: function(index) {
                        var opts = i18n.languageOptions
                        if (settingsModel && index >= 0 && index < opts.length) {
                            settingsModel.language = opts[index].value
                        }
                    }
                    font.pixelSize: Theme.fontSizeSm
                }
            }

            Text {
                Layout.fillWidth: true
                text: i18n.s["settings.system.language_hint"]
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

        // 基本信息区域
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            // 区域标题
            Text {
                text: i18n.s["settings.system.basic_info"]
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
                    text: i18n.s["settings.system.client_id"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
                }
                TextField {
                    id: clientIdField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.clientId : ""
                    onEditingFinished: if (settingsModel) settingsModel.clientId = text
                    placeholderText: i18n.s["settings.system.auto_generated"]
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: clientIdField.activeFocus ? Theme.primary : "transparent"
                    }
                }

                Text {
                    text: i18n.s["settings.system.device_id"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
                }
                TextField {
                    id: deviceIdField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.deviceId : ""
                    onEditingFinished: if (settingsModel) settingsModel.deviceId = text
                    placeholderText: i18n.s["settings.system.auto_generated"]
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
                text: i18n.s["settings.system.aec"]
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
                    text: i18n.s["settings.system.aec_enable"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
                }
                XSwitch {
                    id: aecEnabledSwitch
                    checked: settingsModel ? settingsModel.aecEnabled : false
                    onToggled: if (settingsModel) settingsModel.aecEnabled = checked
                }

                Text {
                    text: i18n.s["settings.system.aec_reference_mode"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
                    opacity: aecEnabledSwitch.checked ? 1 : 0.45
                }
                XComboBox {
                    id: aecReferenceModeCombo
                    Layout.fillWidth: true
                    enabled: aecEnabledSwitch.checked
                    opacity: aecEnabledSwitch.checked ? 1 : 0.45
                    model: [
                        i18n.s["settings.system.aec_ref_self"],
                        i18n.s["settings.system.aec_ref_system"]
                    ]
                    currentIndex: (settingsModel && settingsModel.aecReferenceMode === "system") ? 1 : 0
                    onActivated: function(index) {
                        if (settingsModel) {
                            settingsModel.aecReferenceMode = (index === 1) ? "system" : "self"
                        }
                    }
                    font.pixelSize: Theme.fontSizeSm
                }

                Text {
                    text: i18n.s["settings.system.aec_media_parallel"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
                    opacity: aecEnabledSwitch.checked ? 1 : 0.45
                }
                XSwitch {
                    enabled: aecEnabledSwitch.checked
                    opacity: aecEnabledSwitch.checked ? 1 : 0.45
                    checked: settingsModel ? settingsModel.aecMediaParallel : true
                    onToggled: if (settingsModel) settingsModel.aecMediaParallel = checked
                }

                Text {
                    text: i18n.s["settings.system.aec_frame_delay"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
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
                    text: i18n.s["settings.system.aec_preprocess"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
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
                text: i18n.s["settings.system.aec_hint"]
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
                text: i18n.s["settings.system.network"]
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
                    text: i18n.s["settings.system.ws_url"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
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
                    text: i18n.s["settings.system.ws_token"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
                }
                XTextField {
                    id: wsTokenField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.websocketToken : ""
                    onEditingFinished: if (settingsModel) settingsModel.websocketToken = text
                    isPassword: true
                }

                Text {
                    text: i18n.s["settings.system.ota_url"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
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
                    text: i18n.s["settings.system.auth_url"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
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
                    text: i18n.s["settings.system.activation_version"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
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
                text: i18n.s["settings.system.mqtt"]
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
                    text: i18n.s["settings.system.mqtt_endpoint"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
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
                    text: i18n.s["settings.system.mqtt_client_id"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
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
                    text: i18n.s["settings.system.mqtt_username"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
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
                    text: i18n.s["settings.system.mqtt_password"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
                }
                XTextField {
                    id: mqttPasswordField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.mqttPassword : ""
                    onEditingFinished: if (settingsModel) settingsModel.mqttPassword = text
                    isPassword: true
                }

                Text {
                    text: i18n.s["settings.system.mqtt_pub_topic"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
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
                    text: i18n.s["settings.system.mqtt_sub_topic"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 130
                    wrapMode: Text.WordWrap
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

        // 数据目录
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: i18n.s["settings.system.data_dir"]
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
                    text: i18n.s["common.open_dir"]
                    font.pixelSize: Theme.fontSizeSm
                    Layout.preferredWidth: Math.max(88, openDirText.implicitWidth + 24)
                    Layout.preferredHeight: 32
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: parent.pressed ? Theme.backgroundHover : Theme.backgroundSecondary
                        border.width: 1
                        border.color: Theme.divider
                    }
                    contentItem: Text {
                        id: openDirText
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
                text: i18n.s["settings.system.data_dir_hint"]
                font.pixelSize: Theme.fontSizeXs
                color: Theme.textSecondary
                wrapMode: Text.WordWrap
            }
        }

        Item { Layout.fillHeight: true }
    }
}
