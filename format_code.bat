@echo off
@chcp 65001 >nul
setlocal enabledelayedexpansion

echo 🧹 开始代码格式化...

echo 🔧 检查并安装依赖包...
python -m pip install --upgrade pip >nul
python -m pip install autoflake docformatter isort black flake8 >nul

echo 📦 依赖包安装完成

:: 定义要格式化的目标文件夹和文件
set TARGETS=src/ scripts/ hooks/ main.py

echo 📁 格式化目标: %TARGETS%
echo.

:: 删除未使用导入和变量
 echo 1️⃣ 删除未使用的导入和变量...
python -m autoflake -r --in-place --remove-unused-variables --remove-all-unused-imports --ignore-init-module-imports %TARGETS%

:: 修复文档字符串格式
 echo 2️⃣ 格式化文档字符串...
python -m docformatter -r -i --wrap-summaries=88 --wrap-descriptions=88 --make-summary-multi-line %TARGETS%

:: 自动排序导入
 echo 3️⃣ 排序导入语句...
python -m isort %TARGETS%

:: 自动格式化代码
 echo 4️⃣ 格式化代码...
python -m black %TARGETS%

:: 静态代码检查
 echo 5️⃣ 静态代码检查...
python -m flake8 %TARGETS%

echo.
echo ✅ 代码格式化完成！
echo 📊 已处理的目标: %TARGETS%

endlocal