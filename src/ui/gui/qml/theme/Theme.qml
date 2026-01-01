// 主题系统 - 定义颜色、字体、间距等
pragma Singleton
import QtQuick

QtObject {
    id: theme

    // ========== 响应式断点 ==========
    readonly property int breakpointSm: 480
    readonly property int breakpointMd: 768
    readonly property int breakpointLg: 1024

    // 当前窗口宽度（由 AppWindow 设置）
    property int windowWidth: 800

    // 缩放因子
    readonly property real scaleFactor: {
        if (windowWidth < breakpointSm) return 0.8
        if (windowWidth < breakpointMd) return 0.9
        return 1.0
    }

    // ========== 颜色 ==========
    // 主色系
    readonly property color primary: "#165DFF"
    readonly property color primaryHover: "#4080FF"
    readonly property color primaryPressed: "#0E42D2"
    readonly property color primaryLight: "#E8F3FF"      // 浅蓝背景
    readonly property color primaryText: "#2196F3"       // 蓝色文字

    // 功能色
    readonly property color success: "#00B42A"
    readonly property color successLight: "#E8FFEA"      // 成功浅背景
    readonly property color successBorder: "#B7EB8F"     // 成功边框

    readonly property color warning: "#FF7D00"
    readonly property color warningLight: "#FFF7E8"      // 警告浅背景
    readonly property color warningBorder: "#FFE58F"     // 警告边框

    readonly property color error: "#F53F3F"
    readonly property color errorHover: "#FF7875"        // 错误悬停
    readonly property color errorLight: "#FFF2F0"        // 错误浅背景
    readonly property color errorBorder: "#FFCCC7"       // 错误边框

    // 背景色
    readonly property color background: "#FFFFFF"
    readonly property color backgroundSecondary: "#F7F8FA"
    readonly property color backgroundHover: "#F2F3F5"

    // 文字色
    readonly property color textPrimary: "#1D2129"
    readonly property color textSecondary: "#4E5969"
    readonly property color textPlaceholder: "#86909C"

    // 边框分割线
    readonly property color border: "#E5E6EB"
    readonly property color divider: "#F2F3F5"

    // ========== 字体大小 ==========
    readonly property int fontSizeXs: Math.round(10 * scaleFactor)
    readonly property int fontSizeSm: Math.round(12 * scaleFactor)
    readonly property int fontSizeMd: Math.round(14 * scaleFactor)
    readonly property int fontSizeLg: Math.round(16 * scaleFactor)
    readonly property int fontSizeXl: Math.round(20 * scaleFactor)
    readonly property int fontSizeXxl: Math.round(24 * scaleFactor)

    // ========== 间距 ==========
    readonly property int spacingXs: Math.round(4 * scaleFactor)
    readonly property int spacingSm: Math.round(8 * scaleFactor)
    readonly property int spacingMd: Math.round(12 * scaleFactor)
    readonly property int spacingLg: Math.round(16 * scaleFactor)
    readonly property int spacingXl: Math.round(20 * scaleFactor)
    readonly property int spacingXxl: Math.round(24 * scaleFactor)

    // ========== 圆角 ==========
    readonly property int radiusSm: 4
    readonly property int radiusMd: 8
    readonly property int radiusLg: 12
    readonly property int radiusXl: 16

    // ========== 阴影 ==========
    readonly property color shadowColor: "#15000000"      // 主阴影色
    readonly property color shadowLight: "#08000000"      // 轻阴影 (外层)
    readonly property color shadowMedium: "#06000000"     // 中阴影 (中层)
    readonly property color shadowSubtle: "#04000000"     // 微阴影 (最外层)
    readonly property int shadowRadius: 12

    // ========== 动画 ==========
    readonly property int animationFast: 150
    readonly property int animationNormal: 200
    readonly property int animationSlow: 300

    // ========== 窗口 ==========
    readonly property int windowRadius: 8
    readonly property int titleBarHeight: Math.round(40 * scaleFactor)
    readonly property int resizeMargin: 8

    // ========== 字体家族 ==========
    readonly property string fontFamily: Qt.platform.os === "osx" ? "PingFang SC" : (Qt.platform.os === "windows" ? "Microsoft YaHei UI" : "sans-serif")
    readonly property string fontFamilyMono: Qt.platform.os === "osx" ? "SF Mono" : "monospace"
}
