// MCP 工具启用：分组 + 单工具开关（黑名单 MCP_TOOLS.DISABLED）
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

    function reloadCatalog() {
        if (!settingsModel) {
            catalog = []
            return
        }
        try {
            catalog = JSON.parse(settingsModel.mcpToolsCatalogJson || "[]")
        } catch (e) {
            catalog = []
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
        // 用数量，避免与按钮「全开/全关」文案重复
        return on + "/" + total
    }

    component GroupActionButton: Button {
        id: btn
        font.pixelSize: Theme.fontSizeXs
        Layout.preferredHeight: 28
        Layout.preferredWidth: 52
        padding: 0
        background: Rectangle {
            radius: Theme.radiusSm
            color: btn.pressed ? Theme.backgroundHover
                 : (btn.hovered ? Theme.backgroundSecondary : Theme.background)
            border.width: 1
            border.color: Theme.divider
        }
        contentItem: Text {
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
            text: "MCP 工具"
            font.pixelSize: Theme.fontSizeXl
            font.weight: Font.DemiBold
            color: Theme.textPrimary
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
                                            // 无文字时避免 contentItem 额外占位
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
