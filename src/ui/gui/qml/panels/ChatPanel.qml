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

        // TTS 文本显示区域
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
    }
}
