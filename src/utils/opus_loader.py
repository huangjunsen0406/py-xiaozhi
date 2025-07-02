# 在导入 opuslib 之前处理 opus 动态库
import ctypes
import os
import platform
import shutil
import sys
from pathlib import Path

# 获取日志记录器
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


# 平台和架构常量定义
WINDOWS = "windows"
MACOS = "darwin"
LINUX = "linux"

# 库文件信息
LIB_INFO = {
    WINDOWS: {"name": "opus.dll", "system_name": "opus"},
    MACOS: {"name": "libopus.dylib", "system_name": "libopus.dylib"},
    LINUX: {"name": "libopus.so", "system_name": ["libopus.so.0", "libopus.so"]},
}

# 目录结构定义 - 根据实际目录结构定义路径
DIR_STRUCTURE = {
    WINDOWS: {"arch": "x86_64", "path": "libs/libopus/win/x86_64"},
    MACOS: {
        "arch": {"arm": "arm64", "intel": "x64"},
        "path": "libs/libopus/mac/{arch}",
    },
    LINUX: {
        "arch": {"arm": "arm64", "intel": "x64"},
        "path": "libs/libopus/linux/{arch}",
    },
}


def get_system_info():
    """
    获取当前系统信息.
    """
    system = platform.system().lower()
    architecture = platform.machine().lower()

    # 标准化系统名称
    if system == "windows" or system.startswith("win"):
        system = WINDOWS
    elif system == "darwin":
        system = MACOS
    elif system.startswith("linux"):
        system = LINUX

    # 标准化架构名称
    is_arm = "arm" in architecture or "aarch64" in architecture

    if system == MACOS:
        arch_name = DIR_STRUCTURE[MACOS]["arch"]["arm" if is_arm else "intel"]
    elif system == WINDOWS:
        arch_name = DIR_STRUCTURE[WINDOWS]["arch"]
    else:  # Linux
        arch_name = DIR_STRUCTURE[LINUX]["arch"]["arm" if is_arm else "intel"]

    return system, arch_name


def get_search_paths(system, arch_name):
    """
    获取库文件搜索路径列表（使用统一的资源查找器）
    """
    from .resource_finder import find_libs_dir, get_project_root

    lib_name = LIB_INFO[system]["name"]
    search_paths = []

    # 映射系统名称到目录名称
    system_dir_map = {WINDOWS: "win", MACOS: "mac", LINUX: "linux"}

    system_dir = system_dir_map.get(system)

    # 首先尝试查找特定平台和架构的libs目录
    if system_dir:
        specific_libs_dir = find_libs_dir(f"libopus/{system_dir}", arch_name)
        if specific_libs_dir:
            search_paths.append((specific_libs_dir, lib_name))
            logger.debug(f"找到特定平台架构libs目录: {specific_libs_dir}")

    # 然后查找特定平台的libs目录
    if system_dir:
        platform_libs_dir = find_libs_dir(f"libopus/{system_dir}")
        if platform_libs_dir:
            search_paths.append((platform_libs_dir, lib_name))
            logger.debug(f"找到特定平台libs目录: {platform_libs_dir}")

    # 查找通用libs目录
    general_libs_dir = find_libs_dir()
    if general_libs_dir:
        search_paths.append((general_libs_dir, lib_name))
        logger.debug(f"添加通用libs目录: {general_libs_dir}")

    # 添加项目根目录作为最后的备选
    project_root = get_project_root()
    search_paths.append((project_root, lib_name))

    # 打印所有搜索路径，帮助调试
    for dir_path, filename in search_paths:
        full_path = dir_path / filename
        logger.debug(f"搜索路径: {full_path} (存在: {full_path.exists()})")
    return search_paths


def find_system_opus():
    """
    从系统路径查找opus库.
    """
    system, _ = get_system_info()
    lib_path = None

    try:
        # 获取系统上opus库的名称
        lib_names = LIB_INFO[system]["system_name"]
        if not isinstance(lib_names, list):
            lib_names = [lib_names]

        # 尝试加载每个可能的名称
        for lib_name in lib_names:
            try:
                # 导入ctypes.util以使用find_library函数
                import ctypes.util

                system_lib_path = ctypes.util.find_library(lib_name)

                if system_lib_path:
                    lib_path = system_lib_path
                    logger.info(f"在系统路径中找到opus库: {lib_path}")
                    break
                else:
                    # 直接尝试加载库名
                    ctypes.cdll.LoadLibrary(lib_name)
                    lib_path = lib_name
                    logger.info(f"直接加载系统opus库: {lib_name}")
                    break
            except Exception as e:
                logger.debug(f"加载系统库 {lib_name} 失败: {e}")
                continue

    except Exception as e:
        logger.error(f"查找系统opus库失败: {e}")

    return lib_path


