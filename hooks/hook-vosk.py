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

from src.utils.resource_finder import find_models_dir

# 添加src目录到Python路径，以便导入资源查找器
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

print(f"当前工作目录: {os.getcwd()}")

# 收集 datas 和 binaries
datas = []
binaries = []

# 收集 vosk 的元数据
try:
    datas.extend(copy_metadata("vosk"))
    print("✓ 成功收集vosk元数据")
except Exception as e:
    print(f"警告: 无法收集vosk元数据: {e}")

# 收集 vosk 的数据文件（包括动态库）
try:
    vosk_data_files = collect_data_files("vosk")
    datas.extend(vosk_data_files)
    print(f"✓ 收集了 {len(vosk_data_files)} 个vosk数据文件")
except Exception as e:
    print(f"警告: 无法收集vosk数据文件: {e}")

# 收集 vosk 的动态库
try:
    vosk_binaries = collect_dynamic_libs("vosk")
    binaries.extend(vosk_binaries)
    print(f"✓ 收集了 {len(vosk_binaries)} 个vosk动态库")
except Exception as e:
    print(f"警告: 无法收集vosk动态库: {e}")

# 手动查找并添加 libvosk.dyld 文件
try:
    import vosk
    vosk_dir = Path(vosk.__file__).parent
    libvosk_path = vosk_dir / "libvosk.dyld"

    if libvosk_path.exists():
        # 添加到二进制文件列表
        binaries.append((str(libvosk_path), "vosk"))
        print(f"✓ 手动添加libvosk.dyld: {libvosk_path}")
    else:
        print("警告: 未找到libvosk.dyld文件")

    # 也检查其他可能的动态库文件
    for lib_file in vosk_dir.glob("*.dylib"):
        binaries.append((str(lib_file), "vosk"))
        print(f"✓ 添加动态库: {lib_file}")

except Exception as e:
    print(f"警告: 无法手动添加vosk动态库: {e}")

# 使用统一的资源查找器查找模型目录
models_dir = find_models_dir()
if models_dir:
    print(f"找到模型目录: {models_dir}")

    # 遍历模型目录下的所有子目录
    for item in models_dir.iterdir():
        if item.is_dir():
            print(f"收集模型: {item}")
            # 收集整个模型目录的所有文件
            try:
                model_files = collect_data_files(str(item))
                datas.extend(model_files)
                print(f"收集了 {len(model_files)} 个模型文件")
            except Exception as e:
                print(f"警告: 无法收集模型文件 {item}: {e}")
else:
    print("未找到模型目录")

print(f"总共收集了 {len(datas)} 个数据文件")
print(f"总共收集了 {len(binaries)} 个二进制文件")

# 显示前几个文件作为示例
for i, data in enumerate(datas[:3]):
    print(f"  数据文件{i+1}: {data}")

for i, binary in enumerate(binaries[:3]):
    print(f"  二进制文件{i+1}: {binary}")

# 收集所有 vosk 子模块
try:
    hiddenimports = collect_submodules("vosk")
    print(f"✓ 收集了 {len(hiddenimports)} 个vosk子模块")
except Exception as e:
    print(f"警告: 无法收集vosk子模块: {e}")
    hiddenimports = []

# 添加其他可能未被自动发现的依赖
additional_imports = [
    "vosk",  # 确保主模块被包含
    "cffi",  # vosk 依赖的 cffi
    "packaging.version",  # vosk 检查版本
    "numpy",  # 音频处理
    "sounddevice",  # 录音功能
    "_cffi_backend",  # cffi 后端
]

# 合并所有导入
hiddenimports.extend(additional_imports)
print(f"隐藏导入总数: {len(hiddenimports)}")