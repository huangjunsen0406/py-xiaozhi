import os
import sys
import json
import glob
import ctypes
from pathlib import Path

# 获取应用程序运行路径
base_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

# 从配置文件读取模型路径
def get_model_path_from_config():
    try:
        # 对于打包环境
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            config_path = os.path.join(sys._MEIPASS, 'config', 'config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get("WAKE_WORD_MODEL_PATH", "models/vosk-model-small-cn-0.22")
        
        # 尝试从当前目录读取
        config_path = os.path.join('config', 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get("WAKE_WORD_MODEL_PATH", "models/vosk-model-small-cn-0.22")
                
        # 默认值
        return "models/vosk-model-small-cn-0.22"
    except Exception as e:
        print(f"读取配置文件获取模型路径时出错: {e}")
        return "models/vosk-model-small-cn-0.22"

# 添加必要的库路径
if hasattr(sys, '_MEIPASS'):
    # 添加 libs/windows 到 PATH 环境变量
    libs_dir = os.path.join(sys._MEIPASS, 'libs', 'windows')
    os.environ['PATH'] = libs_dir + os.pathsep + os.environ['PATH']
    
    # 尝试预加载 opus.dll
    try:
        opus_path = os.path.join(libs_dir, 'opus.dll')
        if os.path.exists(opus_path):
            opus_lib = ctypes.cdll.LoadLibrary(opus_path)
            print(f"runtime_hook: 成功加载 opus 库: {opus_path}")
    except Exception as e:
        print(f"runtime_hook: 加载 opus 库失败: {e}")
    
    # 设置 vosk 模型路径 - 从配置文件读取
    model_path = get_model_path_from_config()
    vosk_model_path = os.path.join(sys._MEIPASS, model_path)
    if os.path.exists(vosk_model_path):
        os.environ['VOSK_MODEL_PATH'] = vosk_model_path
        print(f"runtime_hook: 设置 VOSK_MODEL_PATH={vosk_model_path}")
    else:
        print(f"runtime_hook: 警告 - 模型路径不存在: {vosk_model_path}")
    
    # 确保 Python 能找到所有需要的模块
    sys.path.insert(0, sys._MEIPASS)

# 在程序启动时执行
def runtime_init():
    # 如果是 PyInstaller 打包环境
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # 尝试添加额外的 DLL 搜索路径
        vosk_dir = os.path.join(sys._MEIPASS, 'vosk')
        if os.path.exists(vosk_dir):
            try:
                os.add_dll_directory(vosk_dir)
                print(f"已添加 Vosk DLL 目录: {vosk_dir}")
            except Exception as e:
                print(f"添加 Vosk DLL 目录失败: {e}")
        else:
            print(f"Vosk 目录不存在: {vosk_dir}")

# 执行初始化
runtime_init() 