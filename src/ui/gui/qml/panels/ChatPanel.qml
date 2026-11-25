// 对话面板
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

Rectangle {
    id: root

    color: Theme.background

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingLg
        spacing: Theme.spacingMd

        // 对话
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Theme.radiusMd
            color: Theme.backgroundSecondary

            ScrollView {
                anchors.fill: parent
                anchors.margins: Theme.spacingMd

                Text {
                    width: parent.width
                    text: mainModel.ttsText || i18n.s["main.chat.waiting"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeMd
                    color: mainModel.ttsText ? Theme.textPrimary : Theme.textPlaceholder
                    wrapMode: Text.Wrap
                    lineHeight: 1.5
                }
            }
        }

        // 媒体状态 / 副标题
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: mainModel.mediaLine ? 48 : 0
            visible: mainModel.mediaLine && mainModel.mediaLine.length > 0
            radius: Theme.radiusMd
            color: Theme.backgroundSecondary

            Text {
                anchors.fill: parent
                anchors.margins: Theme.spacingSm
                text: mainModel.mediaLine || ""
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSm
                color: Theme.textPlaceholder
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
        }
    }
}