def copy_opus_to_project(system_lib_path):
    """
    将系统库复制到项目目录.
    """
    from .resource_finder import get_project_root

    system, arch_name = get_system_info()

    if not system_lib_path:
        logger.error("无法复制opus库：系统库路径为空")
        return None

    try:
        # 使用resource_finder获取项目根目录
        project_root = get_project_root()

        # 获取目标目录路径 - 使用实际目录结构
        if system == MACOS:
            target_path = DIR_STRUCTURE[MACOS]["path"].format(arch=arch_name)
        elif system == WINDOWS:
            target_path = DIR_STRUCTURE[WINDOWS]["path"]
        else:  # Linux
            target_path = DIR_STRUCTURE[LINUX]["path"]

        target_dir = project_root / target_path

        # 创建目标目录(如果不存在)
        target_dir.mkdir(parents=True, exist_ok=True)

        # 确定目标文件名
        lib_name = LIB_INFO[system]["name"]
        target_file = target_dir / lib_name

        # 复制文件
        shutil.copy2(system_lib_path, target_file)
        logger.info(f"已将opus库从 {system_lib_path} 复制到 {target_file}")

        return str(target_file)

    except Exception as e:
        logger.error(f"复制opus库到项目目录失败: {e}")
        return None


def setup_opus():
    """
    设置opus动态库.
    """
    # 检查是否已经由runtime_hook加载
    if hasattr(sys, "_opus_loaded"):
        logger.info("opus库已由运行时钩子加载")
        return True

    # 获取当前系统信息
    system, arch_name = get_system_info()
    logger.info(f"当前系统: {system}, 架构: {arch_name}")

    # 构建搜索路径
    search_paths = get_search_paths(system, arch_name)

    # 查找本地库文件
    lib_path = None
    lib_dir = None

    for dir_path, file_name in search_paths:
        full_path = dir_path / file_name
        if full_path.exists():
            lib_path = str(full_path)
            lib_dir = str(dir_path)
            logger.info(f"找到opus库文件: {lib_path}")
            break

    # 如果本地没找到，尝试从系统查找
    if lib_path is None:
        logger.warning("本地未找到opus库文件，尝试从系统路径加载")
        system_lib_path = find_system_opus()

        if system_lib_path:
            # 首次尝试直接使用系统库
            try:
                _ = ctypes.cdll.LoadLibrary(system_lib_path)
                logger.info(f"已从系统路径加载opus库: {system_lib_path}")
                sys._opus_loaded = True
                return True
            except Exception as e:
                logger.warning(f"加载系统opus库失败: {e}，尝试复制到项目目录")

            # 如果直接加载失败，尝试复制到项目目录
            lib_path = copy_opus_to_project(system_lib_path)
            if lib_path:
                lib_dir = str(Path(lib_path).parent)
            else:
                logger.error("无法找到或复制opus库文件")
                return False
        else:
            logger.error("在系统中也未找到opus库文件")
            return False

    # Windows平台特殊处理
    if system == WINDOWS and lib_dir:
        # 添加DLL搜索路径
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(lib_dir)
                logger.debug(f"已添加DLL搜索路径: {lib_dir}")
            except Exception as e:
                logger.warning(f"添加DLL搜索路径失败: {e}")

        # 设置环境变量
        os.environ["PATH"] = lib_dir + os.pathsep + os.environ.get("PATH", "")

    # 修补库路径
    _patch_find_library("opus", lib_path)

    # 尝试加载库
    try:
        # 加载DLL并存储引用以防止垃圾回收
        _ = ctypes.CDLL(lib_path)
        logger.info(f"成功加载opus库: {lib_path}")
        sys._opus_loaded = True
        return True
    except Exception as e:
        logger.error(f"加载opus库失败: {e}")
        return False


def _patch_find_library(lib_name, lib_path):
    """
    修补ctypes.util.find_library函数.
    """
    import ctypes.util

    original_find_library = ctypes.util.find_library

    def patched_find_library(name):
        if name == lib_name:
            return lib_path
        return original_find_library(name)

    ctypes.util.find_library = patched_find_library
