# 在导入 opuslib 之前处理 opus 动态库
import ctypes
import os
import sys
import platform


def setup_opus():
    """设置 opus 动态库"""
    if hasattr(sys, '_opus_loaded'):
        print("opus 库已由其他组件加载")
        return True
    
    # 检测运行平台
    system = platform.system().lower()
    
    try:
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后路径
            base_path = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
            
            if system == 'windows':
                lib_paths = [
                    os.path.join(base_path, 'libs', 'windows', 'opus.dll'),
                    os.path.join(base_path, 'opus.dll')
                ]
            elif system == 'darwin':  # macOS
                lib_paths = [
                    os.path.join(base_path, 'libs', 'macos', 'libopus.dylib'),
                    os.path.join(base_path, 'libopus.dylib'),
                    '/usr/local/lib/libopus.dylib'
                ]
            else:  # Linux
                lib_paths = [
                    os.path.join(base_path, 'libs', 'linux', 'libopus.so'),
                    os.path.join(base_path, 'libs', 'linux', 'libopus.so.0'),
                    os.path.join(base_path, 'libopus.so'),
                    '/usr/lib/libopus.so',
                    '/usr/lib/libopus.so.0'
                ]
                
            # 尝试加载所有可能的路径
            for lib_path in lib_paths:
                if os.path.exists(lib_path):
                    opus_lib = ctypes.cdll.LoadLibrary(lib_path)
                    print(f"成功加载 opus 库: {lib_path}")
                    sys._opus_loaded = True
                    return True
                    
            print("未找到 opus 库文件，尝试从系统路径加载")
            
            # 尝试系统默认路径
            if system == 'windows':
                ctypes.cdll.LoadLibrary('opus')
            elif system == 'darwin':
                ctypes.cdll.LoadLibrary('libopus.dylib')
            else:
                for lib_name in ['libopus.so.0', 'libopus.so']:
                    try:
                        ctypes.cdll.LoadLibrary(lib_name)
                        break
                    except:
                        continue
                        
            print("已从系统路径加载 opus 库")
            sys._opus_loaded = True
            return True
            
    except Exception as e:
        print(f"加载 opus 库失败: {e}")
        return False


def _patch_find_library(lib_name, lib_path):
    """修补 ctypes.util.find_library 函数"""
    import ctypes.util
    original_find_library = ctypes.util.find_library

    def patched_find_library(name):
        if name == lib_name:
            return lib_path
        return original_find_library(name)

    ctypes.util.find_library = patched_find_library