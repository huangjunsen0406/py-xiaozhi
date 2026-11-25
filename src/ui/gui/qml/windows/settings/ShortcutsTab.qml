// 快捷键设置页
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
            text: i18n.s["settings.shortcuts.title"]
            font.pixelSize: Theme.fontSizeXl
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        // 基本设置
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: i18n.s["settings.shortcuts.basic"]
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingMd

                Text {
                    text: i18n.s["settings.shortcuts.enable_global"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                }

                Item { Layout.fillWidth: true }

                XSwitch {
                    checked: settingsModel ? settingsModel.shortcutsEnabled : false
                    onToggled: if (settingsModel) settingsModel.shortcutsEnabled = checked
                }
            }
        }

        // 分隔线
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }

        // 快捷键配置
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd
            opacity: settingsModel && settingsModel.shortcutsEnabled ? 1.0 : 0.5
            enabled: settingsModel ? settingsModel.shortcutsEnabled : false

            Text {
                text: i18n.s["settings.shortcuts.section"]
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            // 按住说话
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingMd

                Text {
                    text: i18n.s["settings.shortcuts.manual"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textPrimary
                    Layout.preferredWidth: 110
                    wrapMode: Text.WordWrap
                }

                XComboBox {
                    id: manualModCombo
                    Layout.preferredWidth: 100
                    model: ["Ctrl", "Alt", "Shift", "Cmd"]
                    currentIndex: {
                        var mod = settingsModel ? settingsModel.shortcutManualModifier : "ctrl"
                        if (mod === "alt") return 1
                        if (mod === "shift") return 2
                        if (mod === "cmd") return 3
                        return 0  // ctrl
                    }
                    onActivated: function(index) {
                        var options = ["ctrl", "alt", "shift", "cmd"]
                        if (settingsModel) settingsModel.shortcutManualModifier = options[index]
                    }
                }

                Text { text: "+"; font.pixelSize: Theme.fontSizeSm; color: Theme.textSecondary }

                TextField {
                    id: manualKeyField
                    Layout.preferredWidth: 50
                    text: settingsModel ? settingsModel.shortcutManualKey : ""
                    onEditingFinished: if (settingsModel) settingsModel.shortcutManualKey = text.toLowerCase()
                    maximumLength: 1
                    horizontalAlignment: Text.AlignHCenter
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: manualKeyField.activeFocus ? Theme.primary : "transparent"
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: i18n.s["settings.shortcuts.manual_desc"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textPlaceholder
                    wrapMode: Text.WordWrap
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.divider }

            // 自动对话
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingMd

                Text {
                    text: i18n.s["settings.shortcuts.auto"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textPrimary
                    Layout.preferredWidth: 110
                    wrapMode: Text.WordWrap
                }

                XComboBox {
                    id: autoModCombo
                    Layout.preferredWidth: 100
                    model: ["Ctrl", "Alt", "Shift", "Cmd"]
                    currentIndex: {
                        var mod = settingsModel ? settingsModel.shortcutAutoModifier : "ctrl"
                        if (mod === "alt") return 1
                        if (mod === "shift") return 2
                        if (mod === "cmd") return 3
                        return 0
                    }
                    onActivated: function(index) {
                        var options = ["ctrl", "alt", "shift", "cmd"]
                        if (settingsModel) settingsModel.shortcutAutoModifier = options[index]
                    }
                }

                Text { text: "+"; font.pixelSize: Theme.fontSizeSm; color: Theme.textSecondary }

                TextField {
                    id: autoKeyField
                    Layout.preferredWidth: 50
                    text: settingsModel ? settingsModel.shortcutAutoKey : ""
                    onEditingFinished: if (settingsModel) settingsModel.shortcutAutoKey = text.toLowerCase()
                    maximumLength: 1
                    horizontalAlignment: Text.AlignHCenter
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: autoKeyField.activeFocus ? Theme.primary : "transparent"
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: i18n.s["settings.shortcuts.auto_desc"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textPlaceholder
                    wrapMode: Text.WordWrap
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.divider }

            // 中断对话
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingMd

                Text {
                    text: i18n.s["settings.shortcuts.abort"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textPrimary
                    Layout.preferredWidth: 110
                    wrapMode: Text.WordWrap
                }

                XComboBox {
                    id: abortModCombo
                    Layout.preferredWidth: 100
                    model: ["Ctrl", "Alt", "Shift", "Cmd"]
                    currentIndex: {
                        var mod = settingsModel ? settingsModel.shortcutAbortModifier : "ctrl"
                        if (mod === "alt") return 1
                        if (mod === "shift") return 2
                        if (mod === "cmd") return 3
                        return 0
                    }
                    onActivated: function(index) {
                        var options = ["ctrl", "alt", "shift", "cmd"]
                        if (settingsModel) settingsModel.shortcutAbortModifier = options[index]
                    }
                }

                Text { text: "+"; font.pixelSize: Theme.fontSizeSm; color: Theme.textSecondary }

                TextField {
                    id: abortKeyField
                    Layout.preferredWidth: 50
                    text: settingsModel ? settingsModel.shortcutAbortKey : ""
                    onEditingFinished: if (settingsModel) settingsModel.shortcutAbortKey = text.toLowerCase()
                    maximumLength: 1
                    horizontalAlignment: Text.AlignHCenter
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: abortKeyField.activeFocus ? Theme.primary : "transparent"
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: i18n.s["settings.shortcuts.abort_desc"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textPlaceholder
                    wrapMode: Text.WordWrap
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.divider }

            // 切换模式
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingMd

                Text {
                    text: i18n.s["settings.shortcuts.mode"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textPrimary
                    Layout.preferredWidth: 110
                    wrapMode: Text.WordWrap
                }

                XComboBox {
                    id: modeModCombo
                    Layout.preferredWidth: 100
                    model: ["Ctrl", "Alt", "Shift", "Cmd"]
                    currentIndex: {
                        var mod = settingsModel ? settingsModel.shortcutModeModifier : "ctrl"
                        if (mod === "alt") return 1
                        if (mod === "shift") return 2
                        if (mod === "cmd") return 3
                        return 0
                    }
                    onActivated: function(index) {
                        var options = ["ctrl", "alt", "shift", "cmd"]
                        if (settingsModel) settingsModel.shortcutModeModifier = options[index]
                    }
                }

                Text { text: "+"; font.pixelSize: Theme.fontSizeSm; color: Theme.textSecondary }

                TextField {
                    id: modeKeyField
                    Layout.preferredWidth: 50
                    text: settingsModel ? settingsModel.shortcutModeKey : ""
                    onEditingFinished: if (settingsModel) settingsModel.shortcutModeKey = text.toLowerCase()
                    maximumLength: 1
                    horizontalAlignment: Text.AlignHCenter
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: modeKeyField.activeFocus ? Theme.primary : "transparent"
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: i18n.s["settings.shortcuts.mode_desc"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textPlaceholder
                    wrapMode: Text.WordWrap
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.divider }

            // 显示/隐藏窗口
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingMd

                Text {
                    text: i18n.s["settings.shortcuts.window"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textPrimary
                    Layout.preferredWidth: 110
                    wrapMode: Text.WordWrap
                }

                XComboBox {
                    id: windowModCombo
                    Layout.preferredWidth: 100
                    model: ["Ctrl", "Alt", "Shift", "Cmd"]
                    currentIndex: {
                        var mod = settingsModel ? settingsModel.shortcutWindowModifier : "ctrl"
                        if (mod === "alt") return 1
                        if (mod === "shift") return 2
                        if (mod === "cmd") return 3
                        return 0
                    }
                    onActivated: function(index) {
                        var options = ["ctrl", "alt", "shift", "cmd"]
                        if (settingsModel) settingsModel.shortcutWindowModifier = options[index]
                    }
                }

                Text { text: "+"; font.pixelSize: Theme.fontSizeSm; color: Theme.textSecondary }

                TextField {
                    id: windowKeyField
                    Layout.preferredWidth: 50
                    text: settingsModel ? settingsModel.shortcutWindowKey : ""
                    onEditingFinished: if (settingsModel) settingsModel.shortcutWindowKey = text.toLowerCase()
                    maximumLength: 1
                    horizontalAlignment: Text.AlignHCenter
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: windowKeyField.activeFocus ? Theme.primary : "transparent"
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: i18n.s["settings.shortcuts.window_desc"]
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textPlaceholder
                    wrapMode: Text.WordWrap
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
            text: i18n.s["settings.shortcuts.hint"]
            font.pixelSize: Theme.fontSizeSm
            color: Theme.textPlaceholder
            wrapMode: Text.WordWrap
        }

        Item { Layout.fillHeight: true }
    }
}
