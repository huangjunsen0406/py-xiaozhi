// 摄像头设置页
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../theme"
import "../../controls"

ScrollView {
    id: root
    clip: true

    // 测试状态
    property bool cameraTesting: false
    property string testResult: ""

    // 初始化时加载摄像头列表
    Component.onCompleted: {
        if (settingsModel) {
            cameraCombo.model = settingsModel.getCameras()
            // model 设置后重新同步 currentIndex
            cameraCombo.currentIndex = settingsModel.selectedCameraIndex
        }
    }

    Connections {
        target: settingsModel
        function onDevicesChanged() {
            if (settingsModel) {
                cameraCombo.model = settingsModel.getCameras()
                // model 设置后重新同步 currentIndex
                cameraCombo.currentIndex = settingsModel.selectedCameraIndex
            }
        }
        function onStatusMessage(message) {
            root.testResult = message
            if (message.startsWith("[成功]") || message.startsWith("[失败]") || message.startsWith("[错误]")) {
                root.cameraTesting = false
            }
        }
    }

    ColumnLayout {
        width: root.availableWidth
        spacing: Theme.spacingLg

        // 页面标题
        Text {
            text: "摄像头设置"
            font.pixelSize: Theme.fontSizeXl
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        // 设备选择
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: "设备选择"
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingMd

                Text {
                    text: "摄像头"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 80
                }

                XComboBox {
                    id: cameraCombo
                    Layout.fillWidth: true
                    currentIndex: settingsModel ? settingsModel.selectedCameraIndex : 0
                    onActivated: function(index) {
                        if (settingsModel) settingsModel.selectedCameraIndex = index
                    }
                    font.pixelSize: Theme.fontSizeSm
                }

                Button {
                    text: root.cameraTesting ? "测试中..." : "测试"
                    enabled: !root.cameraTesting
                    Layout.preferredWidth: 70
                    Layout.preferredHeight: 32

                    background: Rectangle {
                        color: parent.enabled ? (parent.pressed ? Theme.primaryPressed : (parent.hovered ? Theme.primaryHover : Theme.primary)) : Theme.textPlaceholder
                        radius: Theme.radiusSm
                    }

                    contentItem: Text {
                        text: parent.text
                        font.pixelSize: Theme.fontSizeSm
                        color: "white"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    onClicked: {
                        root.cameraTesting = true
                        root.testResult = ""
                        if (settingsModel) settingsModel.testCamera()
                    }
                }

                Button {
                    text: "刷新"
                    Layout.preferredWidth: 70
                    Layout.preferredHeight: 32

                    background: Rectangle {
                        color: parent.pressed ? Theme.divider : (parent.hovered ? Theme.backgroundSecondary : Theme.backgroundHover)
                        radius: Theme.radiusSm
                    }

                    contentItem: Text {
                        text: parent.text
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.textSecondary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    onClicked: if (settingsModel) settingsModel.refreshCameras()
                }
            }
        }

        // 分隔线
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }

        // 视频参数
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: "视频参数"
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
                    text: "分辨率"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 80
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacingSm

                    XSpinBox {
                        Layout.preferredWidth: 100
                        from: 320
                        to: 1920
                        stepSize: 160
                        value: settingsModel ? settingsModel.frameWidth : 640
                        onValueModified: if (settingsModel) settingsModel.frameWidth = value
                        font.pixelSize: Theme.fontSizeSm
                    }

                    Text {
                        text: "x"
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.textSecondary
                    }

                    XSpinBox {
                        Layout.preferredWidth: 100
                        from: 240
                        to: 1080
                        stepSize: 120
                        value: settingsModel ? settingsModel.frameHeight : 480
                        onValueModified: if (settingsModel) settingsModel.frameHeight = value
                        font.pixelSize: Theme.fontSizeSm
                    }
                }

                Text {
                    text: "帧率"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 80
                }

                RowLayout {
                    spacing: Theme.spacingSm

                    XSpinBox {
                        Layout.preferredWidth: 100
                        from: 10
                        to: 60
                        stepSize: 5
                        value: settingsModel ? settingsModel.fps : 30
                        onValueModified: if (settingsModel) settingsModel.fps = value
                    }

                    Text {
                        text: "FPS"
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.textSecondary
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

        // VL API 配置
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: "视觉语言模型 (VL API)"
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
                    text: "API 地址"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 80
                }
                TextField {
                    id: vlApiUrlField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.vlApiUrl : ""
                    onEditingFinished: if (settingsModel) settingsModel.vlApiUrl = text
                    placeholderText: "https://..."
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: vlApiUrlField.activeFocus ? Theme.primary : "transparent"
                    }
                }

                Text {
                    text: "API Key"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 80
                }
                XTextField {
                    id: vlApiKeyField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.vlApiKey : ""
                    onEditingFinished: if (settingsModel) settingsModel.vlApiKey = text
                    isPassword: true
                }

                Text {
                    text: "模型"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 80
                }
                TextField {
                    id: vlModelsField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.vlModels : ""
                    onEditingFinished: if (settingsModel) settingsModel.vlModels = text
                    placeholderText: "glm-4v-plus"
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: vlModelsField.activeFocus ? Theme.primary : "transparent"
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

        // 测试结果
        Rectangle {
            Layout.fillWidth: true
            height: 48
            color: root.testResult.startsWith("[成功]") ? Theme.successLight :
                   root.testResult.startsWith("[失败]") ? Theme.errorLight :
                   root.testResult.startsWith("[错误]") ? Theme.errorLight : Theme.backgroundSecondary
            border.color: root.testResult.startsWith("[成功]") ? Theme.successBorder :
                          root.testResult.startsWith("[失败]") ? Theme.errorBorder :
                          root.testResult.startsWith("[错误]") ? Theme.errorBorder : Theme.divider
            radius: Theme.radiusMd
            visible: root.testResult.length > 0 || root.cameraTesting

            RowLayout {
                anchors.fill: parent
                anchors.margins: Theme.spacingMd
                spacing: Theme.spacingSm

                BusyIndicator {
                    visible: root.cameraTesting
                    running: root.cameraTesting
                    Layout.preferredWidth: 24
                    Layout.preferredHeight: 24
                }

                Text {
                    Layout.fillWidth: true
                    text: root.cameraTesting ? "正在测试摄像头..." : root.testResult
                    font.pixelSize: Theme.fontSizeSm
                    color: root.testResult.startsWith("[成功]") ? Theme.success :
                           root.testResult.startsWith("[失败]") ? Theme.error :
                           root.testResult.startsWith("[错误]") ? Theme.error : Theme.textSecondary
                    elide: Text.ElideRight
                }
            }
        }

        // 提示信息
        Text {
            Layout.fillWidth: true
            text: "摄像头用于视觉识别功能。如需使用本地 VL 模型，请配置 API 地址和密钥。"
            font.pixelSize: Theme.fontSizeSm
            color: Theme.textPlaceholder
            wrapMode: Text.WordWrap
        }

        Item { Layout.fillHeight: true }
    }
}
