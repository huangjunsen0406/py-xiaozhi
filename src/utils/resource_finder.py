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
    _app_name = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """
        初始化资源查找器.
        """
        if self._base_paths is None:
            self._app_name = self._detect_app_name()
            self._base_paths = self._get_base_paths()
            logger.debug(
                f"资源查找器初始化，应用名: {self._app_name}, 基础路径: {[str(p) for p in self._base_paths]}"
            )

    def _detect_app_name(self) -> str:
        """
        动态检测应用名称，避免硬编码 优先级：环境变量 > .app bundle名 > 可执行文件名 > 项目目录名 > 默认值.
        """
        import os

        # 1. 环境变量指定
        env_name = os.getenv("APP_NAME") or os.getenv("XIAOZHI_APP_NAME")
        if env_name:
            logger.debug(f"从环境变量获取应用名: {env_name}")
            return env_name.lower()

        # 2. macOS .app bundle 名称
        if sys.platform == "darwin" and getattr(sys, "frozen", False):
            exe_path = Path(sys.executable)
            for p in [exe_path] + list(exe_path.parents):
                if p.name.endswith(".app"):
                    app_name = p.name[:-4]  # 去掉 .app 后缀
                    logger.debug(f"从 .app bundle 获取应用名: {app_name}")
                    return app_name.lower()

        # 3. 可执行文件名（去掉扩展名）
        if getattr(sys, "frozen", False):
            exe_name = Path(sys.executable).stem
            if exe_name and exe_name != "python":
                logger.debug(f"从可执行文件获取应用名: {exe_name}")
                return exe_name.lower()

        # 4. 项目目录名（开发环境）
        if not getattr(sys, "frozen", False):
            project_root = Path(__file__).parent.parent.parent
            project_name = project_root.name
            if project_name and not project_name.startswith("."):
                # 智能处理项目名称：py-xiaozhi -> xiaozhi, MyApp-iOS -> myapp
                app_name = project_name.lower()
                # 移除常见前缀
                for prefix in ["py-", "python-", "app-", "project-"]:
                    if app_name.startswith(prefix):
                        app_name = app_name[len(prefix) :]
                        break
                # 移除常见后缀
                for suffix in ["-app", "-project", "-ios", "-android", "-desktop"]:
                    if app_name.endswith(suffix):
                        app_name = app_name[: -len(suffix)]
                        break
                # 清理特殊字符
                app_name = app_name.replace("-", "").replace("_", "")
                logger.debug(f"从项目目录获取应用名: {project_name} -> {app_name}")
                return app_name

        # 5. 默认值
        logger.debug("使用默认应用名: xiaozhi")
        return "xiaozhi"

    def _get_base_paths(self) -> List[Path]:
        """
        获取所有可能的基础路径，优先级顺序：
        1. 开发环境：项目根目录
        2. macOS .app bundle: Contents/Resources (PyInstaller --add-data 目标)
        3. PyInstaller 其他标准路径
        4. 兜底路径：当前工作目录及其父目录
        """
        base_paths = []

        logger.debug(
            f"检测运行环境 - frozen: {getattr(sys, 'frozen', False)}, platform: {sys.platform}"
        )

        # 开发环境优先
        if not getattr(sys, "frozen", False):
            project_root = Path(__file__).parent.parent.parent
            base_paths.append(project_root)
            logger.debug(f"开发环境 - 项目根目录: {project_root}")

            cwd = Path.cwd()
            if cwd != project_root:
                base_paths.append(cwd)
                logger.debug(f"开发环境 - 当前工作目录: {cwd}")
            # 允许环境变量覆盖（最高优先级）
            self._add_env_paths(base_paths)
            return base_paths

        # === 打包环境 ===
        exe_path = Path(sys.executable).resolve()
        exe_dir = exe_path.parent
        logger.debug(f"打包环境 - 可执行文件路径: {exe_path}")
        logger.debug(f"打包环境 - 可执行文件目录: {exe_dir}")

        # macOS .app Bundle 支持 (最高优先级)
        app_root = None
        if sys.platform == "darwin":
            # 在 exe 路径及其父路径中寻找以 .app 结尾的目录
            for p in [exe_path] + list(exe_path.parents):
                if p.name.endswith(".app"):
                    app_root = p
                    logger.debug(f"找到 macOS .app bundle: {app_root}")
                    break

        if app_root is not None:
            # Contents/Resources - PyInstaller --add-data 的目标位置
            resources_dir = app_root / "Contents" / "Resources"
            if resources_dir.exists():
                base_paths.append(resources_dir)
                logger.debug(f"添加 macOS Resources 路径: {resources_dir}")

            # 也检查Frameworks目录，有些资源可能在这里
            frameworks_dir = app_root / "Contents" / "Frameworks"
            if frameworks_dir.exists():
                base_paths.append(frameworks_dir)
                logger.debug(f"添加 macOS Frameworks 路径: {frameworks_dir}")

            # Contents/MacOS - 可执行文件目录（兜底）
            if exe_dir not in base_paths:
                base_paths.append(exe_dir)
                logger.debug(f"添加 macOS MacOS 目录: {exe_dir}")
        else:
            logger.debug("未找到 macOS .app bundle")

        # PyInstaller 标准路径
        if exe_dir not in base_paths:
            base_paths.append(exe_dir)

        # PyInstaller _MEIPASS (单文件模式)
        if hasattr(sys, "_MEIPASS"):
            meipass_dir = Path(sys._MEIPASS)
            if meipass_dir not in base_paths:
                base_paths.append(meipass_dir)

        # PyInstaller _internal 目录 (6.0.0+)
        internal_dir = exe_dir / "_internal"
        if internal_dir.exists() and internal_dir not in base_paths:
            base_paths.append(internal_dir)

        # 标准安装路径支持 (系统级安装)
        self._add_system_install_paths(base_paths, exe_path)

        # 用户配置路径 (用于可写配置)
        self._add_user_config_paths(base_paths)

        # 环境变量指定路径
        self._add_env_paths(base_paths)

        # 兜底路径
        exe_parent = exe_dir.parent
        if exe_parent not in base_paths:
            base_paths.append(exe_parent)

        # 当前工作目录兜底（某些情况下从非标准位置启动）
        try:
            cwd = Path.cwd()
            if cwd not in base_paths:
                base_paths.append(cwd)
        except Exception:
            pass

        # 去重但保持顺序
        unique_paths = []
        seen = set()
        for p in base_paths:
            if p not in seen:
                unique_paths.append(p)
                seen.add(p)

        return unique_paths

    def _add_system_install_paths(self, base_paths: List[Path], exe_path: Path):
        """
        添加系统级安装路径.
        """
        if sys.platform == "darwin":
            # macOS 标准路径
            candidates = [
                exe_path.parent
                / ".."
                / "share"
                / self._app_name,  # /usr/local/share/app_name
                exe_path.parent / ".." / "Resources",  # 相对Resources
                Path("/usr/local/share") / self._app_name,
                Path("/opt") / self._app_name,
            ]
        elif sys.platform.startswith("linux"):
            # Linux 标准路径
            candidates = [
                exe_path.parent / ".." / "share" / self._app_name,
                Path("/usr/share") / self._app_name,
                Path("/usr/local/share") / self._app_name,
                Path("/opt") / self._app_name,
            ]
        else:
            # Windows
            candidates = [
                exe_path.parent / "data",
                Path("C:/ProgramData") / self._app_name,
            ]

        for candidate in candidates:
            try:
                if candidate.exists() and candidate not in base_paths:
                    base_paths.append(candidate.resolve())
            except (OSError, RuntimeError):
                pass  # 忽略无效路径

    def _add_user_config_paths(self, base_paths: List[Path]):
        """
        添加用户配置路径.
        """
        home = Path.home()

        if sys.platform == "darwin":
            candidates = [
                home / "Library" / "Application Support" / self._app_name,
                home / ".config" / self._app_name,
            ]
        elif sys.platform.startswith("linux"):
            candidates = [
                home / ".config" / self._app_name,
                home / ".local" / "share" / self._app_name,
            ]
        else:
            candidates = [
                home / "AppData" / "Local" / self._app_name,
                home / "AppData" / "Roaming" / self._app_name,
            ]

        for candidate in candidates:
            try:
                if candidate.exists() and candidate not in base_paths:
                    base_paths.append(candidate)
            except (OSError, RuntimeError):
                pass

    def _add_env_paths(self, base_paths: List[Path]):
        """
        添加环境变量指定的路径.
        """
        import os

        app_name_upper = self._app_name.upper()
        env_vars = [
            f"{app_name_upper}_DATA_DIR",
            f"{app_name_upper}_HOME",
            f"{app_name_upper}_RESOURCES_DIR",
            # 兼容旧的环境变量
            "XIAOZHI_DATA_DIR",
            "XIAOZHI_HOME",
            "XIAOZHI_RESOURCES_DIR",
        ]

        for env_var in env_vars:
            env_path = os.getenv(env_var)
            if env_path:
                try:
                    path = Path(env_path)
                    if path.exists() and path not in base_paths:
                        base_paths.insert(0, path)  # 环境变量最高优先级
                except (OSError, RuntimeError):
                    pass

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
        logger.debug(f"查找资源: {resource_path}, 类型: {resource_type}")

        # 如果已经是绝对路径且存在，直接返回
        if resource_path.is_absolute():
            if resource_type == "file" and resource_path.is_file():
                logger.debug(f"使用绝对路径找到文件: {resource_path}")
                return resource_path
            elif resource_type == "dir" and resource_path.is_dir():
                logger.debug(f"使用绝对路径找到目录: {resource_path}")
                return resource_path
            else:
                logger.debug(f"绝对路径不存在: {resource_path}")
                return None

        # 在所有基础路径中查找
        logger.debug(f"在 {len(self._base_paths)} 个基础路径中查找资源")
        for i, base_path in enumerate(self._base_paths):
            full_path = base_path / resource_path
            logger.debug(f"尝试路径 {i+1}: {full_path}")

            if resource_type == "file" and full_path.is_file():
                logger.info(f"✓ 找到文件: {full_path}")
                return full_path
            elif resource_type == "dir" and full_path.is_dir():
                logger.info(f"✓ 找到目录: {full_path}")
                return full_path

        logger.warning(f"✗ 未找到资源: {resource_path}")
        logger.debug(f"搜索的基础路径: {[str(p) for p in self._base_paths]}")
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
        # 开发环境：直接返回源码项目根目录
        if not getattr(sys, "frozen", False):
            return Path(__file__).parent.parent.parent

        # 打包环境：优先 macOS .app 的 Resources，其次单文件解包目录，最后可执行文件目录
        exe_path = Path(sys.executable).resolve()
        exe_dir = exe_path.parent

        if sys.platform == "darwin":
            for p in [exe_path] + list(exe_path.parents):
                if p.name.endswith(".app"):
                    resources_dir = p / "Contents" / "Resources"
                    if resources_dir.exists():
                        return resources_dir
                    break

        if hasattr(sys, "_MEIPASS"):
            try:
                meipass_dir = Path(sys._MEIPASS)
                if meipass_dir.exists():
                    return meipass_dir
            except Exception:
                pass

        return exe_dir

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

    def get_user_data_dir(self, create: bool = True) -> Path:
        """获取用户数据目录，用于存储可写文件.

        Args:
            create: 是否创建目录（如果不存在）

        Returns:
            用户数据目录路径
        """
        if sys.platform == "win32":  # Windows
            data_dir = Path.home() / "AppData" / "Local" / self._app_name
        elif sys.platform == "darwin":  # macOS
            data_dir = Path.home() / "Library" / "Application Support" / self._app_name
        else:  # Linux and others
            data_dir = Path.home() / ".local" / "share" / self._app_name

        if create:
            try:
                data_dir.mkdir(parents=True, exist_ok=True)
                logger.debug(f"用户数据目录: {data_dir}")
            except OSError as e:
                logger.error(f"创建用户数据目录失败: {e}")
                # 兜底方案：使用临时目录
                import tempfile

                data_dir = Path(tempfile.gettempdir()) / self._app_name
                data_dir.mkdir(parents=True, exist_ok=True)
                logger.warning(f"使用临时目录作为用户数据目录: {data_dir}")

        return data_dir

    def get_user_cache_dir(self, create: bool = True) -> Path:
        """获取用户缓存目录.

        Args:
            create: 是否创建目录（如果不存在）

        Returns:
            用户缓存目录路径
        """
        cache_dir = self.get_user_data_dir(create=False) / "cache"

        if create:
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                logger.debug(f"用户缓存目录: {cache_dir}")
            except OSError as e:
                logger.error(f"创建用户缓存目录失败: {e}")

        return cache_dir

    def get_app_name(self) -> str:
        """获取应用名称.

        Returns:
            检测到的应用名称
        """
        return self._app_name

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


def get_user_data_dir(create: bool = True) -> Path:
    """
    获取用户数据目录的便捷函数.
    """
    return resource_finder.get_user_data_dir(create)


def get_user_cache_dir(create: bool = True) -> Path:
    """
    获取用户缓存目录的便捷函数.
    """
    return resource_finder.get_user_cache_dir(create)


def get_app_name() -> str:
    """
    获取应用名称的便捷函数.
    """
    return resource_finder.get_app_name()
