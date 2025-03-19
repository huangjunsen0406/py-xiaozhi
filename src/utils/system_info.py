# 在导入 opuslib 之前处理 opus 动态库
import ctypes
import os
import sys


def setup_opus():
    """设置 opus 动态库"""
    if hasattr(sys, '_opus_loaded'):
        print("opus 库已由其他组件加载")
        return True
        
    # 获取 opus.dll 的路径
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的路径
        if hasattr(sys, '_MEIPASS'):
            opus_path = os.path.join(sys._MEIPASS, 'libs', 'windows', 'opus.dll')
        else:
            # 其他打包工具可能使用不同的方式
            opus_path = os.path.join(os.path.dirname(sys.executable), 'libs', 'windows', 'opus.dll')
    else:
        # 开发环境路径
        # 假设 system_info.py 在 src/utils 目录下，需要向上三级才能到达项目根目录
        opus_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                               'libs', 'windows', 'opus.dll')
    
    # 检查文件是否存在
    if os.path.exists(opus_path):
        print(f"找到 opus 库文件: {opus_path}")
    else:
        print(f"警告: opus 库文件不存在于路径: {opus_path}")
        # 尝试在其他可能的位置查找
        if getattr(sys, 'frozen', False):
            alternate_path = os.path.join(os.path.dirname(sys.executable), 'opus.dll')
            if os.path.exists(alternate_path):
                opus_path = alternate_path
                print(f"在替代位置找到 opus 库文件: {opus_path}")
    
    # 预加载 opus.dll
    try:
        opus_lib = ctypes.cdll.LoadLibrary(opus_path)
        print(f"成功加载 opus 库: {opus_path}")
        sys._opus_loaded = True
        return True
    except Exception as e:
        print(f"加载 opus 库失败: {e}")
        
        # 尝试使用系统路径查找
        try:
            if sys.platform == 'win32':
                ctypes.cdll.LoadLibrary('opus')
                print("已从系统路径加载 opus 库")
                sys._opus_loaded = True
                return True
            elif sys.platform == 'darwin':  # macOS
                ctypes.cdll.LoadLibrary('libopus.dylib')
                print("已从系统路径加载 libopus.dylib")
                sys._opus_loaded = True
                return True
            else:  # Linux 和其他 Unix 系统
                # 尝试几种常见的库名称
                for lib_name in ['libopus.so.0', 'libopus.so', 'libopus.so.0.8.0']:
                    try:
                        ctypes.cdll.LoadLibrary(lib_name)
                        print(f"已从系统路径加载 {lib_name}")
                        sys._opus_loaded = True
                        return True
                    except:
                        continue
        except Exception as e2:
            print(f"从系统路径加载 opus 库失败: {e2}")
        
        print("确保 opus 动态库已正确安装或位于正确的位置")
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