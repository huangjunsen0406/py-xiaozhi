// 无边框可调整大小的窗口基类
import QtQuick
import QtQuick.Window
import "../theme"

Window {
    id: root

    flags: Qt.FramelessWindowHint | Qt.Window
    color: "transparent"

    minimumWidth: 480
    minimumHeight: 360

    // 边缘拖拽调整大小的边距
    property int resizeMargin: 8

    // 是否最大化或全屏
    property bool isMaximized: root.visibility === Window.Maximized || root.visibility === Window.FullScreen

    // 内容区域
    default property alias content: contentArea.data

    // 更新主题的窗口宽度
    onWidthChanged: Theme.windowWidth = width

    // 主容器（带圆角和边框）
    Rectangle {
        id: container
        anchors.fill: parent
        anchors.margins: root.isMaximized ? 0 : 1
        radius: root.isMaximized ? 0 : Theme.windowRadius
        color: Theme.background
        antialiasing: true
        border.width: root.isMaximized ? 0 : 1
        border.color: Theme.border

        // 内容区域
        Item {
            id: contentArea
            anchors.fill: parent
        }
    }

    // 边缘调整大小的 MouseArea - 放在顶层（最大化时隐藏）
    // 左边缘
    MouseArea {
        visible: !root.isMaximized
        width: resizeMargin
        height: parent.height - resizeMargin * 2
        x: 0
        y: resizeMargin
        cursorShape: Qt.SizeHorCursor
        onPressed: root.startSystemResize(Qt.LeftEdge)
    }

    // 右边缘
    MouseArea {
        visible: !root.isMaximized
        width: resizeMargin
        height: parent.height - resizeMargin * 2
        x: parent.width - resizeMargin
        y: resizeMargin
        cursorShape: Qt.SizeHorCursor
        onPressed: root.startSystemResize(Qt.RightEdge)
    }

    // 上边缘
    MouseArea {
        visible: !root.isMaximized
        width: parent.width - resizeMargin * 2
        height: resizeMargin
        x: resizeMargin
        y: 0
        cursorShape: Qt.SizeVerCursor
        onPressed: root.startSystemResize(Qt.TopEdge)
    }

    // 下边缘
    MouseArea {
        visible: !root.isMaximized
        width: parent.width - resizeMargin * 2
        height: resizeMargin
        x: resizeMargin
        y: parent.height - resizeMargin
        cursorShape: Qt.SizeVerCursor
        onPressed: root.startSystemResize(Qt.BottomEdge)
    }

    // 左上角
    MouseArea {
        visible: !root.isMaximized
        width: resizeMargin
        height: resizeMargin
        x: 0
        y: 0
        cursorShape: Qt.SizeFDiagCursor
        onPressed: root.startSystemResize(Qt.LeftEdge | Qt.TopEdge)
    }

    // 右上角
    MouseArea {
        visible: !root.isMaximized
        width: resizeMargin
        height: resizeMargin
        x: parent.width - resizeMargin
        y: 0
        cursorShape: Qt.SizeBDiagCursor
        onPressed: root.startSystemResize(Qt.RightEdge | Qt.TopEdge)
    }

    // 左下角
    MouseArea {
        visible: !root.isMaximized
        width: resizeMargin
        height: resizeMargin
        x: 0
        y: parent.height - resizeMargin
        cursorShape: Qt.SizeBDiagCursor
        onPressed: root.startSystemResize(Qt.LeftEdge | Qt.BottomEdge)
    }

    // 右下角
    MouseArea {
        visible: !root.isMaximized
        width: resizeMargin
        height: resizeMargin
        x: parent.width - resizeMargin
        y: parent.height - resizeMargin
        cursorShape: Qt.SizeFDiagCursor
        onPressed: root.startSystemResize(Qt.RightEdge | Qt.BottomEdge)
    }
}
