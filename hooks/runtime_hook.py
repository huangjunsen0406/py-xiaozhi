import os
import sys
import json
import glob
import ctypes
import platform
from pathlib import Path

# 获取应用程序运行路径
base_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

# 从配置文件读取模型配置
def get_model_config_from_file():
    try:
        # 对于打包环境
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            config_path = os.path.join(sys._MEIPASS, 'config', 'config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    use_wake_word = config.get("USE_WAKE_WORD", True)
                    model_path = config.get("WAKE_WORD_MODEL_PATH", "models/vosk-model-small-cn-0.22")
                    return use_wake_word, model_path
        
        # 尝试从当前目录读取
        config_path = os.path.join('config', 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                use_wake_word = config.get("USE_WAKE_WORD", True)
                model_path = config.get("WAKE_WORD_MODEL_PATH", "models/vosk-model-small-cn-0.22")
                return use_wake_word, model_path
                
        # 默认值
        return True, "models/vosk-model-small-cn-0.22"
    except Exception as e:
        print(f"读取配置文件获取模型配置时出错: {e}")
        return True, "models/vosk-model-small-cn-0.22"

# 添加必要的库路径
if hasattr(sys, '_MEIPASS'):
    # 获取系统类型
    system = platform.system().lower()
    
    # 根据不同平台添加相应的库路径
    if system == 'windows':
        libs_dir = os.path.join(sys._MEIPASS, 'libs', 'windows')
        opus_lib_name = 'opus.dll'
    elif system == 'darwin':  # macOS
        libs_dir = os.path.join(sys._MEIPASS, 'libs', 'macos')
        opus_lib_name = 'libopus.dylib'
    else:  # Linux
        libs_dir = os.path.join(sys._MEIPASS, 'libs', 'linux')
        opus_lib_name = 'libopus.so'  # 可能需要尝试不同的版本
    
    # 添加库目录到环境变量
    if os.path.exists(libs_dir):
        os.environ['PATH'] = libs_dir + os.pathsep + os.environ['PATH']
        
        # 在 Linux 下，还需要添加 LD_LIBRARY_PATH
        if system == 'linux':
            os.environ['LD_LIBRARY_PATH'] = libs_dir + os.pathsep + os.environ.get('LD_LIBRARY_PATH', '')
    
    # 尝试预加载 opus 库
    try:
        opus_path = os.path.join(libs_dir, opus_lib_name)
        if os.path.exists(opus_path):
            opus_lib = ctypes.cdll.LoadLibrary(opus_path)
            print(f"runtime_hook: 成功加载 opus 库: {opus_path}")
    except Exception as e:
        print(f"runtime_hook: 加载 opus 库失败: {e}")
    
    # 获取唤醒词配置
    use_wake_word, model_path = get_model_config_from_file()
    
    # 只有在需要使用唤醒词时才设置模型路径
    if use_wake_word:
        vosk_model_path = os.path.join(sys._MEIPASS, model_path)
        if os.path.exists(vosk_model_path):
            os.environ['VOSK_MODEL_PATH'] = vosk_model_path
            print(f"runtime_hook: 设置 VOSK_MODEL_PATH={vosk_model_path}")
        else:
            print(f"runtime_hook: 警告 - 模型路径不存在: {vosk_model_path}")
    else:
        print("runtime_hook: 配置为不使用唤醒词，跳过设置模型路径")
    
    # 确保 Python 能找到所有需要的模块
    sys.path.insert(0, sys._MEIPASS)

# 在程序启动时执行
def runtime_init():
    # 如果是 PyInstaller 打包环境
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # 获取系统类型
        system = platform.system().lower()
        
        # 查找 Vosk 相关的 DLL/SO 文件
        vosk_dir = os.path.join(sys._MEIPASS, 'vosk')
        if os.path.exists(vosk_dir):
            try:
                # Windows 需要使用 add_dll_directory
                if system == 'windows' and hasattr(os, 'add_dll_directory'):
                    os.add_dll_directory(vosk_dir)
                    print(f"已添加 Vosk DLL 目录: {vosk_dir}")
                # Linux/macOS 设置 LD_LIBRARY_PATH
                elif system in ('linux', 'darwin'):
                    os.environ['LD_LIBRARY_PATH'] = vosk_dir + os.pathsep + os.environ.get('LD_LIBRARY_PATH', '')
                    print(f"已添加 Vosk 库目录到 LD_LIBRARY_PATH: {vosk_dir}")
            except Exception as e:
                print(f"添加 Vosk 库目录失败: {e}")
        else:
            print(f"Vosk 目录不存在: {vosk_dir}")
            
            # 尝试查找其他可能的位置
            for possible_dir in [
                os.path.join(sys._MEIPASS, 'lib', 'vosk'),
                os.path.join(sys._MEIPASS, 'site-packages', 'vosk'),
                os.path.join(sys._MEIPASS, 'Lib', 'site-packages', 'vosk'),
                # 如果 vosk 模块已经被打包到根目录下
                os.path.dirname(sys._MEIPASS),
            ]:
                if os.path.exists(possible_dir):
                    try:
                        if system == 'windows' and hasattr(os, 'add_dll_directory'):
                            os.add_dll_directory(possible_dir)
                            print(f"已添加替代 Vosk DLL 目录: {possible_dir}")
                        elif system in ('linux', 'darwin'):
                            os.environ['LD_LIBRARY_PATH'] = possible_dir + os.pathsep + os.environ.get('LD_LIBRARY_PATH', '')
                            print(f"已添加替代 Vosk 库目录到 LD_LIBRARY_PATH: {possible_dir}")
                        break
                    except Exception as e:
                        print(f"添加替代 Vosk 库目录失败: {e}")
            
            # 尝试直接从系统 PATH 中加载
            print("尝试从系统路径中加载 Vosk 库")

# 执行初始化
runtime_init() 