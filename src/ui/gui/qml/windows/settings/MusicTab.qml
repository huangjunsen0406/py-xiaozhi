// 音乐设置页
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

        Text {
            text: "音乐配置"
            font.pixelSize: Theme.fontSizeXl
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        // API 配置
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: "API 设置"
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
                    text: "搜索 API"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 120
                }
                TextField {
                    id: musicSearchUrlField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.musicSearchUrl : ""
                    onEditingFinished: if (settingsModel) settingsModel.musicSearchUrl = text
                    placeholderText: "留空使用默认酷我搜索 API"
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: musicSearchUrlField.activeFocus ? Theme.primary : "transparent"
                    }
                }

                Text {
                    text: "直链 API"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 120
                }
                TextField {
                    id: musicUrlApiField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.musicUrlApi : ""
                    onEditingFinished: if (settingsModel) settingsModel.musicUrlApi = text
                    placeholderText: "留空使用默认 lx-music-api"
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: musicUrlApiField.activeFocus ? Theme.primary : "transparent"
                    }
                }

                Text {
                    text: "API Key"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 120
                }
                TextField {
                    id: musicUrlApiKeyField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.musicUrlApiKey : ""
                    onEditingFinished: if (settingsModel) settingsModel.musicUrlApiKey = text
                    placeholderText: "留空使用默认 Key"
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: musicUrlApiKeyField.activeFocus ? Theme.primary : "transparent"
                    }
                }
            }

            Text {
                text: "搜索 API 使用酷我官方接口，直链 API 用于获取播放地址（需配合 API Key）"
                font.pixelSize: Theme.fontSizeXs
                color: Theme.textTertiary
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }

        // 播放偏好
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: "播放偏好"
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
                    text: "默认音质"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 120
                }
                XComboBox {
                    id: musicQualityCombo
                    Layout.preferredWidth: 150
                    model: ["128k", "320k"]
                    currentIndex: {
                        var q = settingsModel ? settingsModel.musicDefaultQuality : "320k"
                        var idx = ["128k", "320k"].indexOf(q)
                        return idx >= 0 ? idx : 1
                    }
                    onActivated: function(index) {
                        if (settingsModel) settingsModel.musicDefaultQuality = model[index]
                    }
                    font.pixelSize: Theme.fontSizeSm
                }
            }
        }

        Item { Layout.fillHeight: true }
    }
}
