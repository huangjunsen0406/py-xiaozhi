"""
小智应用程序 PyInstaller 运行时钩子

此钩子在应用程序启动时执行，用于:
1. 初始化日志系统
2. 预加载 opus 库
3. 设置必要的环境变量
4. 配置模型路径
"""

import sys
import os
import ctypes
import logging
from pathlib import Path
import platform

from src.utils.logging_config import get_logger

# 常量定义
LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DEFAULT_VOSK_MODEL_PATH = 'models/vosk-model-small-cn-0.22'

# 获取系统信息
SYSTEM = platform.system().lower()
ARCHITECTURE = platform.machine().lower()
logger = get_logger(__name__)



def get_base_path():
    """获取应用程序基础路径"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller打包环境
        return Path(sys._MEIPASS)
    else:
        # 开发环境
        return Path.cwd()


def setup_opus_early():
    """尽早加载 opus 库"""
    logger = logging.getLogger("RuntimeHook")
    logger.info("正在预加载 opus 库...")
    
    base_path = get_base_path()
    logger.info(f"应用程序基础路径: {base_path}")
    
    lib_paths = {
        'windows': {
            'x86': base_path / 'libs' / 'windows' / 'x86' / 'opus.dll',
            'x86_64': base_path / 'libs' / 'windows' / 'opus.dll',
            'amd64': base_path / 'libs' / 'windows' / 'opus.dll',
            'arm64': base_path / 'libs' / 'windows' / 'arm64' / 'opus.dll',
        },
        'darwin': {
            'x86_64': base_path / 'libs' / 'macos' / 'libopus.dylib',
            'arm64': base_path / 'libs' / 'macos' / 'arm64' / 'libopus.dylib',
        },
        'linux': {
            'x86_64': base_path / 'libs' / 'linux' / 'libopus.so',
            'arm64': base_path / 'libs' / 'linux' / 'arm64' / 'libopus.so',
            'aarch64': base_path / 'libs' / 'linux' / 'arm64' / 'libopus.so',
        }
    }
    
    try:
        # 获取当前系统对应的库路径
        system_paths = lib_paths.get(SYSTEM, {})
        lib_path = system_paths.get(ARCHITECTURE)
        
        # 尝试备用路径
        if not lib_path or not lib_path.exists():
            if SYSTEM == 'linux':
                lib_path = base_path / 'libs' / 'linux' / 'libopus.so.0'
            
        if lib_path and lib_path.exists():
            logger.info(f"找到opus库文件: {lib_path}")
            
            # 设置环境变量
            setup_library_path(lib_path)
            
            # 尝试加载库
            try:
                opus_lib = ctypes.CDLL(str(lib_path))
                logger.info("opus库加载成功")
                # 设置全局标记
                sys._opus_loaded = True
                return True
            except Exception as e:
                logger.error(f"opus库加载失败: {e}")
        else:
            logger.warning(f"未找到适用于{SYSTEM}-{ARCHITECTURE}的opus库文件")
        
        return False
    except Exception as e:
        logger.error(f"opus库初始化过程中出错: {e}")
        return False


def setup_library_path(lib_path):
    """设置库搜索路径环境变量"""
    logger = logging.getLogger("RuntimeHook")
    lib_dir = str(lib_path.parent)
    
    if SYSTEM == 'windows':
        # Windows平台
        os.environ['PATH'] = (lib_dir + os.pathsep + os.environ.get('PATH', ''))
        
        # 添加DLL搜索路径 (Windows 10+)
        if hasattr(os, 'add_dll_directory'):
            try:
                os.add_dll_directory(lib_dir)
                logger.info(f"已添加DLL搜索路径: {lib_dir}")
            except Exception as e:
                logger.error(f"添加DLL搜索路径失败: {e}")
                
    elif SYSTEM == 'darwin':
        # macOS平台
        os.environ['DYLD_LIBRARY_PATH'] = (
            lib_dir + os.pathsep + os.environ.get('DYLD_LIBRARY_PATH', '')
        )
        
    else:
        # Linux平台
        os.environ['LD_LIBRARY_PATH'] = (
            lib_dir + os.pathsep + os.environ.get('LD_LIBRARY_PATH', '')
        )
        
    logger.info(f"已设置库搜索路径环境变量: {lib_dir}")


def setup_vosk_model_path():
    """设置Vosk模型路径环境变量"""
    logger = logging.getLogger("RuntimeHook")
    
    # 从ConfigManager获取配置的模型路径
    try:
        from src.utils.config_manager import ConfigManager
        config_manager = ConfigManager.get_instance()
        model_path_str = config_manager.get_config(
            "WAKE_WORD_OPTIONS.MODEL_PATH", 
            DEFAULT_VOSK_MODEL_PATH
        )
        logger.info(f"从配置读取模型路径: {model_path_str}")
    except Exception as e:
        logger.warning(f"无法从ConfigManager获取模型路径: {e}")
        model_path_str = DEFAULT_VOSK_MODEL_PATH
    
    base_path = get_base_path()
    model_path = base_path / model_path_str
    
    if model_path.exists() and model_path.is_dir():
        logger.info(f"找到Vosk模型目录: {model_path}")
        os.environ['VOSK_MODEL_PATH'] = str(model_path)
        return True
    else:
        logger.warning(f"未找到Vosk模型目录: {model_path}")
        # 尝试备用路径
        alt_model_path = Path.cwd() / model_path_str
        if alt_model_path.exists():
            logger.info(f"在备用位置找到模型: {alt_model_path}")
            os.environ['VOSK_MODEL_PATH'] = str(alt_model_path)
            return True
        return False


def setup_executable_path():
    """记录可执行文件路径信息"""
    logger = logging.getLogger("RuntimeHook")
    try:
        logger.info(f"可执行文件路径: {sys.executable}")
        logger.info(f"当前工作目录: {os.getcwd()}")
        if hasattr(sys, '_MEIPASS'):
            logger.info(f"PyInstaller临时目录: {sys._MEIPASS}")
            
        # 记录系统信息
        logger.info(f"操作系统: {platform.system()} {platform.release()}")
        logger.info(f"系统架构: {platform.machine()}")
        logger.info(f"Python版本: {platform.python_version()}")
    except Exception as e:
        logger.error(f"获取路径信息时出错: {e}")


def main():
    """主函数：按顺序执行所有初始化步骤"""
    logger.info(f"开始初始化运行环境 (系统: {SYSTEM}, 架构: {ARCHITECTURE})")
    
    # 记录环境信息
    setup_executable_path()
    
    # 加载必要的库文件
    opus_loaded = setup_opus_early()
    if not opus_loaded:
        logger.warning("opus库加载失败，某些音频功能可能不可用")
    
    # 设置模型路径
    model_setup = setup_vosk_model_path()
    if not model_setup:
        logger.warning("Vosk模型路径设置失败，语音识别功能可能不可用")
    
    logger.info("运行时初始化完成")


# 执行主函数
if __name__ == "__main__":
    main()
else:
    # 作为钩子执行时的入口点
    main() 