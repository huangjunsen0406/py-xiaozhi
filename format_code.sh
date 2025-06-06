#!/bin/bash

# 删除未使用导入和变量（非侵入但有效）
autoflake -r --in-place --remove-unused-variables --remove-all-unused-imports .

# 修复 docstring 的标点、首字母等格式
docformatter -r -i .

# 自动排序导入
isort .

# 自动格式化
black .

# 最后静态检查（非修复）
flake8 .
