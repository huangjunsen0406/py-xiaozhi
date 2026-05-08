"""App management 共享工具函数."""

import re


def clean_app_name(name: str) -> str:
    """清理应用程序名称，移除版本号和特殊字符.

    Args:
        name: 原始名称

    Returns:
        str: 清理后的名称
    """
    if not name:
        return ""

    # 移除常见的版本号模式
    name = re.sub(r"\s+v?\d+[\.\d]*", "", name)
    name = re.sub(r"\s*\(\d+\)", "", name)
    name = re.sub(r"\s*\[.*?\]", "", name)

    # 移除多余的空格
    name = " ".join(name.split())

    return name.strip()
