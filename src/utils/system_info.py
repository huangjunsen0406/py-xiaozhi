# 在导入 opuslib 之前处理 opus 动态库
import ctypes
import os
import sys
import platform
from pathlib import Path


def setup_opus():
    """设置 opus 动态库"""
    if hasattr(sys, '_opus_loaded'):
        print("opus 库已由其他组件加载")
        return True
    
    # 检测运行平台
    system = platform.system().lower()
    
    # Windows 平台特殊处理
    if system == 'windows':
        return setup_opus_windows()
    else:
        return setup_opus_unix(system)


def setup_opus_windows():
    """Windows 平台下设置 opus 动态库"""
    # 尝试多个可能的基准路径
    possible_base_dirs = [
        Path(__file__).parent.parent.parent,  # 项目根目录
        Path.cwd(),  # 当前工作目录
        # PyInstaller 打包路径
        (Path(getattr(sys, '_MEIPASS', ''))
         if hasattr(sys, '_MEIPASS') else None),
        # 可执行文件目录
        (Path(sys.executable).parent
         if getattr(sys, 'frozen', False) else None),
    ]
    
    lib_path = None
    libs_dir = None
    
    # 搜索可能的路径
    for base_dir in filter(None, possible_base_dirs):
        # 检查 libs/windows 路径
        temp_libs_dir = base_dir / 'libs' / 'windows'
        temp_lib_path = temp_libs_dir / 'opus.dll'
        
        if temp_lib_path.exists():
            lib_path = str(temp_lib_path)
            libs_dir = str(temp_libs_dir)
            print(f"找到opus库文件: {lib_path}")
            break
        
        # 也检查根目录
        temp_lib_path = base_dir / 'opus.dll'
        if temp_lib_path.exists():
            lib_path = str(temp_lib_path)
            libs_dir = str(base_dir)
            print(f"找到opus库文件: {lib_path}")
            break
    
    if lib_path is None:
        print("错误: 未能找到 opus 库文件，将尝试系统路径")
        try:
            # 尝试从系统路径加载
            ctypes.cdll.LoadLibrary('opus')
            print("已从系统路径加载 opus 库")
            sys._opus_loaded = True
            return True
        except Exception as e:
            print(f"从系统路径加载opus失败: {e}")
            return False
    
    # 添加DLL搜索路径
    if hasattr(os, 'add_dll_directory'):
        try:
            os.add_dll_directory(libs_dir)
            print(f"已添加DLL搜索路径: {libs_dir}")
        except Exception as e:
            print(f"添加DLL搜索路径失败: {e}")
    
    # 设置环境变量
    os.environ['PATH'] = libs_dir + os.pathsep + os.environ.get('PATH', '')
    
    # 修补库路径
    _patch_find_library('opus', lib_path)
    
    # 尝试直接加载
    try:
        # 加载DLL并存储引用以防止垃圾回收
        _ = ctypes.CDLL(lib_path)
        print(f"已成功加载 opus.dll: {lib_path}")
        sys._opus_loaded = True
        return True
    except Exception as e:
        print(f"加载 opus.dll 失败: {e}")
        return False


def setup_opus_unix(system):
    """Unix系统(Linux/macOS)下设置opus动态库"""
    try:
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后路径
            base_path = (
                Path(sys._MEIPASS)
                if hasattr(sys, '_MEIPASS')
                else Path(sys.executable).parent
            )
            
            if system == 'darwin':  # macOS
                lib_paths = [
                    base_path / 'libs' / 'macos' / 'libopus.dylib',
                    base_path / 'libopus.dylib',
                    Path('/usr/local/lib/libopus.dylib')
                ]
            else:  # Linux
                lib_paths = [
                    base_path / 'libs' / 'linux' / 'libopus.so',
                    base_path / 'libs' / 'linux' / 'libopus.so.0',
                    base_path / 'libopus.so',
                    Path('/usr/lib/libopus.so'),
                    Path('/usr/lib/libopus.so.0')
                ]
        else:
            # 开发环境路径
            base_path = Path(__file__).parent.parent.parent
            
            if system == 'darwin':  # macOS
                lib_paths = [
                    base_path / 'libs' / 'macos' / 'libopus.dylib',
                    Path('/usr/local/lib/libopus.dylib')
                ]
            else:  # Linux
                lib_paths = [
                    base_path / 'libs' / 'linux' / 'libopus.so',
                    base_path / 'libs' / 'linux' / 'libopus.so.0',
                    Path('/usr/lib/libopus.so'),
                    Path('/usr/lib/libopus.so.0')
                ]
                
        # 尝试加载所有可能的路径
        for lib_path in lib_paths:
            if lib_path.exists():
                # 加载库并存储引用以防止垃圾回收
                _ = ctypes.cdll.LoadLibrary(str(lib_path))
                print(f"成功加载 opus 库: {lib_path}")
                sys._opus_loaded = True
                return True
                
        print("未找到 opus 库文件，尝试从系统路径加载")
        
        # 尝试系统默认路径
        if system == 'darwin':
            ctypes.cdll.LoadLibrary('libopus.dylib')
        else:
            for lib_name in ['libopus.so.0', 'libopus.so']:
                try:
                    ctypes.cdll.LoadLibrary(lib_name)
                    break
                except Exception:
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