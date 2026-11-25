// 音频设备设置页
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../theme"
import "../../controls"

ScrollView {
    id: root
    clip: true

    // 测试状态
    property bool inputTesting: false
    property bool outputTesting: false

    // 状态日志
    property var statusLogs: []

    function addLog(message) {
        var timestamp = new Date().toLocaleTimeString(Qt.locale(), "HH:mm:ss")
        statusLogs = [...statusLogs, "[" + timestamp + "] " + message]
        if (statusLogs.length > 20) {
            statusLogs = statusLogs.slice(-20)
        }
    }

    // 初始化时加载设备列表
    Component.onCompleted: {
        if (settingsModel) {
            inputCombo.model = settingsModel.getInputDevices()
            outputCombo.model = settingsModel.getOutputDevices()
            // model 设置后重新同步 currentIndex
            inputCombo.currentIndex = settingsModel.selectedInputIndex
            outputCombo.currentIndex = settingsModel.selectedOutputIndex
            addLog(i18n.tr("settings.audio.log_loaded"))
        }
    }

    Connections {
        target: settingsModel
        function onDevicesChanged() {
            if (settingsModel) {
                inputCombo.model = settingsModel.getInputDevices()
                outputCombo.model = settingsModel.getOutputDevices()
                // model 设置后重新同步 currentIndex
                inputCombo.currentIndex = settingsModel.selectedInputIndex
                outputCombo.currentIndex = settingsModel.selectedOutputIndex
                addLog(i18n.tr("settings.audio.log_refreshed"))
            }
        }
        function onTestComplete(type, success) {
            if (type === "input") {
                root.inputTesting = false
            } else if (type === "output") {
                root.outputTesting = false
            }
        }
        function onStatusMessage(message) {
            addLog(message)
        }
    }

    ColumnLayout {
        width: root.availableWidth
        spacing: Theme.spacingLg

        // 页面标题
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: i18n.s["settings.audio.title"]
                font.pixelSize: Theme.fontSizeXl
                font.weight: Font.DemiBold
                color: Theme.textPrimary
            }

            Item { Layout.fillWidth: true }

            Button {
                text: i18n.s["settings.audio.refresh_devices"]
                Layout.preferredHeight: 32
                Layout.preferredWidth: Math.max(92, refreshDevText.implicitWidth + 24)

                background: Rectangle {
                    color: parent.pressed ? Theme.divider : (parent.hovered ? Theme.backgroundSecondary : Theme.backgroundHover)
                    radius: Theme.radiusSm
                }

                contentItem: Text {
                    id: refreshDevText
                    text: parent.text
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                onClicked: if (settingsModel) settingsModel.refreshDevices()
            }
        }

        // 输入设备
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: i18n.s["settings.audio.input_section"]
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingMd

                XComboBox {
                    id: inputCombo
                    Layout.fillWidth: true
                    currentIndex: settingsModel ? settingsModel.selectedInputIndex : 0
                    onActivated: function(index) {
                        if (settingsModel) settingsModel.selectedInputIndex = index
                    }
                    font.pixelSize: Theme.fontSizeSm
                }

                Button {
                    text: root.inputTesting ? i18n.s["common.testing"] : i18n.s["common.test"]
                    enabled: !root.inputTesting
                    Layout.preferredWidth: Math.max(80, inTestText.implicitWidth + 20)
                    Layout.preferredHeight: 32

                    background: Rectangle {
                        color: parent.enabled ? (parent.pressed ? Theme.primaryPressed : (parent.hovered ? Theme.primaryHover : Theme.primary)) : Theme.textPlaceholder
                        radius: Theme.radiusSm
                    }

                    contentItem: Text {
                        id: inTestText
                        text: parent.text
                        font.pixelSize: Theme.fontSizeSm
                        color: "white"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    onClicked: {
                        root.inputTesting = true
                        if (settingsModel) settingsModel.testInputDevice()
                    }
                }
            }

            // 设备信息
            Rectangle {
                Layout.fillWidth: true
                height: 36
                color: Theme.backgroundSecondary
                radius: Theme.radiusSm

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: Theme.spacingMd
                    anchors.verticalCenter: parent.verticalCenter
                    text: (i18n.rev >= 0 && settingsModel) ? settingsModel.inputDeviceInfo : ""
                    font.pixelSize: Theme.fontSizeXs
                    color: Theme.textPlaceholder
                }
            }
        }

        // 分隔线
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }

        // 输出设备
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: i18n.s["settings.audio.output_section"]
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingMd

                XComboBox {
                    id: outputCombo
                    Layout.fillWidth: true
                    currentIndex: settingsModel ? settingsModel.selectedOutputIndex : 0
                    onActivated: function(index) {
                        if (settingsModel) settingsModel.selectedOutputIndex = index
                    }
                    font.pixelSize: Theme.fontSizeSm
                }

                Button {
                    text: root.outputTesting ? i18n.s["common.testing"] : i18n.s["common.test"]
                    enabled: !root.outputTesting
                    Layout.preferredWidth: Math.max(80, outTestText.implicitWidth + 20)
                    Layout.preferredHeight: 32

                    background: Rectangle {
                        color: parent.enabled ? (parent.pressed ? Theme.primaryPressed : (parent.hovered ? Theme.primaryHover : Theme.primary)) : Theme.textPlaceholder
                        radius: Theme.radiusSm
                    }

                    contentItem: Text {
                        id: outTestText
                        text: parent.text
                        font.pixelSize: Theme.fontSizeSm
                        color: "white"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    onClicked: {
                        root.outputTesting = true
                        if (settingsModel) settingsModel.testOutputDevice()
                    }
                }
            }

            // 设备信息
            Rectangle {
                Layout.fillWidth: true
                height: 36
                color: Theme.backgroundSecondary
                radius: Theme.radiusSm

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: Theme.spacingMd
                    anchors.verticalCenter: parent.verticalCenter
                    text: (i18n.rev >= 0 && settingsModel) ? settingsModel.outputDeviceInfo : ""
                    font.pixelSize: Theme.fontSizeXs
                    color: Theme.textPlaceholder
                }
            }
        }

        // 分隔线
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }

        // Opus 输出采样率
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: i18n.s["settings.audio.opus_rate"]
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingMd

                XComboBox {
                    id: sampleRateCombo
                    Layout.fillWidth: true
                    model: [i18n.s["settings.audio.opus_rate_24k"], i18n.s["settings.audio.opus_rate_16k"]]
                    currentIndex: settingsModel ? (settingsModel.opusOutputSampleRate === 24000 ? 0 : 1) : 0
                    onActivated: function(index) {
                        if (settingsModel) {
                            var rate = (index === 0) ? 24000 : 16000
                            settingsModel.opusOutputSampleRate = rate
                            addLog(i18n.fmt("settings.audio.log_rate_set", { rate: rate }))
                        }
                    }
                    font.pixelSize: Theme.fontSizeSm
                }
            }

            // 提示
            Rectangle {
                Layout.fillWidth: true
                height: 36
                color: Theme.backgroundSecondary
                radius: Theme.radiusSm

                Text {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: Theme.spacingMd
                    anchors.rightMargin: Theme.spacingMd
                    anchors.verticalCenter: parent.verticalCenter
                    text: i18n.s["settings.audio.opus_rate_hint"]
                    font.pixelSize: Theme.fontSizeXs
                    color: Theme.textPlaceholder
                    elide: Text.ElideRight
                }
            }
        }

        // 分隔线
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }

        // 音频帧长度
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: i18n.s["settings.audio.frame_duration"]
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingMd

                XComboBox {
                    id: frameDurationCombo
                    Layout.fillWidth: true
                    model: [i18n.s["settings.audio.frame_20"], i18n.s["settings.audio.frame_40"], i18n.s["settings.audio.frame_60"]]
                    currentIndex: {
                        if (!settingsModel) return 0
                        var duration = settingsModel.frameDuration
                        if (duration === 20) return 0
                        if (duration === 40) return 1
                        if (duration === 60) return 2
                        return 0
                    }
                    onActivated: function(index) {
                        if (settingsModel) {
                            var durations = [20, 40, 60]
                            settingsModel.frameDuration = durations[index]
                            addLog(i18n.fmt("settings.audio.log_frame_set", { ms: durations[index] }))
                        }
                    }
                    font.pixelSize: Theme.fontSizeSm
                }
            }

            // 提示
            Rectangle {
                Layout.fillWidth: true
                height: 36
                color: Theme.backgroundSecondary
                radius: Theme.radiusSm

                Text {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: Theme.spacingMd
                    anchors.rightMargin: Theme.spacingMd
                    anchors.verticalCenter: parent.verticalCenter
                    text: i18n.s["settings.audio.frame_hint"]
                    font.pixelSize: Theme.fontSizeXs
                    color: Theme.textPlaceholder
                    elide: Text.ElideRight
                }
            }
        }

        // 提示信息
        Text {
            Layout.fillWidth: true
            text: i18n.s["settings.audio.test_hint"]
            font.pixelSize: Theme.fontSizeSm
            color: Theme.textPlaceholder
            wrapMode: Text.WordWrap
        }

        // 分隔线
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }

        // 状态日志区域
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            RowLayout {
                Layout.fillWidth: true

                Text {
                    text: i18n.s["settings.audio.log_title"]
                    font.pixelSize: Theme.fontSizeMd
                    font.weight: Font.Medium
                    color: Theme.textSecondary
                }

                Item { Layout.fillWidth: true }

                Button {
                    text: i18n.s["settings.audio.clear_log"]
                    Layout.preferredHeight: 28
                    Layout.preferredWidth: Math.max(76, clearLogText.implicitWidth + 20)

                    background: Rectangle {
                        color: parent.pressed ? Theme.divider : (parent.hovered ? Theme.backgroundSecondary : Theme.backgroundHover)
                        radius: Theme.radiusSm
                    }

                    contentItem: Text {
                        id: clearLogText
                        text: parent.text
                        font.pixelSize: Theme.fontSizeXs
                        color: Theme.textSecondary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    onClicked: {
                        root.statusLogs = []
                        addLog(i18n.tr("settings.audio.log_cleared"))
                    }
                }
            }

            // 日志显示区域
            Rectangle {
                Layout.fillWidth: true
                height: 120
                color: Theme.textPrimary
                radius: Theme.radiusSm

                ScrollView {
                    id: logScrollView
                    anchors.fill: parent
                    anchors.margins: Theme.spacingSm
                    clip: true

                    TextArea {
                        id: logText
                        readOnly: true
                        text: root.statusLogs.join("\n")
                        color: Theme.success
                        font.pixelSize: Theme.fontSizeXs
                        wrapMode: Text.NoWrap
                        background: null
                        selectByMouse: true

                        onTextChanged: {
                            logScrollView.ScrollBar.vertical.position = 1.0 - logScrollView.ScrollBar.vertical.size
                        }
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }
    }
}
