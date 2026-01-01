// 设备激活窗口
import QtQuick
import QtQuick.Layouts
import "../theme"
import "../components"
import "../controls"

AppWindow {
    id: root

    width: 520
    height: 340
    minimumWidth: 450
    minimumHeight: 300
    title: "设备激活"
    visible: true

    // 信号
    signal activationCompleted(bool success)

    // 标题栏拖拽区域（避开右侧按钮区域）
    MouseArea {
        id: titleBarDragArea
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.rightMargin: 100  // 避开右侧按钮区域
        height: 50  // 标题栏高度

        property point startPos

        onPressed: (mouse) => {
            startPos = Qt.point(mouse.x, mouse.y)
        }

        onPositionChanged: (mouse) => {
            if (pressed) {
                let delta = Qt.point(mouse.x - startPos.x, mouse.y - startPos.y)
                root.x += delta.x
                root.y += delta.y
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingXl
        spacing: Theme.spacingLg

        // 标题栏
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingLg

            Text {
                text: "设备激活"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeXl
                font.weight: Font.Medium
                color: Theme.textPrimary
            }

            Item { Layout.fillWidth: true }

            // 状态指示器
            RowLayout {
                spacing: Theme.spacingSm

                Rectangle {
                    width: 8
                    height: 8
                    radius: 4
                    color: activationModel.statusColor

                    // 激活中时闪烁动画
                    SequentialAnimation on opacity {
                        running: activationModel.isActivating
                        loops: Animation.Infinite
                        NumberAnimation { to: 0.3; duration: 500 }
                        NumberAnimation { to: 1.0; duration: 500 }
                    }
                }

                Text {
                    text: activationModel.activationStatus
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                }
            }

            // 最小化按钮
            XIconButton {
                icon: "−"
                flat: true
                onClicked: root.showMinimized()
            }

            // 关闭按钮
            XIconButton {
                icon: "×"
                flat: true
                hoverColor: Theme.errorHover
                pressedColor: Theme.error
                iconHoverColor: "white"
                onClicked: root.close()
            }
        }

        // 设备信息卡片
        XCard {
            Layout.fillWidth: true
            Layout.preferredHeight: 90
            hoverable: true

            ColumnLayout {
                anchors.fill: parent
                spacing: Theme.spacingMd

                Text {
                    text: "设备信息"
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeMd
                    font.weight: Font.Medium
                    color: Theme.textSecondary
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: Theme.spacingXxl
                    rowSpacing: Theme.spacingXs

                    // 序列号
                    Text {
                        text: "设备序列号"
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.textPlaceholder
                    }

                    Text {
                        text: "MAC 地址"
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.textPlaceholder
                    }

                    Text {
                        text: activationModel.serialNumber
                        font.family: Theme.fontFamilyMono
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.textPrimary
                        elide: Text.ElideMiddle
                        Layout.maximumWidth: 200
                    }

                    Text {
                        text: activationModel.macAddress
                        font.family: Theme.fontFamilyMono
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.textPrimary
                    }
                }
            }
        }

        // 激活码卡片
        XCard {
            Layout.fillWidth: true
            Layout.preferredHeight: 70
            hoverable: true

            RowLayout {
                anchors.fill: parent
                spacing: Theme.spacingLg

                Text {
                    text: "激活验证码"
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeMd
                    font.weight: Font.Medium
                    color: Theme.textSecondary
                }

                // 验证码显示框
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 40
                    radius: Theme.radiusSm
                    color: Theme.background
                    border.width: 1
                    border.color: Theme.border

                    Text {
                        anchors.centerIn: parent
                        text: activationModel.activationCode
                        font.family: Theme.fontFamilyMono
                        font.pixelSize: Theme.fontSizeLg
                        font.weight: Font.Bold
                        font.letterSpacing: 4
                        color: activationModel.activationCode !== "------" ? Theme.error : Theme.textPlaceholder
                    }
                }

                // 复制按钮
                XButton {
                    text: "复制"
                    enabled: activationModel.activationCode !== "------"
                    onClicked: {
                        if (typeof activationController !== 'undefined') {
                            activationController.copyActivationCode()
                        }
                        copyToast.show()
                    }
                }
            }
        }

        // 操作按钮
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            XButton {
                Layout.fillWidth: true
                Layout.preferredHeight: 40
                text: "打开激活页面"
                enabled: !activationModel.isActivated
                onClicked: {
                    if (typeof activationController !== 'undefined') {
                        activationController.openActivationUrl()
                    }
                }
            }
        }

        // 提示信息
        Text {
            Layout.fillWidth: true
            text: activationModel.isActivated
                ? "设备已激活，窗口即将关闭..."
                : "请在激活页面输入验证码完成设备激活"
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSm
            color: Theme.textPlaceholder
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }

        Item { Layout.fillHeight: true }
    }

    // 复制成功提示
    Rectangle {
        id: copyToast
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Theme.spacingXl
        anchors.horizontalCenter: parent.horizontalCenter
        width: toastText.implicitWidth + Theme.spacingLg * 2
        height: 36
        radius: Theme.radiusMd
        color: Theme.success
        opacity: 0
        visible: opacity > 0

        function show() {
            opacity = 1
            hideTimer.restart()
        }

        Timer {
            id: hideTimer
            interval: 2000
            onTriggered: copyToast.opacity = 0
        }

        Behavior on opacity {
            NumberAnimation { duration: Theme.animationNormal }
        }

        Text {
            id: toastText
            anchors.centerIn: parent
            text: "验证码已复制"
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSm
            color: "white"
        }
    }
}
