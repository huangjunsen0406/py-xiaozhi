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
                    text: mainModel.ttsText || "等待对话..."
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeMd
                    color: mainModel.ttsText ? Theme.textPrimary : Theme.textPlaceholder
                    wrapMode: Text.Wrap
                    lineHeight: 1.5
                }
            }
        }

        // 音乐 / 歌词
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: mainModel.musicLine ? 48 : 0
            visible: mainModel.musicLine && mainModel.musicLine.length > 0
            radius: Theme.radiusMd
            color: Theme.backgroundSecondary

            Text {
                anchors.fill: parent
                anchors.margins: Theme.spacingSm
                text: mainModel.musicLine || ""
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
