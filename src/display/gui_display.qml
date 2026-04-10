import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtGraphicalEffects 1.15

Rectangle {
    id: root
    color: "#f5f5f5"

    // 信号定义 - 与 Python 回调对接
    signal manualButtonPressed()
    signal manualButtonReleased()
    signal autoButtonClicked()
    signal abortButtonClicked()
    signal modeButtonClicked()
    signal sendButtonClicked(string text)
    signal settingsButtonClicked()
    // 标题栏相关信号
    signal titleMinimize()
    signal titleClose()
    signal titleDragStart(real mouseX, real mouseY)
    signal titleDragMoveTo(real mouseX, real mouseY)
    signal titleDragEnd()

    // 主布局
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 0
        spacing: 0

        // 自定义标题栏：最小化、关闭、可拖动
        Rectangle {
            id: titleBar
            Layout.fillWidth: true
            Layout.preferredHeight: 36
            color: "#f7f8fa"
            border.width: 0

            // 整条标题栏拖动（使用屏幕坐标，避免累计误差导致抖动）
            // 放在最底层，让按钮的 MouseArea 可以优先响应
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton
                onPressed: {
                    root.titleDragStart(mouse.x, mouse.y)
                }
                onPositionChanged: {
                    if (pressed) {
                        root.titleDragMoveTo(mouse.x, mouse.y)
                    }
                }
                onReleased: {
                    root.titleDragEnd()
                }
                z: 0  // 最底层
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 8
                spacing: 8
                z: 1  // 按钮层在拖动层上方

                // 左侧拖动区域
                Item { id: dragArea; Layout.fillWidth: true; Layout.fillHeight: true }

                // 最小化
                Rectangle {
                    id: btnMin
                    width: 24; height: 24; radius: 6
                    color: btnMinMouse.pressed ? "#e5e6eb" : (btnMinMouse.containsMouse ? "#f2f3f5" : "transparent")
                    z: 2  // 确保按钮在最上层
                    Text { anchors.centerIn: parent; text: "–"; font.pixelSize: 14; color: "#4e5969" }
                    MouseArea {
                        id: btnMinMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: root.titleMinimize()
                    }
                }

                // 关闭
                Rectangle {
                    id: btnClose
                    width: 24; height: 24; radius: 6
                    color: btnCloseMouse.pressed ? "#f53f3f" : (btnCloseMouse.containsMouse ? "#ff7875" : "transparent")
                    z: 2  // 确保按钮在最上层
                    Text { anchors.centerIn: parent; text: "×"; font.pixelSize: 14; color: btnCloseMouse.containsMouse ? "white" : "#86909c" }
                    MouseArea {
                        id: btnCloseMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: root.titleClose()
                    }
                }
            }
        }

        // 状态卡片区域
        Rectangle {
            id: statusCard
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "transparent"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 12

                // 状态标签
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 40
                    color: "#E3F2FD"
                    radius: 10

                    Text {
                        anchors.centerIn: parent
                        text: displayModel ? displayModel.statusText : qsTr("状态: 未连接")
                        font.family: "PingFang SC, Microsoft YaHei UI"
                        font.pixelSize: 14
                        font.weight: Font.Bold
                        color: "#2196F3"
                    }
                }

                // 表情显示区域
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 80

                    // 动态加载表情：AnimatedImage 用于 GIF，Image 用于静态图，Text 用于 emoji
                    Loader {
                        id: emotionLoader
                        anchors.centerIn: parent
                        // 保持正方形，取宽高中较小值的 70%，最小60px
                        property real maxSize: Math.max(Math.min(parent.width, parent.height) * 0.7, 60)
                        width: maxSize
                        height: maxSize

                        sourceComponent: {
                            var path = displayModel ? displayModel.emotionPath : ""
                            if (!path || path.length === 0) {
                                return emojiComponent
                            }
                            if (path.indexOf(".gif") !== -1) {
                                return gifComponent
                            }
                            if (path.indexOf(".") !== -1) {
                                return imageComponent
                            }
                            return emojiComponent
                        }

                        // GIF 动图组件
                        Component {
                            id: gifComponent
                            AnimatedImage {
                                fillMode: Image.PreserveAspectCrop
                                source: displayModel ? displayModel.emotionPath : ""
                                playing: true
                                speed: 1.05
                                cache: true
                                clip: true
                                onStatusChanged: {
                                    if (status === Image.Error) {
                                        console.error("AnimatedImage error:", errorString, "src=", source)
                                    }
                                }
                            }
                        }

                        // 静态图片组件
                        Component {
                            id: imageComponent
                            Image {
                                fillMode: Image.PreserveAspectCrop
                                source: displayModel ? displayModel.emotionPath : ""
                                cache: true
                                clip: true
                                onStatusChanged: {
                                    if (status === Image.Error) {
                                        console.error("Image error:", errorString, "src=", source)
                                    }
                                }
                            }
                        }

                        // Emoji 文本组件
                        Component {
                            id: emojiComponent
                            Text {
                                text: displayModel ? displayModel.emotionPath : "😊"
                                font.pixelSize: 80
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }

                // TTS 文本显示区域
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 60
                    color: "transparent"

                    Text {
                        anchors.fill: parent
                        anchors.margins: 10
                        text: displayModel ? displayModel.ttsText : qsTr("待命")
                        font.family: "PingFang SC, Microsoft YaHei UI"
                        font.pixelSize: 13
                        color: "#555555"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }

        // 按钮区域（统一配色与尺寸）
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 72
            color: "#f7f8fa"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                anchors.bottomMargin: 10
                spacing: 6

                // 手动模式按钮（按住说话） - 主色
                Button {
                    id: manualBtn
                    Layout.preferredWidth: 100
                    Layout.fillWidth: true
                    Layout.maximumWidth: 140
                    Layout.preferredHeight: 38
                    text: qsTr("按住后说话")
                    visible: displayModel ? !displayModel.autoMode : true

                    background: Rectangle {
                        color: manualBtn.pressed ? "#0e42d2" : (manualBtn.hovered ? "#4080ff" : "#165dff")
                        radius: 8

                        Behavior on color { ColorAnimation { duration: 120; easing.type: Easing.OutCubic } }
                    }

                    contentItem: Text {
                        text: manualBtn.text
                        font.family: "PingFang SC, Microsoft YaHei UI"
                        font.pixelSize: 12
                        color: "white"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }

                    onPressed: { manualBtn.text = qsTr("松开以停止"); root.manualButtonPressed() }
                    onReleased: { manualBtn.text = qsTr("按住后说话"); root.manualButtonReleased() }
                }

                // 自动模式按钮 - 主色
                Button {
                    id: autoBtn
                    Layout.preferredWidth: 100
                    Layout.fillWidth: true
                    Layout.maximumWidth: 140
                    Layout.preferredHeight: 38
                    text: displayModel ? displayModel.buttonText : qsTr("开始对话")
                    visible: displayModel ? displayModel.autoMode : false

                    background: Rectangle {
                        color: autoBtn.pressed ? "#0e42d2" : (autoBtn.hovered ? "#4080ff" : "#165dff")
                        radius: 8
                        Behavior on color { ColorAnimation { duration: 120; easing.type: Easing.OutCubic } }
                    }

                    contentItem: Text {
                        text: autoBtn.text
                        font.family: "PingFang SC, Microsoft YaHei UI"
                        font.pixelSize: 12
                        color: "white"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    onClicked: root.autoButtonClicked()
                }

                // 打断对话 - 次要色
                Button {
                    id: abortBtn
                    Layout.preferredWidth: 80
                    Layout.fillWidth: true
                    Layout.maximumWidth: 120
                    Layout.preferredHeight: 38
                    text: qsTr("打断对话")

                    background: Rectangle { color: abortBtn.pressed ? "#e5e6eb" : (abortBtn.hovered ? "#f2f3f5" : "#eceff3"); radius: 8 }
                    contentItem: Text {
                        text: abortBtn.text
                        font.family: "PingFang SC, Microsoft YaHei UI"
                        font.pixelSize: 12
                        color: "#1d2129"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    onClicked: root.abortButtonClicked()
                }

                // 输入 + 发送
                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 120
                    Layout.preferredHeight: 38
                    spacing: 6

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 38
                        color: "white"
                        radius: 8
                        border.color: textInput.activeFocus ? "#165dff" : "#e5e6eb"
                        border.width: 1

                        TextInput {
                            id: textInput
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            verticalAlignment: TextInput.AlignVCenter
                            font.family: "PingFang SC, Microsoft YaHei UI"
                            font.pixelSize: 12
                            color: "#333333"
                            selectByMouse: true
                            clip: true

                            // 占位符
                            Text { anchors.fill: parent; text: qsTr("输入文字..."); font: textInput.font; color: "#c9cdd4"; verticalAlignment: Text.AlignVCenter; visible: !textInput.text && !textInput.activeFocus }

                            Keys.onReturnPressed: { if (textInput.text.trim().length > 0) { root.sendButtonClicked(textInput.text); textInput.text = "" } }
                        }
                    }

                    Button {
                        id: sendBtn
                        Layout.preferredWidth: 60
                        Layout.maximumWidth: 84
                        Layout.preferredHeight: 38
                        text: qsTr("发送")
                        background: Rectangle { color: sendBtn.pressed ? "#0e42d2" : (sendBtn.hovered ? "#4080ff" : "#165dff"); radius: 8 }
                        contentItem: Text {
                            text: sendBtn.text
                            font.family: "PingFang SC, Microsoft YaHei UI"
                            font.pixelSize: 12
                            color: "white"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: { if (textInput.text.trim().length > 0) { root.sendButtonClicked(textInput.text); textInput.text = "" } }
                    }
                }

                // 模式（次要）
                Button {
                    id: modeBtn
                    Layout.preferredWidth: 80
                    Layout.fillWidth: true
                    Layout.maximumWidth: 120
                    Layout.preferredHeight: 38
                    text: displayModel ? displayModel.modeText : qsTr("手动对话")
                    background: Rectangle { color: modeBtn.pressed ? "#e5e6eb" : (modeBtn.hovered ? "#f2f3f5" : "#eceff3"); radius: 8 }
                    contentItem: Text {
                        text: modeBtn.text
                        font.family: "PingFang SC, Microsoft YaHei UI"
                        font.pixelSize: 12
                        color: "#1d2129"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    onClicked: root.modeButtonClicked()
                }

                // 设置（次要）
                Button {
                    id: settingsBtn
                    Layout.preferredWidth: 80
                    Layout.fillWidth: true
                    Layout.maximumWidth: 120
                    Layout.preferredHeight: 38
                    text: qsTr("参数配置")
                    background: Rectangle { color: settingsBtn.pressed ? "#e5e6eb" : (settingsBtn.hovered ? "#f2f3f5" : "#eceff3"); radius: 8 }
                    contentItem: Text {
                        text: settingsBtn.text
                        font.family: "PingFang SC, Microsoft YaHei UI"
                        font.pixelSize: 12
                        color: "#1d2129"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    onClicked: root.settingsButtonClicked()
                }
            }
        }
    }
}
