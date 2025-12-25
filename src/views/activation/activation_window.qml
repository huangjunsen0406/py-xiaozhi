import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtGraphicalEffects 1.15

Rectangle {
    id: root
    width: 520
    height: 420
    color: "transparent"

    // 屏幕尺寸模式: "normal", "small", "compact"
    property string screenMode: "normal"

    // 根据屏幕模式计算尺寸
    readonly property int baseFontSize: screenMode === "compact" ? 10 : (screenMode === "small" ? 11 : 12)
    readonly property int titleFontSize: screenMode === "compact" ? 16 : (screenMode === "small" ? 18 : 20)
    readonly property int cardHeight: screenMode === "compact" ? 60 : (screenMode === "small" ? 70 : 80)
    readonly property int codeCardHeight: screenMode === "compact" ? 48 : (screenMode === "small" ? 56 : 64)
    readonly property int buttonHeight: screenMode === "compact" ? 28 : (screenMode === "small" ? 32 : 36)
    readonly property int margins: screenMode === "compact" ? 12 : (screenMode === "small" ? 16 : 20)
    readonly property int spacing: screenMode === "compact" ? 12 : (screenMode === "small" ? 16 : 20)

    // 信号定义
    signal copyCodeClicked()
    signal retryClicked()
    signal closeClicked()

    Rectangle {
        id: mainContainer
        anchors.fill: parent
        anchors.margins: 8
        color: "#ffffff"
        radius: 10
        border.width: 0
        antialiasing: true

        layer.enabled: true
        layer.effect: DropShadow {
            horizontalOffset: 0
            verticalOffset: 2
            radius: 10
            samples: 16
            color: "#15000000"
            transparentBorder: true
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: root.margins
            spacing: root.spacing

            // 标题区域
            RowLayout {
                Layout.fillWidth: true
                spacing: 16

                Text {
                    text: "设备激活"
                    font.family: "PingFang SC, Microsoft YaHei UI, Helvetica Neue"
                    font.pixelSize: root.titleFontSize
                    font.weight: Font.Medium
                    color: "#1d2129"
                }

                Item { Layout.fillWidth: true }

                // 激活状态
                RowLayout {
                    spacing: 8

                    Rectangle {
                        width: 6
                        height: 6
                        radius: 3
                        color: activationModel ? getStatusColor() : "#f53f3f"

                        function getStatusColor() {
                            var status = activationModel.activationStatus
                            if (status === "已激活") return "#00b42a"
                            if (status === "激活中...") return "#ff7d00"
                            if (status.includes("不一致")) return "#f53f3f"
                            return "#f53f3f"
                        }
                    }

                    Text {
                        text: activationModel ? activationModel.activationStatus : "未激活"
                        font.family: "PingFang SC, Microsoft YaHei UI"
                        font.pixelSize: root.baseFontSize
                        color: "#4e5969"
                    }
                }

                // 关闭按钮
                Button {
                    id: windowCloseBtn
                    width: root.buttonHeight
                    height: root.buttonHeight

                    background: Rectangle {
                        color: windowCloseBtn.pressed ? "#f53f3f" :
                               windowCloseBtn.hovered ? "#ff7875" : "transparent"
                        radius: 3
                        antialiasing: true

                        Behavior on color {
                            ColorAnimation { duration: 200; easing.type: Easing.OutCubic }
                        }

                        scale: windowCloseBtn.pressed ? 0.9 : (windowCloseBtn.hovered ? 1.1 : 1.0)
                        Behavior on scale {
                            NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
                        }
                    }

                    contentItem: Text {
                        text: "×"
                        color: windowCloseBtn.hovered ? "white" : "#86909c"
                        font.pixelSize: root.titleFontSize - 2
                        font.weight: Font.Bold
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter

                        Behavior on color {
                            ColorAnimation { duration: 200; easing.type: Easing.OutCubic }
                        }
                    }

                    onClicked: root.closeClicked()
                }
            }

            // 设备信息卡片
            Rectangle {
                id: deviceInfoCard
                Layout.fillWidth: true
                Layout.preferredHeight: root.cardHeight
                color: deviceInfoMouseArea.containsMouse ? "#f2f3f5" : "#f7f8fa"
                radius: 3
                antialiasing: true

                Behavior on color {
                    ColorAnimation { duration: 200; easing.type: Easing.OutCubic }
                }

                MouseArea {
                    id: deviceInfoMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 16
                    anchors.rightMargin: 16
                    spacing: 0

                    Item { Layout.fillHeight: true }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        Text {
                            text: "设备信息"
                            font.family: "PingFang SC, Microsoft YaHei UI"
                            font.pixelSize: root.baseFontSize + 1
                            font.weight: Font.Medium
                            color: "#4e5969"
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: 48
                            rowSpacing: 4

                            Text {
                                text: "设备序列号"
                                font.family: "PingFang SC, Microsoft YaHei UI"
                                font.pixelSize: root.baseFontSize
                                color: "#86909c"
                            }

                            Text {
                                text: "MAC地址"
                                font.family: "PingFang SC, Microsoft YaHei UI"
                                font.pixelSize: root.baseFontSize
                                color: "#86909c"
                            }

                            Text {
                                text: activationModel ? activationModel.serialNumber : "--"
                                font.family: "SF Mono, Consolas, monospace"
                                font.pixelSize: root.baseFontSize
                                color: "#1d2129"
                            }

                            Text {
                                text: activationModel ? activationModel.macAddress : "--"
                                font.family: "SF Mono, Consolas, monospace"
                                font.pixelSize: root.baseFontSize
                                color: "#1d2129"
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }

            // 激活验证码卡片
            Rectangle {
                id: activationCodeCard
                Layout.fillWidth: true
                Layout.preferredHeight: root.codeCardHeight
                color: activationCodeMouseArea.containsMouse ? "#f2f3f5" : "#f7f8fa"
                radius: 3
                antialiasing: true

                Behavior on color {
                    ColorAnimation { duration: 200; easing.type: Easing.OutCubic }
                }

                MouseArea {
                    id: activationCodeMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 16
                    anchors.rightMargin: 16
                    spacing: 16

                    Text {
                        text: "激活验证码"
                        font.family: "PingFang SC, Microsoft YaHei UI"
                        font.pixelSize: root.baseFontSize + 1
                        font.weight: Font.Medium
                        color: "#4e5969"
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: root.buttonHeight
                        color: "#ffffff"
                        radius: 3
                        border.color: "#e5e6eb"
                        border.width: 1
                        antialiasing: true

                        Text {
                            anchors.centerIn: parent
                            text: activationModel ? activationModel.activationCode : "------"
                            font.family: "SF Mono, Consolas, monospace"
                            font.pixelSize: root.baseFontSize + 3
                            font.weight: Font.Medium
                            color: "#f53f3f"
                            font.letterSpacing: 2
                        }
                    }

                    Button {
                        id: copyCodeBtn
                        text: "复制"
                        Layout.preferredWidth: screenMode === "compact" ? 60 : 80
                        height: root.buttonHeight

                        background: Rectangle {
                            color: copyCodeBtn.pressed ? "#0e42d2" :
                                   copyCodeBtn.hovered ? "#4080ff" : "#165dff"
                            radius: 3
                            antialiasing: true

                            Behavior on color {
                                ColorAnimation { duration: 200; easing.type: Easing.OutCubic }
                            }

                            scale: copyCodeBtn.pressed ? 0.95 : (copyCodeBtn.hovered ? 1.05 : 1.0)
                            Behavior on scale {
                                NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
                            }
                        }

                        font.family: "PingFang SC, Microsoft YaHei UI"
                        font.pixelSize: root.baseFontSize + 1
                        palette.buttonText: "white"

                        onClicked: root.copyCodeClicked()
                    }
                }
            }

            // 按钮区域
            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: root.buttonHeight + 4
                spacing: 16

                Button {
                    id: retryBtn
                    text: "跳转激活"
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.buttonHeight

                    background: Rectangle {
                        color: retryBtn.pressed ? "#0e42d2" :
                               retryBtn.hovered ? "#4080ff" : "#165dff"
                        radius: 3
                        antialiasing: true

                        Behavior on color {
                            ColorAnimation { duration: 200; easing.type: Easing.OutCubic }
                        }

                        scale: retryBtn.pressed ? 0.98 : (retryBtn.hovered ? 1.02 : 1.0)
                        Behavior on scale {
                            NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
                        }

                        layer.enabled: true
                        layer.effect: DropShadow {
                            horizontalOffset: 0
                            verticalOffset: 2
                            radius: 6
                            samples: 12
                            color: "#20165dff"
                        }
                    }

                    font.family: "PingFang SC, Microsoft YaHei UI"
                    font.pixelSize: root.baseFontSize + 2
                    font.weight: Font.Medium
                    palette.buttonText: "white"

                    onClicked: root.retryClicked()
                }
            }
        }
    }
}
