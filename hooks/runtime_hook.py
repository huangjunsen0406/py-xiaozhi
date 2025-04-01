"""
小智应用程序 PyInstaller 运行时钩子

此钩子在应用程序启动时执行，用于:
1. 初始化日志系统
2. 预加载 opus 库
3. 设置必要的环境变量
"""

import sys
import os
import ctypes
import logging
from pathlib import Path
import platform


# 配置日志系统
def setup_logging():
    """设置基本日志配置"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format
    )
    logger = logging.getLogger("RuntimeHook")
    logger.info("运行时钩子已加载")
    return logger


# 加载 opus 库
def setup_opus_early():
    """尽早加载 opus 库"""
    logger = logging.getLogger("RuntimeHook")
    logger.info("正在预加载 opus 库...")
    
    # 设置 _MEIPASS 为基准路径
    base_path = (Path(sys._MEIPASS)
                 if hasattr(sys, '_MEIPASS')
                 else Path.cwd())
    logger.info(f"应用程序基础路径: {base_path}")
    
    # 检测运行平台
    system = platform.system().lower()
    
    try:
        if system == 'windows':
            # Windows 平台
            lib_path = base_path / 'libs' / 'windows' / 'opus.dll'
            
            if lib_path.exists():
                logger.info(f"opus库文件路径: {lib_path}")
                
                # 添加到环境变量
                libs_dir = str(lib_path.parent)
                os.environ['PATH'] = (libs_dir + os.pathsep +
                                      os.environ.get('PATH', ''))
                
                # 添加DLL搜索路径 (Windows 10+)
                if hasattr(os, 'add_dll_directory'):
                    try:
                        os.add_dll_directory(libs_dir)
                        logger.info(f"已添加DLL搜索路径: {libs_dir}")
                    except Exception as e:
                        logger.error(f"添加DLL搜索路径失败: {e}")
                
                # 尝试加载
                try:
                    _ = ctypes.CDLL(str(lib_path))
                    logger.info("opus库加载成功")
                    sys._opus_loaded = True
                except Exception as e:
                    logger.error(f"opus库加载失败: {e}")
            else:
                logger.warning(f"未找到opus库文件: {lib_path}")
        
        elif system == 'darwin':
            # macOS
            lib_path = base_path / 'libs' / 'macos' / 'libopus.dylib'
            if lib_path.exists():
                logger.info(f"opus库文件路径: {lib_path}")
                
                # 设置DYLD_LIBRARY_PATH
                lib_dir = str(lib_path.parent)
                os.environ['DYLD_LIBRARY_PATH'] = (
                    lib_dir + os.pathsep +
                    os.environ.get('DYLD_LIBRARY_PATH', '')
                )
                
                try:
                    _ = ctypes.CDLL(str(lib_path))
                    logger.info("opus库加载成功")
                    sys._opus_loaded = True
                except Exception as e:
                    logger.error(f"opus库加载失败: {e}")
            else:
                logger.warning(f"未找到opus库文件: {lib_path}")
        
        else:
            # Linux
            lib_path = base_path / 'libs' / 'linux' / 'libopus.so'
            if not lib_path.exists():
                lib_path = base_path / 'libs' / 'linux' / 'libopus.so.0'
            
            if lib_path.exists():
                logger.info(f"opus库文件路径: {lib_path}")
                
                # 设置LD_LIBRARY_PATH
                lib_dir = str(lib_path.parent)
                os.environ['LD_LIBRARY_PATH'] = (
                    lib_dir + os.pathsep +
                    os.environ.get('LD_LIBRARY_PATH', '')
                )
                
                try:
                    _ = ctypes.CDLL(str(lib_path))
                    logger.info("opus库加载成功")
                    sys._opus_loaded = True
                except Exception as e:
                    logger.error(f"opus库加载失败: {e}")
            else:
                logger.warning(f"未找到opus库文件: {lib_path}")
    
    except Exception as e:
        logger.error(f"opus库初始化过程中出错: {e}")


# 预初始化Vosk模型路径
def setup_vosk_model_path():
    """设置Vosk模型路径环境变量"""
    logger = logging.getLogger("RuntimeHook")
    
    base_path = (Path(sys._MEIPASS)
                 if hasattr(sys, '_MEIPASS')
                 else Path.cwd())
    model_path = base_path / 'models' / 'vosk-model-small-cn-0.22'
    
    if model_path.exists() and model_path.is_dir():
        logger.info(f"找到Vosk模型目录: {model_path}")
        os.environ['VOSK_MODEL_PATH'] = str(model_path)
    else:
        logger.warning(f"未找到Vosk模型目录: {model_path}")


# 设置可执行文件路径
def setup_executable_path():
    """记录可执行文件路径信息"""
    logger = logging.getLogger("RuntimeHook")
    try:
        logger.info(f"可执行文件路径: {sys.executable}")
        logger.info(f"当前工作目录: {os.getcwd()}")
        if hasattr(sys, '_MEIPASS'):
            logger.info(f"PyInstaller临时目录: {sys._MEIPASS}")
    except Exception as e:
        logger.error(f"获取路径信息时出错: {e}")


# 运行所有钩子函数
logger = setup_logging()
logger.info("启动运行时初始化...")

setup_executable_path()
setup_opus_early()
setup_vosk_model_path()

logger.info("运行时初始化完成") 