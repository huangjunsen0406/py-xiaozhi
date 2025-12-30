// 自定义输入框组件
import QtQuick
import QtQuick.Controls
import "../theme"

TextField {
    id: root

    // 是否为密码模式
    property bool isPassword: false
    // 密码是否可见
    property bool passwordVisible: false

    implicitWidth: 200
    implicitHeight: 36

    font.family: Theme.fontFamily
    font.pixelSize: Theme.fontSizeSm
    color: enabled ? Theme.textPrimary : Theme.textPlaceholder
    placeholderTextColor: Theme.textPlaceholder
    selectionColor: Theme.primary
    selectedTextColor: "white"
    selectByMouse: true

    leftPadding: Theme.spacingMd
    rightPadding: isPassword ? 40 : Theme.spacingMd

    echoMode: isPassword && !passwordVisible ? TextInput.Password : TextInput.Normal

    background: Rectangle {
        radius: Theme.radiusMd
        color: Theme.backgroundSecondary
        border.width: 1
        border.color: root.activeFocus ? Theme.primary : "transparent"
    }

    // 密码切换按钮
    Item {
        visible: root.isPassword
        anchors.right: parent.right
        anchors.rightMargin: 4
        anchors.verticalCenter: parent.verticalCenter
        width: 28
        height: 28

        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusSm
            color: eyeMouseArea.containsMouse ? Theme.backgroundHover : "transparent"
        }

        // 眼睛图标 (SVG path)
        Canvas {
            id: eyeIcon
            anchors.centerIn: parent
            width: 18
            height: 18

            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                ctx.strokeStyle = Theme.textSecondary
                ctx.lineWidth = 1.5
                ctx.lineCap = "round"
                ctx.lineJoin = "round"

                // 眼睛轮廓
                ctx.beginPath()
                ctx.moveTo(1, 9)
                ctx.bezierCurveTo(1, 9, 4, 3, 9, 3)
                ctx.bezierCurveTo(14, 3, 17, 9, 17, 9)
                ctx.bezierCurveTo(17, 9, 14, 15, 9, 15)
                ctx.bezierCurveTo(4, 15, 1, 9, 1, 9)
                ctx.stroke()

                // 瞳孔
                ctx.beginPath()
                ctx.arc(9, 9, 3, 0, Math.PI * 2)
                ctx.stroke()

                // 斜线 (隐藏时)
                if (!root.passwordVisible) {
                    ctx.beginPath()
                    ctx.moveTo(3, 15)
                    ctx.lineTo(15, 3)
                    ctx.stroke()
                }
            }
        }

        MouseArea {
            id: eyeMouseArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                root.passwordVisible = !root.passwordVisible
                eyeIcon.requestPaint()
            }
        }
    }
}
