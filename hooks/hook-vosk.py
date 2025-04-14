"""
PyInstaller 钩子文件: vosk

解决 vosk 在打包时找不到模型或依赖库的问题
"""

import os
import sys
import logging
from pathlib import Path
from PyInstaller.utils.hooks import (
    collect_dynamic_libs, 
    copy_metadata,
    collect_submodules
)

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# 常量定义
DEFAULT_MODEL_PATH = "models/vosk-model-small-cn-0.22"

# 收集 datas 和 binaries
datas = []
binaries = []

# 收集 vosk 的元数据
datas.extend(copy_metadata('vosk'))

# 收集 vosk 可能用到的动态库
binaries.extend(collect_dynamic_libs('vosk'))

# 读取配置文件获取模型路径
def get_model_path_from_config():
    """从ConfigManager获取Vosk模型路径"""
    try:
        # 尝试导入ConfigManager
        sys.path.insert(0, str(Path.cwd()))
        from src.utils.config_manager import ConfigManager
        
        # 获取配置实例
        config_manager = ConfigManager.get_instance()
        
        # 获取模型路径
        model_path = config_manager.get_config(
            "WAKE_WORD_OPTIONS.MODEL_PATH", 
            DEFAULT_MODEL_PATH
        )
        logger.info(f"从配置中获取模型路径: {model_path}")
        return Path(model_path)
    except Exception as e:
        logger.error(f"通过ConfigManager获取模型路径时出错: {e}")
        logger.exception("详细错误信息:")
        # 回退到默认路径
        return Path(DEFAULT_MODEL_PATH)

# 获取模型路径
model_path = get_model_path_from_config()
model_dir = Path.cwd() / model_path
model_dir = model_dir.resolve()  # 获取绝对路径

# 设置环境变量
if model_dir.exists():
    os.environ['VOSK_MODEL_PATH'] = str(model_dir)
    logger.info(f"设置VOSK_MODEL_PATH环境变量: {os.environ['VOSK_MODEL_PATH']}")

if model_dir.exists() and model_dir.is_dir():
    logger.info(f"发现 Vosk 模型目录: {model_dir}")
    
    # 收集模型目录下的所有文件
    model_files = []
    for root, dirs, files in os.walk(model_dir):
        rel_dir = Path(root).relative_to(Path.cwd())
        for file in files:
            # 跳过临时文件
            if file.startswith('.') or file.endswith('.tmp'):
                continue
                
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