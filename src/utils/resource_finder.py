import sys
from pathlib import Path
from typing import List, Optional, Union

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class ResourceFinder:
    """
    统一的资源查找器 支持开发环境、PyInstaller目录模式和单文件模式下的资源查找.
    """

    _instance = None
    _base_paths = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """
        初始化资源查找器.
        """
        if self._base_paths is None:
            self._base_paths = self._get_base_paths()
            logger.debug(
                f"资源查找器初始化，基础路径: {[str(p) for p in self._base_paths]}"
            )

    def _get_base_paths(self) -> List[Path]:
        """
        获取所有可能的基础路径 按优先级排序：项目根目录 > 当前工作目录 > 可执行文件目录 > _MEIPASS.
        """
        base_paths = []

        # 1. 项目根目录（开发环境）
        project_root = Path(__file__).parent.parent.parent
        base_paths.append(project_root)

        # 2. 当前工作目录
        cwd = Path.cwd()
        if cwd != project_root:
            base_paths.append(cwd)

        # 3. 如果是打包环境
        if getattr(sys, "frozen", False):
            # 可执行文件所在目录
            exe_dir = Path(sys.executable).parent
            if exe_dir not in base_paths:
                base_paths.append(exe_dir)

            # PyInstaller的_MEIPASS路径（单文件模式）
            if hasattr(sys, "_MEIPASS"):
                meipass_dir = Path(sys._MEIPASS)
                if meipass_dir not in base_paths:
                    base_paths.append(meipass_dir)

                # _MEIPASS的父目录（某些情况下资源在这里）
                meipass_parent = meipass_dir.parent
                if meipass_parent not in base_paths:
                    base_paths.append(meipass_parent)

            # 可执行文件的父目录（处理某些安装情况）
            exe_parent = exe_dir.parent
            if exe_parent not in base_paths:
                base_paths.append(exe_parent)

            # 支持PyInstaller 6.0.0+：检查_internal目录
            internal_dir = exe_dir / "_internal"
            if internal_dir.exists() and internal_dir not in base_paths:
                base_paths.append(internal_dir)

        return base_paths

    def find_resource(
        self, resource_path: Union[str, Path], resource_type: str = "file"
    ) -> Optional[Path]:
        """查找资源文件或目录.

        Args:
            resource_path: 相对于项目根目录的资源路径
            resource_type: 资源类型，"file" 或 "dir"

        Returns:
            找到的资源绝对路径，未找到返回None
        """
        resource_path = Path(resource_path)

        # 如果已经是绝对路径且存在，直接返回
        if resource_path.is_absolute():
            if resource_type == "file" and resource_path.is_file():
                return resource_path
            elif resource_type == "dir" and resource_path.is_dir():
                return resource_path
            else:
                return None

        # 在所有基础路径中查找
        for base_path in self._base_paths:
            full_path = base_path / resource_path

            if resource_type == "file" and full_path.is_file():
                logger.debug(f"找到文件: {full_path}")
                return full_path
            elif resource_type == "dir" and full_path.is_dir():
                logger.debug(f"找到目录: {full_path}")
                return full_path

        logger.warning(f"未找到资源: {resource_path}")
        return None

    def find_file(self, file_path: Union[str, Path]) -> Optional[Path]:
        """查找文件.

        Args:
            file_path: 相对于项目根目录的文件路径

        Returns:
            找到的文件绝对路径，未找到返回None
        """
        return self.find_resource(file_path, "file")

    def find_directory(self, dir_path: Union[str, Path]) -> Optional[Path]:
        """查找目录.

        Args:
            dir_path: 相对于项目根目录的目录路径

        Returns:
            找到的目录绝对路径，未找到返回None
        """
        return self.find_resource(dir_path, "dir")

    def find_models_dir(self) -> Optional[Path]:
        """查找models目录.

        Returns:
            找到的models目录绝对路径，未找到返回None
        """
        return self.find_directory("models")

    def find_config_dir(self) -> Optional[Path]:
        """查找config目录.

        Returns:
            找到的config目录绝对路径，未找到返回None
        """
        return self.find_directory("config")

    def find_assets_dir(self) -> Optional[Path]:
        """查找assets目录.

        Returns:
            找到的assets目录绝对路径，未找到返回None
        """
        return self.find_directory("assets")

    def find_libs_dir(self, system: str = None, arch: str = None) -> Optional[Path]:
        """查找libs目录（用于动态库）

        Args:
            system: 系统名称（如Windows、Linux、Darwin）
            arch: 架构名称（如x64、x86、arm64）

        Returns:
            找到的libs目录绝对路径，未找到返回None
        """
        # 基础libs目录
        libs_dir = self.find_directory("libs")
        if not libs_dir:
            return None

        # 如果指定了系统和架构，查找具体的子目录
        if system and arch:
            specific_dir = libs_dir / system / arch
            if specific_dir.is_dir():
                return specific_dir
        elif system:
            system_dir = libs_dir / system
            if system_dir.is_dir():
                return system_dir

        return libs_dir

    def get_project_root(self) -> Path:
        """获取项目根目录.

        Returns:
            项目根目录路径
        """
        return self._base_paths[0]

    def get_app_path(self) -> Path:
        """获取应用程序的基础路径（兼容ConfigManager的方法）

        Returns:
            应用程序基础路径
        """
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            # 如果是通过 PyInstaller 打包运行
            return Path(sys._MEIPASS)
        else:
            # 如果是开发环境运行
            return self.get_project_root()

    def list_files_in_directory(
        self, dir_path: Union[str, Path], pattern: str = "*"
    ) -> List[Path]:
        """列出目录中的文件.

        Args:
            dir_path: 目录路径
            pattern: 文件匹配模式

        Returns:
            文件路径列表
        """
        directory = self.find_directory(dir_path)
        if not directory:
            return []

        try:
            return list(directory.glob(pattern))
        except Exception as e:
            logger.error(f"列出目录文件时出错: {e}")
            return []


# 全局单例实例
resource_finder = ResourceFinder()


# 便捷函数
def find_file(file_path: Union[str, Path]) -> Optional[Path]:
    """
    查找文件的便捷函数.
    """
    return resource_finder.find_file(file_path)


def find_directory(dir_path: Union[str, Path]) -> Optional[Path]:
    """
    查找目录的便捷函数.
    """
    return resource_finder.find_directory(dir_path)


def find_models_dir() -> Optional[Path]:
    """
    查找models目录的便捷函数.
    """
    return resource_finder.find_models_dir()


def find_config_dir() -> Optional[Path]:
    """
    查找config目录的便捷函数.
    """
    return resource_finder.find_config_dir()


def find_assets_dir() -> Optional[Path]:
    """
    查找assets目录的便捷函数.
    """
    return resource_finder.find_assets_dir()


def find_libs_dir(system: str = None, arch: str = None) -> Optional[Path]:
    """
    查找libs目录的便捷函数.
    """
    return resource_finder.find_libs_dir(system, arch)


def get_project_root() -> Path:
    """
    获取项目根目录的便捷函数.
    """
    return resource_finder.get_project_root()


def get_app_path() -> Path:
    """
    获取应用程序基础路径的便捷函数.
    """
    return resource_finder.get_app_path()
