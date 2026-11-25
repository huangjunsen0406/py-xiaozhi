// 控制面板
import QtQuick
import QtQuick.Layouts
import "../theme"
import "../controls"

Rectangle {
    id: root

    color: Theme.backgroundSecondary

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingMd
        spacing: Theme.spacingMd

        // 输入区域
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingSm

            XTextField {
                id: inputField
                Layout.fillWidth: true
                placeholderText: i18n.s["main.input.message_placeholder"]

                Keys.onReturnPressed: sendText()
            }

            XButton {
                text: i18n.s["common.send"]
                onClicked: sendText()
            }
        }

        // 控制按钮区域
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            // 手动/自动模式切换
            XButton {
                Layout.fillWidth: true
                text: mainModel.autoMode ? i18n.s["main.mode.switch_to_manual"] : i18n.s["main.mode.switch_to_auto"]
                variant: "secondary"
                onClicked: eventBridge.onAutoToggle()
            }

            // 说话按钮（手动模式）
            XButton {
                Layout.fillWidth: true
                text: mainModel.buttonText
                visible: !mainModel.autoMode
                onPressed: eventBridge.onButtonPress()
                onReleased: eventBridge.onButtonRelease()
            }

            // 中断按钮
            XButton {
                Layout.preferredWidth: 80
                text: i18n.s["common.abort"]
                variant: "secondary"
                onClicked: eventBridge.onAbort()
            }
        }
    }

    function sendText() {
        let text = inputField.text.trim()
        if (text.length > 0) {
            eventBridge.onSendText(text)
            inputField.text = ""
        }
    }
}
