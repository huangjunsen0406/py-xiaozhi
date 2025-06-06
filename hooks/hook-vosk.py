"""PyInstaller 钩子文件: hook-vosk.py.

解决 vosk 在打包时找不到模型或依赖库的问题
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

# 添加src目录到Python路径，以便导入资源查找器
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from utils.resource_finder import find_models_dir

print(f"当前工作目录: {os.getcwd()}")

# 收集 datas 和 binaries
datas = []
binaries = []

# 收集 vosk 的元数据
datas.extend(copy_metadata("vosk"))

# 收集 vosk 可能用到的动态库
binaries.extend(collect_dynamic_libs("vosk"))

# 使用统一的资源查找器查找模型目录
models_dir = find_models_dir()
if models_dir:
    print(f"找到模型目录: {models_dir}")

    # 遍历模型目录下的所有子目录
    for item in models_dir.iterdir():
        if item.is_dir():
            print(f"收集模型: {item}")
            # 收集整个模型目录
            model_files = collect_data_files(str(item))
            datas.extend(model_files)
            print(f"收集了 {len(model_files)} 个文件")
else:
    print("未找到模型目录")

print(f"总共收集了 {len(datas)} 个数据文件")
for data in datas[:5]:  # 只打印前5个文件作为示例
    print(f"  {data}")

# 自动收集 vosk 的所有子模块
hiddenimports = collect_submodules("vosk")

# 添加其他可能未被自动发现的依赖
additional_imports = [
    "cffi",  # vosk 依赖的 cffi
    "packaging.version",  # vosk 检查版本
    "numpy",  # 音频处理
    "sounddevice",  # 录音功能
]

# 合并所有导入
hiddenimports.extend(additional_imports)
