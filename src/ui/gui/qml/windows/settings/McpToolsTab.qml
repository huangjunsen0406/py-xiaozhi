// MCP 工具与外挂插件管理：导入 ZIP/文件夹、卸载、应用内播放授权 + 分组开关
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../theme"
import "../../controls"

ScrollView {
    id: root
    clip: true
    // 给纵向滚动条留空，避免右侧开关被裁切
    rightPadding: 8
    contentWidth: availableWidth

    property var catalog: []
    property var installedPlugins: []

    function reloadCatalog() {
        if (!settingsModel) {
            catalog = []
            installedPlugins = []
            return
        }
        try {
            catalog = JSON.parse(settingsModel.mcpToolsCatalogJson || "[]")
        } catch (e) {
            catalog = []
        }
        try {
            installedPlugins = JSON.parse(settingsModel.mcpInstalledPluginsJson || "[]")
        } catch (e) {
            installedPlugins = []
        }
    }

    function groupsModel() {
        var map = ({})
        var order = []
        for (var i = 0; i < catalog.length; i++) {
            var row = catalog[i]
            var g = row.group || "other"
            if (!map[g]) {
                map[g] = {
                    group: g,
                    groupLabel: row.groupLabel || g,
                    tools: []
                }
                order.push(g)
            }
            map[g].tools.push(row)
        }
        var out = []
        for (var j = 0; j < order.length; j++)
            out.push(map[order[j]])
        return out
    }

    function groupEnabledCount(tools) {
        var n = 0
        for (var i = 0; i < tools.length; i++)
            if (tools[i].enabled)
                n++
        return n
    }

    function groupStatusText(tools) {
        var on = groupEnabledCount(tools)
        var total = tools.length
        return on + "/" + total
    }

    component GroupActionButton: Button {
        id: btn
        font.pixelSize: Theme.fontSizeXs
        Layout.preferredHeight: 28
        implicitWidth: Math.max(52, contentText.implicitWidth + 18)
        padding: 0
        background: Rectangle {
            radius: Theme.radiusSm
            color: btn.pressed ? Theme.backgroundHover
                 : (btn.hovered ? Theme.backgroundSecondary : Theme.background)
            border.width: 1
            border.color: Theme.divider
        }
        contentItem: Text {
            id: contentText
            text: btn.text
            font.pixelSize: Theme.fontSizeXs
            color: Theme.textSecondary
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    Component.onCompleted: reloadCatalog()

    Connections {
        target: settingsModel
        function onSettingsChanged() { root.reloadCatalog() }
    }

    ColumnLayout {
        width: root.availableWidth
        spacing: Theme.spacingLg

        Text {
            text: "MCP 工具与外挂插件"
            font.pixelSize: Theme.fontSizeXl
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        // 外挂插件管理卡片
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: pluginMgrCol.implicitHeight + Theme.spacingMd * 2
            radius: Theme.radiusMd
            color: Theme.backgroundSecondary
            border.width: 1
            border.color: Theme.divider

            ColumnLayout {
                id: pluginMgrCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: Theme.spacingMd
                spacing: Theme.spacingSm

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacingSm

                    Text {
                        text: "外挂插件 (" + root.installedPlugins.length + ")"
                        font.pixelSize: Theme.fontSizeMd
                        font.weight: Font.Medium
                        color: Theme.textPrimary
                    }

                    Item { Layout.fillWidth: true }

                    GroupActionButton {
                        text: "导入 ZIP"
                        onClicked: if (settingsModel) settingsModel.importMcpPluginZip()
                    }
                    GroupActionButton {
                        text: "导入文件夹"
                        onClicked: if (settingsModel) settingsModel.importMcpPluginDir()
                    }
                    GroupActionButton {
                        text: "打开目录"
                        onClicked: if (settingsModel) settingsModel.openMcpPluginsDir()
                    }
                    GroupActionButton {
                        text: "刷新"
                        onClicked: if (settingsModel) settingsModel.refreshMcpPlugins()
                    }
                }

                // 宿主能力授权开关
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacingMd

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            text: "允许外挂使用应用内播放"
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.textPrimary
                        }
                        Text {
                            text: "开启后，外挂可通过受控 media_player 播放音频，并启用宿主通用播控工具（暂停/停止/跳转）。保存后生效。"
                            font.pixelSize: Theme.fontSizeXs
                            color: Theme.textPlaceholder
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }

                    Item {
                        Layout.preferredWidth: 52
                        Layout.preferredHeight: 28
                        Layout.alignment: Qt.AlignVCenter

                        XSwitch {
                            anchors.centerIn: parent
                            text: ""
                            checked: settingsModel ? settingsModel.mcpAllowMediaPlayer : false
                            onToggled: if (settingsModel) settingsModel.mcpAllowMediaPlayer = checked
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: Theme.divider
                    visible: root.installedPlugins.length > 0
                }

                Text {
                    visible: root.installedPlugins.length === 0
                    text: "尚未安装外挂插件。可点击上方「导入 ZIP」或「导入文件夹」添加。"
                    font.pixelSize: Theme.fontSizeXs
                    color: Theme.textPlaceholder
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                Repeater {
                    model: root.installedPlugins

                    delegate: RowLayout {
                        id: pluginRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Theme.spacingSm

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: Theme.spacingXs

                                Text {
                                    text: pluginRow.modelData.name || pluginRow.modelData.id
                                    font.pixelSize: Theme.fontSizeSm
                                    font.weight: Font.Medium
                                    color: Theme.textPrimary
                                    elide: Text.ElideRight
                                }
                                Text {
                                    visible: !!(pluginRow.modelData.version)
                                    text: "v" + pluginRow.modelData.version
                                    font.pixelSize: Theme.fontSizeXs
                                    color: Theme.textPlaceholder
                                }
                                Text {
                                    text: "[" + (pluginRow.modelData.runtime || "inprocess") + "]"
                                    font.pixelSize: Theme.fontSizeXs
                                    color: Theme.textPlaceholder
                                }
                            }

                            Text {
                                visible: !!(pluginRow.modelData.error || pluginRow.modelData.description)
                                text: pluginRow.modelData.error ? ("错误: " + pluginRow.modelData.error) : (pluginRow.modelData.description || "")
                                font.pixelSize: Theme.fontSizeXs
                                color: pluginRow.modelData.error ? Theme.error : Theme.textSecondary
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }

                        GroupActionButton {
                            text: "卸载"
                            onClicked: {
                                if (settingsModel)
                                    settingsModel.uninstallMcpPlugin(pluginRow.modelData.id)
                            }
                        }
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: "控制哪些工具暴露给服务端。关闭后不出现在 tools/list，也无法调用。保存后若已连接将自动重连以更新列表。"
            font.pixelSize: Theme.fontSizeXs
            color: Theme.textSecondary
            wrapMode: Text.WordWrap
        }

        Repeater {
            model: root.groupsModel()

            delegate: ColumnLayout {
                id: groupBlock
                required property var modelData
                Layout.fillWidth: true
                spacing: Theme.spacingSm

                // 组头
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacingSm

                    Text {
                        text: groupBlock.modelData.groupLabel
                        font.pixelSize: Theme.fontSizeMd
                        font.weight: Font.Medium
                        color: Theme.textSecondary
                    }

                    Text {
                        text: root.groupStatusText(groupBlock.modelData.tools)
                        font.pixelSize: Theme.fontSizeXs
                        color: Theme.textPlaceholder
                    }

                    Item { Layout.fillWidth: true }

                    GroupActionButton {
                        text: "全开"
                        onClicked: {
                            if (settingsModel)
                                settingsModel.setMcpToolGroupEnabled(groupBlock.modelData.group, true)
                        }
                    }
                    GroupActionButton {
                        text: "全关"
                        onClicked: {
                            if (settingsModel)
                                settingsModel.setMcpToolGroupEnabled(groupBlock.modelData.group, false)
                        }
                    }
                }

                // 工具列表卡片
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: toolsCol.implicitHeight + Theme.spacingSm * 2
                    radius: Theme.radiusMd
                    color: Theme.backgroundSecondary
                    border.width: 1
                    border.color: Theme.divider

                    ColumnLayout {
                        id: toolsCol
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: Theme.spacingSm
                        spacing: 0

                        Repeater {
                            model: groupBlock.modelData.tools

                            delegate: ColumnLayout {
                                id: toolRow
                                required property var modelData
                                required property int index
                                Layout.fillWidth: true
                                spacing: 0

                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 48
                                    Layout.leftMargin: Theme.spacingSm
                                    Layout.rightMargin: Theme.spacingSm
                                    spacing: Theme.spacingMd

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2

                                        Text {
                                            text: toolRow.modelData.label || toolRow.modelData.name
                                            font.pixelSize: Theme.fontSizeSm
                                            color: Theme.textPrimary
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }
                                        Text {
                                            text: toolRow.modelData.name
                                            font.pixelSize: Theme.fontSizeXs
                                            color: Theme.textPlaceholder
                                            elide: Text.ElideMiddle
                                            Layout.fillWidth: true
                                        }
                                    }

                                    // 固定开关区域，避免被挤出/裁切
                                    Item {
                                        Layout.preferredWidth: 52
                                        Layout.preferredHeight: 28
                                        Layout.alignment: Qt.AlignVCenter

                                        XSwitch {
                                            anchors.centerIn: parent
                                            text: ""
                                            checked: toolRow.modelData.enabled
                                            onToggled: {
                                                if (settingsModel)
                                                    settingsModel.setMcpToolEnabled(
                                                        toolRow.modelData.name, checked)
                                            }
                                        }
                                    }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.leftMargin: Theme.spacingSm
                                    Layout.rightMargin: Theme.spacingSm
                                    height: 1
                                    color: Theme.divider
                                    visible: toolRow.index < groupBlock.modelData.tools.length - 1
                                }
                            }
                        }
                    }
                }
            }
        }

        Item { Layout.preferredHeight: Theme.spacingMd }
    }
}
