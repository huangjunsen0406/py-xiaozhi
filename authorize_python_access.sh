#!/bin/bash

# 获取 conda 环境中的 Python 可执行文件路径
PYTHON_BIN=$(which python3)

echo "🔍 当前 Python 路径: $PYTHON_BIN"

# 拷贝路径到剪贴板
echo "$PYTHON_BIN" | pbcopy
echo "✅ 路径已复制到剪贴板"

# 打开辅助功能设置界面
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"

# 弹出提示
osascript <<EOF
tell application "System Events"
	display dialog "请手动将以下 Python 路径添加到『辅助功能』中:\n\n$PYTHON_BIN\n\n路径已复制到剪贴板。" buttons {"知道了"} default button "知道了"
end tell
EOF
