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

                Text {
                    text: "回声消除"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                XSwitch {
                    checked: settingsModel ? settingsModel.aecEnabled : false
                    onToggled: if (settingsModel) settingsModel.aecEnabled = checked
                }
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

            Text {
                Layout.fillWidth: true
                text: "配置文件仍在用户数据目录。点「选择」打开系统文件夹对话框；「默认」清空为系统默认。保存后下次启动会从旧目录复制到新路径。"
                font.pixelSize: Theme.fontSizeXs
                color: Theme.textSecondary
                wrapMode: Text.WordWrap
            }

            // 缓存
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingSm
                Text {
                    text: "缓存目录"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                TextField {
                    id: pathCacheField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.pathCacheDir : ""
                    onTextEdited: if (settingsModel) settingsModel.pathCacheDir = text
                    onEditingFinished: if (settingsModel) settingsModel.pathCacheDir = text
                    placeholderText: settingsModel ? settingsModel.pathDefaultCacheDir : ""
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: pathCacheField.activeFocus ? Theme.primary : "transparent"
                    }
                }
                Button {
                    text: "选择"
                    font.pixelSize: Theme.fontSizeSm
                    Layout.preferredWidth: 64
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
                        if (!settingsModel) return
                        var p = settingsModel.browseDirectory("cache")
                        if (p) pathCacheField.text = p
                    }
                }
                Button {
                    text: "默认"
                    font.pixelSize: Theme.fontSizeSm
                    Layout.preferredWidth: 64
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
                        if (!settingsModel) return
                        settingsModel.clearPathDir("cache")
                        pathCacheField.text = ""
                    }
                }
            }

            // 日志
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingSm
                Text {
                    text: "日志目录"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                TextField {
                    id: pathLogField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.pathLogDir : ""
                    onTextEdited: if (settingsModel) settingsModel.pathLogDir = text
                    onEditingFinished: if (settingsModel) settingsModel.pathLogDir = text
                    placeholderText: settingsModel ? settingsModel.pathDefaultLogDir : ""
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: pathLogField.activeFocus ? Theme.primary : "transparent"
                    }
                }
                Button {
                    text: "选择"
                    font.pixelSize: Theme.fontSizeSm
                    Layout.preferredWidth: 64
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
                        if (!settingsModel) return
                        var p = settingsModel.browseDirectory("log")
                        if (p) pathLogField.text = p
                    }
                }
                Button {
                    text: "默认"
                    font.pixelSize: Theme.fontSizeSm
                    Layout.preferredWidth: 64
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
                        if (!settingsModel) return
                        settingsModel.clearPathDir("log")
                        pathLogField.text = ""
                    }
                }
            }

            // 音乐
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingSm
                Text {
                    text: "音乐缓存"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                TextField {
                    id: pathMusicField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.pathMusicCacheDir : ""
                    onTextEdited: if (settingsModel) settingsModel.pathMusicCacheDir = text
                    onEditingFinished: if (settingsModel) settingsModel.pathMusicCacheDir = text
                    placeholderText: settingsModel ? settingsModel.pathDefaultMusicCacheDir : ""
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: pathMusicField.activeFocus ? Theme.primary : "transparent"
                    }
                }
                Button {
                    text: "选择"
                    font.pixelSize: Theme.fontSizeSm
                    Layout.preferredWidth: 64
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
                        if (!settingsModel) return
                        var p = settingsModel.browseDirectory("music")
                        if (p) pathMusicField.text = p
                    }
                }
                Button {
                    text: "默认"
                    font.pixelSize: Theme.fontSizeSm
                    Layout.preferredWidth: 64
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
                        if (!settingsModel) return
                        settingsModel.clearPathDir("music")
                        pathMusicField.text = ""
                    }
                }
            }

            // 唤醒词
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingSm
                Text {
                    text: "唤醒词目录"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                TextField {
                    id: pathKeywordsField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.pathKeywordsDir : ""
                    onTextEdited: if (settingsModel) settingsModel.pathKeywordsDir = text
                    onEditingFinished: if (settingsModel) settingsModel.pathKeywordsDir = text
                    placeholderText: settingsModel ? settingsModel.pathDefaultKeywordsDir : ""
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: pathKeywordsField.activeFocus ? Theme.primary : "transparent"
                    }
                }
                Button {
                    text: "选择"
                    font.pixelSize: Theme.fontSizeSm
                    Layout.preferredWidth: 64
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
                        if (!settingsModel) return
                        var p = settingsModel.browseDirectory("keywords")
                        if (p) pathKeywordsField.text = p
                    }
                }
                Button {
                    text: "默认"
                    font.pixelSize: Theme.fontSizeSm
                    Layout.preferredWidth: 64
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
                        if (!settingsModel) return
                        settingsModel.clearPathDir("keywords")
                        pathKeywordsField.text = ""
                    }
                }
            }

            // MCP 插件
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingSm
                Text {
                    text: "MCP 插件目录"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                }
                TextField {
                    id: pathMcpField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.pathMcpPluginsDir : ""
                    onTextEdited: if (settingsModel) settingsModel.pathMcpPluginsDir = text
                    onEditingFinished: if (settingsModel) settingsModel.pathMcpPluginsDir = text
                    placeholderText: settingsModel ? settingsModel.pathDefaultMcpPluginsDir : ""
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: pathMcpField.activeFocus ? Theme.primary : "transparent"
                    }
                }
                Button {
                    text: "选择"
                    font.pixelSize: Theme.fontSizeSm
                    Layout.preferredWidth: 64
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
                        if (!settingsModel) return
                        var p = settingsModel.browseDirectory("mcp")
                        if (p) pathMcpField.text = p
                    }
                }
                Button {
                    text: "默认"
                    font.pixelSize: Theme.fontSizeSm
                    Layout.preferredWidth: 64
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
                        if (!settingsModel) return
                        settingsModel.clearPathDir("mcp")
                        pathMcpField.text = ""
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                text: settingsModel ? settingsModel.pathHints : ""
                font.pixelSize: Theme.fontSizeXs
                color: Theme.textSecondary
                wrapMode: Text.WordWrap
            }
        }

        Item { Layout.fillHeight: true }
    }
}
