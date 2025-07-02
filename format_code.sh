#!/bin/bash

echo "🧹 开始代码格式化..."

# 定义要格式化的目标文件夹和文件
TARGETS="src/ scripts/ hooks/ main.py"

echo "📁 格式化目标: $TARGETS"
echo ""

# 删除未使用导入和变量（非侵入但有效）
echo "1️⃣ 删除未使用的导入和变量..."
autoflake -r --in-place --remove-unused-variables --remove-all-unused-imports --ignore-init-module-imports $TARGETS

# 修复 docstring 的标点、首字母等格式
echo "2️⃣ 格式化文档字符串..."
docformatter -r -i --wrap-summaries=88 --wrap-descriptions=88 --make-summary-multi-line $TARGETS

# 自动排序导入
echo "3️⃣ 排序导入语句..."
isort $TARGETS

# 自动格式化（处理长行、函数参数、f字符串等）
echo "4️⃣ 格式化代码..."
black $TARGETS

# 最后静态检查（非修复）
echo "5️⃣ 静态代码检查..."
flake8 $TARGETS

echo ""
echo "✅ 代码格式化完成！"
echo "📊 已处理的目标: $TARGETS"
