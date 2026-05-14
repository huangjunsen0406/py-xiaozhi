// 唤醒词设置页
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
            text: "唤醒词设置"
            font.pixelSize: Theme.fontSizeXl
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        // 唤醒词设置
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: "唤醒词"
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            // 启用唤醒词
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingMd

                Text {
                    text: "启用唤醒词"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                }

                Item { Layout.fillWidth: true }

                XSwitch {
                    checked: settingsModel ? settingsModel.wakeWordEnabled : false
                    onToggled: if (settingsModel) settingsModel.wakeWordEnabled = checked
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: Theme.divider
            }

            // 唤醒词输入
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingMd

                Text {
                    text: "唤醒词"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 80
                }

                TextField {
                    id: wakeWordInput
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.wakeWord : ""
                    onTextChanged: if (settingsModel && text !== settingsModel.wakeWord) settingsModel.wakeWord = text
                    placeholderText: "输入唤醒词，如「小智」或「Hey Jarvis」"
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: wakeWordInput.activeFocus ? Theme.primary : "transparent"
                    }
                }

                // 语言标签
                Rectangle {
                    visible: settingsModel && settingsModel.wakeWord && settingsModel.wakeWord.length > 0
                    width: langLabel.width + 16
                    height: 24
                    radius: Theme.radiusSm
                    color: settingsModel && settingsModel.wakeWordLang === "zh" ? Theme.primaryLight : Theme.successLight

                    Text {
                        id: langLabel
                        anchors.centerIn: parent
                        text: settingsModel && settingsModel.wakeWordLang === "zh" ? "中文" : "English"
                        font.pixelSize: Theme.fontSizeXs
                        color: settingsModel && settingsModel.wakeWordLang === "zh" ? Theme.primary : Theme.success
                    }
                }
            }

            // 预览区域
            Rectangle {
                Layout.fillWidth: true
                height: previewLayout.height + 20
                color: Theme.backgroundSecondary
                radius: Theme.radiusSm
                visible: settingsModel && settingsModel.wakeWordPreview && settingsModel.wakeWordPreview.length > 0

                ColumnLayout {
                    id: previewLayout
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: Theme.spacingMd
                    spacing: 4

                    Text {
                        text: "转换预览"
                        font.pixelSize: Theme.fontSizeXs
                        color: Theme.textPlaceholder
                    }

                    Text {
                        Layout.fillWidth: true
                        text: settingsModel ? settingsModel.wakeWordPreview : ""
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.textPrimary
                        wrapMode: Text.WrapAnywhere
                    }
                }
            }

            // 保存按钮
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingMd

                Item { Layout.fillWidth: true }

                Button {
                    text: "保存唤醒词"
                    implicitHeight: 36
                    implicitWidth: 120

                    contentItem: Text {
                        text: parent.text
                        font.pixelSize: Theme.fontSizeSm
                        color: "white"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: parent.enabled ? (parent.pressed ? Theme.primaryPressed : (parent.hovered ? Theme.primaryHover : Theme.primary)) : Theme.textPlaceholder
                    }

                    enabled: settingsModel && settingsModel.wakeWord && settingsModel.wakeWord.length > 0
                    onClicked: if (settingsModel) settingsModel.saveWakeWord()
                }
            }
        }

        // 分隔线
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }

        // 检测参数
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: "检测参数"
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 3
                rowSpacing: Theme.spacingMd
                columnSpacing: Theme.spacingMd

                // 线程数
                Text {
                    text: "线程数"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 80
                }

                XSpinBox {
                    Layout.preferredWidth: 120
                    from: 1
                    to: 16
                    value: settingsModel ? settingsModel.numThreads : 4
                    onValueModified: if (settingsModel) settingsModel.numThreads = value
                    font.pixelSize: Theme.fontSizeSm
                }

                Text {
                    text: "建议设置为 CPU 核心数"
                    font.pixelSize: Theme.fontSizeXs
                    color: Theme.textPlaceholder
                }

                // 关键词得分
                Text {
                    text: "关键词得分"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 80
                }

                Slider {
                    id: scoreSlider
                    Layout.fillWidth: true
                    from: 0.5
                    to: 3.0
                    stepSize: 0.1
                    value: settingsModel ? settingsModel.keywordsScore : 1.0
                    onMoved: if (settingsModel) settingsModel.keywordsScore = value
                }

                Text {
                    text: scoreSlider.value.toFixed(1)
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textPrimary
                    Layout.preferredWidth: 40
                }

                // 关键词阈值
                Text {
                    text: "关键词阈值"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 80
                }

                Slider {
                    id: thresholdSlider
                    Layout.fillWidth: true
                    from: 0.0
                    to: 1.0
                    stepSize: 0.05
                    value: settingsModel ? settingsModel.keywordsThreshold : 0.5
                    onMoved: if (settingsModel) settingsModel.keywordsThreshold = value
                }

                Text {
                    text: thresholdSlider.value.toFixed(2)
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textPrimary
                    Layout.preferredWidth: 40
                }
            }
        }

        // 分隔线
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }

        // 提示信息
        Text {
            Layout.fillWidth: true
            text: "支持中文和英文唤醒词。中文会自动转换为拼音格式，英文使用 BPE 分词。得分越高越严格，阈值越低越敏感。"
            font.pixelSize: Theme.fontSizeSm
            color: Theme.textPlaceholder
            wrapMode: Text.WordWrap
        }

        Item { Layout.fillHeight: true }
    }
}
