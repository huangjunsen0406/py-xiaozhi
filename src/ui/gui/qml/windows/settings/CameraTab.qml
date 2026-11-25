// 摄像头设置页
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../theme"
import "../../controls"

ScrollView {
    id: root
    clip: true

    // 测试状态: 0=无, 1=成功, -1=失败/错误
    property bool cameraTesting: false
    property string testResult: ""
    property int testState: 0

    // 进入摄像头页时再扫描（启动阶段不扫 OpenCV，避免冷启动卡顿）
    Component.onCompleted: {
        if (settingsModel) {
            var list = settingsModel.getCameras()
            if (list.length === 0) {
                settingsModel.refreshCameras()
            } else {
                cameraCombo.model = list
                cameraCombo.currentIndex = settingsModel.selectedCameraIndex
            }
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
        }
        function onTestComplete(type, success) {
            if (type === "camera") {
                root.cameraTesting = false
                root.testState = success ? 1 : -1
            }
        }
    }

    ColumnLayout {
        width: root.availableWidth
        spacing: Theme.spacingLg

        // 页面标题
        Text {
            text: i18n.s["settings.camera.title"]
            font.pixelSize: Theme.fontSizeXl
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        // 设备选择
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: i18n.s["settings.camera.device_select"]
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingMd

                Text {
                    text: i18n.s["settings.camera.camera"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                    wrapMode: Text.WordWrap
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
                    text: root.cameraTesting ? i18n.s["common.testing"] : i18n.s["common.test"]
                    enabled: !root.cameraTesting
                    Layout.preferredWidth: Math.max(76, camTestText.implicitWidth + 20)
                    Layout.preferredHeight: 32

                    background: Rectangle {
                        color: parent.enabled ? (parent.pressed ? Theme.primaryPressed : (parent.hovered ? Theme.primaryHover : Theme.primary)) : Theme.textPlaceholder
                        radius: Theme.radiusSm
                    }

                    contentItem: Text {
                        id: camTestText
                        text: parent.text
                        font.pixelSize: Theme.fontSizeSm
                        color: "white"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    onClicked: {
                        root.cameraTesting = true
                        root.testResult = ""
                        root.testState = 0
                        if (settingsModel) settingsModel.testCamera()
                    }
                }

                Button {
                    text: i18n.s["common.refresh"]
                    Layout.preferredWidth: Math.max(76, camRefreshText.implicitWidth + 20)
                    Layout.preferredHeight: 32

                    background: Rectangle {
                        color: parent.pressed ? Theme.divider : (parent.hovered ? Theme.backgroundSecondary : Theme.backgroundHover)
                        radius: Theme.radiusSm
                    }

                    contentItem: Text {
                        id: camRefreshText
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
                text: i18n.s["settings.camera.video_params"]
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
                    text: i18n.s["settings.camera.resolution"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                    wrapMode: Text.WordWrap
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
                text: i18n.s["settings.camera.vl_api"]
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
                    text: i18n.s["settings.camera.api_url"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                    wrapMode: Text.WordWrap
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
                    text: i18n.s["settings.camera.api_key"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                    wrapMode: Text.WordWrap
                }
                XTextField {
                    id: vlApiKeyField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.vlApiKey : ""
                    onEditingFinished: if (settingsModel) settingsModel.vlApiKey = text
                    isPassword: true
                }

                Text {
                    text: i18n.s["settings.camera.model"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 100
                    wrapMode: Text.WordWrap
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
            color: root.testState === 1 ? Theme.successLight :
                   root.testState === -1 ? Theme.errorLight : Theme.backgroundSecondary
            border.color: root.testState === 1 ? Theme.successBorder :
                          root.testState === -1 ? Theme.errorBorder : Theme.divider
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
                    text: root.cameraTesting ? i18n.s["settings.camera.testing_camera"] : root.testResult
                    font.pixelSize: Theme.fontSizeSm
                    color: root.testState === 1 ? Theme.success :
                           root.testState === -1 ? Theme.error : Theme.textSecondary
                    elide: Text.ElideRight
                }
            }
        }

        // 提示信息
        Text {
            Layout.fillWidth: true
            text: i18n.s["settings.camera.hint"]
            font.pixelSize: Theme.fontSizeSm
            color: Theme.textPlaceholder
            wrapMode: Text.WordWrap
        }

        Item { Layout.fillHeight: true }
    }
}
