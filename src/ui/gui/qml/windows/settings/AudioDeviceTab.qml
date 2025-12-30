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
            addLog("设备列表已加载")
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
                addLog("设备列表已刷新")
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
                text: "音频设备"
                font.pixelSize: Theme.fontSizeXl
                font.weight: Font.DemiBold
                color: Theme.textPrimary
            }

            Item { Layout.fillWidth: true }

            Button {
                text: "刷新设备"
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

                onClicked: if (settingsModel) settingsModel.refreshDevices()
            }
        }

        // 输入设备
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: "输入设备 (麦克风)"
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
                    text: root.inputTesting ? "测试中..." : "测试"
                    enabled: !root.inputTesting
                    Layout.preferredWidth: 80
                    Layout.preferredHeight: 32

                    background: Rectangle {
                        color: parent.enabled ? (parent.pressed ? "#0e42d2" : (parent.hovered ? "#4080ff" : Theme.primary)) : Theme.textPlaceholder
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
                    text: settingsModel ? settingsModel.inputDeviceInfo : ""
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
                text: "输出设备 (扬声器)"
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
                    text: root.outputTesting ? "测试中..." : "测试"
                    enabled: !root.outputTesting
                    Layout.preferredWidth: 80
                    Layout.preferredHeight: 32

                    background: Rectangle {
                        color: parent.enabled ? (parent.pressed ? "#0e42d2" : (parent.hovered ? "#4080ff" : Theme.primary)) : Theme.textPlaceholder
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
                    text: settingsModel ? settingsModel.outputDeviceInfo : ""
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
                text: "Opus 输出采样率"
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
                    model: ["24000 Hz (官方服务器)", "16000 Hz (第三方服务器)"]
                    currentIndex: settingsModel ? (settingsModel.opusOutputSampleRate === 24000 ? 0 : 1) : 0
                    onActivated: function(index) {
                        if (settingsModel) {
                            settingsModel.opusOutputSampleRate = (index === 0) ? 24000 : 16000
                            addLog("Opus 输出采样率已设置为 " + (index === 0 ? "24000" : "16000") + " Hz")
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
                    anchors.leftMargin: Theme.spacingMd
                    anchors.verticalCenter: parent.verticalCenter
                    text: "官方服务器使用 24kHz，第三方服务器通常使用 16kHz"
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

        // 音频帧长度
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: "音频帧长度"
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
                    model: ["20 ms (低延迟)", "40 ms (平衡)", "60 ms (低CPU)"]
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
                            addLog("音频帧长度已设置为 " + durations[index] + " ms")
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
                    anchors.leftMargin: Theme.spacingMd
                    anchors.verticalCenter: parent.verticalCenter
                    text: "20ms 低延迟高CPU，60ms 高延迟低CPU（适合树莓派）"
                    font.pixelSize: Theme.fontSizeXs
                    color: Theme.textPlaceholder
                }
            }
        }

        // 提示信息
        Text {
            Layout.fillWidth: true
            text: "点击测试按钮验证设备是否正常工作。输入测试会录制 3 秒音频，输出测试会播放 440Hz 测试音。"
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
                    text: "状态日志"
                    font.pixelSize: Theme.fontSizeMd
                    font.weight: Font.Medium
                    color: Theme.textSecondary
                }

                Item { Layout.fillWidth: true }

                Button {
                    text: "清除日志"
                    Layout.preferredHeight: 28

                    background: Rectangle {
                        color: parent.pressed ? Theme.divider : (parent.hovered ? Theme.backgroundSecondary : Theme.backgroundHover)
                        radius: Theme.radiusSm
                    }

                    contentItem: Text {
                        text: parent.text
                        font.pixelSize: Theme.fontSizeXs
                        color: Theme.textSecondary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    onClicked: {
                        root.statusLogs = []
                        addLog("日志已清除")
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
