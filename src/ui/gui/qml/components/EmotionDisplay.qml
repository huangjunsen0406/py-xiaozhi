// 表情显示组件
import QtQuick
import "../theme"

Item {
    id: root

    property string source: ""

    implicitWidth: 200
    implicitHeight: 200

    // 图片或动画
    AnimatedImage {
        id: image
        anchors.centerIn: parent
        width: Math.min(parent.width, parent.height) * 0.9
        height: width
        source: root.source
        fillMode: Image.PreserveAspectFit
        visible: root.source.length > 0 && !root.source.startsWith("😊")
        playing: visible
    }

    // Emoji 回退
    Text {
        anchors.centerIn: parent
        text: root.source
        font.pixelSize: Math.min(parent.width, parent.height) * 0.6
        visible: root.source.length > 0 && root.source.startsWith("😊")
    }

    // 占位
    Text {
        anchors.centerIn: parent
        text: "😊"
        font.pixelSize: Math.min(parent.width, parent.height) * 0.6
        visible: root.source.length === 0
        opacity: 0.3
    }
}
