"""
PyInstaller 钩子文件: vosk

解决 vosk 在打包时找不到模型或依赖库的问题
"""

import os
import sys
import json
import logging
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

logger = logging.getLogger('hook-vosk')

# 收集 datas 和 binaries
datas = []
binaries = []

# 收集 vosk 的元数据
datas.extend(copy_metadata('vosk'))

# 收集 vosk 可能用到的动态库
binaries.extend(collect_dynamic_libs('vosk'))

# 读取配置文件获取模型路径
def get_model_path_from_config():
    """从配置文件读取 Vosk 模型路径"""
    try:
        config_paths = [
            Path('config/config.json'),
            Path(Path.cwd() / 'config' / 'config.json'),
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    model_path = config.get(
                        "WAKE_WORD_MODEL_PATH", 
                        "models/vosk-model-small-cn-0.22"
                    )
                    return Path(model_path)
        
        # 默认路径
        return Path("models/vosk-model-small-cn-0.22")
    except Exception as e:
        logger.error(f"读取配置获取模型路径时出错: {e}")
        return Path("models/vosk-model-small-cn-0.22")  # 默认路径

# 获取模型路径
model_path = get_model_path_from_config()
model_dir = Path.cwd() / model_path

if model_dir.exists() and model_dir.is_dir():
    logger.info(f"发现 Vosk 模型目录: {model_dir}")
    
    # 收集模型目录下的所有文件
    model_files = []
    for root, dirs, files in os.walk(model_dir):
        rel_dir = Path(root).relative_to(Path.cwd())
        for file in files:
            src_file = Path(root) / file
            # 确保是相对路径
            model_files.append((str(src_file), str(rel_dir)))
    
    if model_files:
        logger.info(f"添加 {len(model_files)} 个模型文件到打包资源")
        datas.extend(model_files)
    else:
        logger.warning(f"模型目录存在但没有找到文件: {model_dir}")
else:
    logger.warning(f"未找到 Vosk 模型目录: {model_dir}")

# 确保加载 vosk 所需的所有模块
hiddenimports = [
    'vosk',
    'vosk.vosk_cffi',  # 必要的 C 接口
    'cffi',  # vosk 依赖的 cffi
    'packaging.version',  # vosk 检查版本
    'numpy',  # 音频处理
    'sounddevice',  # 录音功能
] 