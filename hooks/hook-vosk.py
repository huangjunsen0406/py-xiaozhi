"""
PyInstaller 钩子文件: hook-vosk.py

解决 vosk 在打包时找不到模型或依赖库的问题
"""

import os
from PyInstaller.utils.hooks import (
    collect_dynamic_libs, 
    copy_metadata,
    collect_submodules
)

# 常量定义
DEFAULT_MODEL_PATH = "models/vosk-model-small-cn-0.22"

# 收集 datas 和 binaries
datas = []
binaries = []

# 收集 vosk 的元数据
datas.extend(copy_metadata('vosk'))

# 收集 vosk 可能用到的动态库
binaries.extend(collect_dynamic_libs('vosk'))

# 获取模型路径
try:
    model_path = os.path.join(os.getcwd(), DEFAULT_MODEL_PATH)
    if os.path.exists(model_path) and os.path.isdir(model_path):
        print(f"Found Vosk model directory: {model_path}")
        
        # 收集模型目录下的所有文件
        for root, dirs, files in os.walk(model_path):
            rel_dir = os.path.relpath(root, os.getcwd())
            for file in files:
                # 跳过临时文件
                if file.startswith('.') or file.endswith('.tmp'):
                    continue
                    
                src_file = os.path.join(root, file)
                # 确保是相对路径
                datas.append((src_file, rel_dir))
        
        print(f"Added {len(datas)} model files to package resources")
    else:
        print(f"Vosk model directory not found: {model_path}")
except Exception as e:
    print(f"Error collecting Vosk model files: {e}")

# 自动收集 vosk 的所有子模块
hiddenimports = collect_submodules('vosk')

# 添加其他可能未被自动发现的依赖
additional_imports = [
    'cffi',  # vosk 依赖的 cffi
    'packaging.version',  # vosk 检查版本
    'numpy',  # 音频处理
    'sounddevice',  # 录音功能
]

# 合并所有导入
hiddenimports.extend(additional_imports) 