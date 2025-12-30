// 应用主入口
import QtQuick
import QtQuick.Window

import "windows"

// 主窗口作为根元素
MainWindow {
    id: mainWindow
    visible: true

    // 设置窗口 - 使用 Loader 延迟加载（作为独立窗口）
    Loader {
        id: settingsLoader
        active: false
        source: "windows/SettingsWindow.qml"

        onLoaded: {
            item.visible = true
            item.raise()
            item.requestActivate()
        }
    }

    // 监听 eventBridge 的信号来控制设置窗口
    Connections {
        target: eventBridge

        function onShowSettingsWindow() {
            if (settingsLoader.active) {
                // 已加载，直接显示
                settingsLoader.item.visible = true
                settingsLoader.item.raise()
                settingsLoader.item.requestActivate()
            } else {
                // 首次加载
                settingsLoader.active = true
            }
        }
    }
}
