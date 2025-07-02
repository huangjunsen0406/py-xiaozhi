import platform
import re
import shutil
import subprocess
from functools import wraps
from typing import Any, Callable, List, Optional

from src.utils.logging_config import get_logger


class VolumeController:
    """
    跨平台音量控制器.
    """

    # 默认音量常量
    DEFAULT_VOLUME = 70

    # 平台特定的方法映射
    PLATFORM_INIT = {
        "Windows": "_init_windows",
        "Darwin": "_init_macos",
        "Linux": "_init_linux",
    }

    VOLUME_METHODS = {
        "Windows": ("_get_windows_volume", "_set_windows_volume"),
        "Darwin": ("_get_macos_volume", "_set_macos_volume"),
        "Linux": ("_get_linux_volume", "_set_linux_volume"),
    }

    LINUX_VOLUME_METHODS = {
        "pactl": ("_get_pactl_volume", "_set_pactl_volume"),
        "wpctl": ("_get_wpctl_volume", "_set_wpctl_volume"),
        "amixer": ("_get_amixer_volume", "_set_amixer_volume"),
        "alsamixer": (None, "_set_alsamixer_volume"),
    }

    # 平台特定的模块依赖
    PLATFORM_MODULES = {
        "Windows": {
            "pycaw": "pycaw.pycaw",
            "comtypes": "comtypes",
            "ctypes": "ctypes",
        },
        "Darwin": {
            "applescript": "applescript",
        },
        "Linux": {},
    }

    def __init__(self):
        """
        初始化音量控制器.
        """
        self.logger = get_logger("VolumeController")
        self.system = platform.system()
        self.is_arm = platform.machine().startswith(("arm", "aarch"))
        self.linux_tool = None
        self._module_cache = {}  # 模块缓存

        # 初始化特定平台的控制器
        init_method_name = self.PLATFORM_INIT.get(self.system)
        if init_method_name:
            init_method = getattr(self, init_method_name)
            init_method()
        else:
            self.logger.warning(f"不支持的操作系统: {self.system}")
            raise NotImplementedError(f"不支持的操作系统: {self.system}")

    def _lazy_import(self, module_name: str, attr: str = None) -> Any:
        """懒加载模块，支持缓存和属性导入.

        Args:
            module_name: 模块名称
            attr: 可选，模块中的属性名

        Returns:
            导入的模块或属性
        """
        if module_name in self._module_cache:
            module = self._module_cache[module_name]
        else:
            try:
                module = __import__(
                    module_name, fromlist=["*"] if "." in module_name else []
                )
                self._module_cache[module_name] = module
            except ImportError as e:
                self.logger.warning(f"导入模块 {module_name} 失败: {e}")
                raise

        if attr:
            return getattr(module, attr)
        return module

    def _safe_execute(self, func_name: str, default_return: Any = None) -> Callable:
        """
        安全执行函数的装饰器.
        """

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    self.logger.warning(f"{func_name}失败: {e}")
                    return default_return

            return wrapper

        return decorator

    def _run_command(
        self, cmd: List[str], check: bool = False
    ) -> Optional[subprocess.CompletedProcess]:
        """
        通用命令执行方法.
        """
        try:
            return subprocess.run(cmd, capture_output=True, text=True, check=check)
        except Exception as e:
            self.logger.debug(f"执行命令失败 {' '.join(cmd)}: {e}")
            return None

    def _init_windows(self) -> None:
        """
        初始化Windows音量控制.
        """
        try:
            # 使用懒加载导入所需模块
            POINTER = self._lazy_import("ctypes", "POINTER")
            cast = self._lazy_import("ctypes", "cast")
            CLSCTX_ALL = self._lazy_import("comtypes", "CLSCTX_ALL")
            AudioUtilities = self._lazy_import("pycaw.pycaw", "AudioUtilities")
            IAudioEndpointVolume = self._lazy_import(
                "pycaw.pycaw", "IAudioEndpointVolume"
            )

            self.devices = AudioUtilities.GetSpeakers()
            interface = self.devices.Activate(
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None
            )
            self.volume_control = cast(interface, POINTER(IAudioEndpointVolume))
            self.logger.debug("Windows音量控制初始化成功")
        except Exception as e:
            self.logger.error(f"Windows音量控制初始化失败: {e}")
            raise

    def _init_macos(self) -> None:
        """
        初始化macOS音量控制.
        """
        try:
            applescript = self._lazy_import("applescript")

            # 测试是否可以访问音量控制
            result = applescript.run("get volume settings")
            if not result or result.code != 0:
                raise Exception("无法访问macOS音量控制")
            self.logger.debug("macOS音量控制初始化成功")
        except Exception as e:
            self.logger.error(f"macOS音量控制初始化失败: {e}")
            raise

    def _init_linux(self) -> None:
        """
        初始化Linux音量控制.
        """
        # 按优先级检查工具
        linux_tools = ["pactl", "wpctl", "amixer"]
        for tool in linux_tools:
            if shutil.which(tool):
                self.linux_tool = tool
                break

        # 检查alsamixer作为备选
        if not self.linux_tool and shutil.which("alsamixer") and shutil.which("expect"):
            self.linux_tool = "alsamixer"

        if not self.linux_tool:
            self.logger.error("未找到可用的Linux音量控制工具")
            raise Exception("未找到可用的Linux音量控制工具")

        self.logger.debug(f"Linux音量控制初始化成功，使用: {self.linux_tool}")

    def get_volume(self) -> int:
        """
        获取当前音量 (0-100)
        """
        get_method_name, _ = self.VOLUME_METHODS.get(self.system, (None, None))
        if not get_method_name:
            return self.DEFAULT_VOLUME

        get_method = getattr(self, get_method_name)
        return get_method()

    def set_volume(self, volume: int) -> None:
        """
        设置音量 (0-100)
        """
        # 确保音量在有效范围内
        volume = max(0, min(100, volume))

        _, set_method_name = self.VOLUME_METHODS.get(self.system, (None, None))
        if set_method_name:
            set_method = getattr(self, set_method_name)
            set_method(volume)

    @property
    def _get_windows_volume(self) -> Callable[[], int]:
        @self._safe_execute("获取Windows音量", self.DEFAULT_VOLUME)
        def get_volume():
            volume_scalar = self.volume_control.GetMasterVolumeLevelScalar()
            return int(volume_scalar * 100)

        return get_volume

    @property
    def _set_windows_volume(self) -> Callable[[int], None]:
        @self._safe_execute("设置Windows音量")
        def set_volume(volume):
            self.volume_control.SetMasterVolumeLevelScalar(volume / 100.0, None)

        return set_volume

    @property
    def _get_macos_volume(self) -> Callable[[], int]:
        @self._safe_execute("获取macOS音量", self.DEFAULT_VOLUME)
        def get_volume():
            applescript = self._lazy_import("applescript")
            result = applescript.run("output volume of (get volume settings)")
            if result and result.out:
                return int(result.out.strip())
            return self.DEFAULT_VOLUME

        return get_volume

    @property
    def _set_macos_volume(self) -> Callable[[int], None]:
        @self._safe_execute("设置macOS音量")
        def set_volume(volume):
            applescript = self._lazy_import("applescript")
            applescript.run(f"set volume output volume {volume}")

        return set_volume

    def _get_linux_volume(self) -> int:
        """
        获取Linux音量.
        """
        get_method_name, _ = self.LINUX_VOLUME_METHODS.get(
            self.linux_tool, (None, None)
        )
        if not get_method_name:
            return self.DEFAULT_VOLUME

        get_method = getattr(self, get_method_name)
        return get_method()

    def _set_linux_volume(self, volume: int) -> None:
        """
        设置Linux音量.
        """
        _, set_method_name = self.LINUX_VOLUME_METHODS.get(
            self.linux_tool, (None, None)
        )
        if set_method_name:
            set_method = getattr(self, set_method_name)
            set_method(volume)

    @property
    def _get_pactl_volume(self) -> Callable[[], int]:
        @self._safe_execute("通过pactl获取音量", self.DEFAULT_VOLUME)
        def get_volume():
            result = self._run_command(["pactl", "list", "sinks"])
            if result and result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "Volume:" in line and "front-left:" in line:
                        match = re.search(r"(\d+)%", line)
                        if match:
                            return int(match.group(1))
            return self.DEFAULT_VOLUME

        return get_volume

    @property
    def _set_pactl_volume(self) -> Callable[[int], None]:
        @self._safe_execute("通过pactl设置音量")
        def set_volume(volume):
            self._run_command(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{volume}%"]
            )

        return set_volume

    @property
    def _get_wpctl_volume(self) -> Callable[[], int]:
        @self._safe_execute("通过wpctl获取音量", self.DEFAULT_VOLUME)
        def get_volume():
            result = self._run_command(
                ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], check=True
            )
            if result:
                return int(float(result.stdout.split(" ")[1]) * 100)
            return self.DEFAULT_VOLUME

        return get_volume

    @property
    def _set_wpctl_volume(self) -> Callable[[int], None]:
        @self._safe_execute("通过wpctl设置音量")
        def set_volume(volume):
            self._run_command(
                ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{volume}%"],
                check=True,
            )

        return set_volume

    @property
    def _get_amixer_volume(self) -> Callable[[], int]:
        @self._safe_execute("通过amixer获取音量", self.DEFAULT_VOLUME)
        def get_volume():
            result = self._run_command(["amixer", "get", "Master"])
            if result and result.returncode == 0:
                match = re.search(r"(\d+)%", result.stdout)
                if match:
                    return int(match.group(1))
            return self.DEFAULT_VOLUME

        return get_volume

    @property
    def _set_amixer_volume(self) -> Callable[[int], None]:
        @self._safe_execute("通过amixer设置音量")
        def set_volume(volume):
            self._run_command(["amixer", "sset", "Master", f"{volume}%"])

        return set_volume

    @property
    def _set_alsamixer_volume(self) -> Callable[[int], None]:
        @self._safe_execute("通过alsamixer设置音量")
        def set_volume(volume):
            script = f"""
            spawn alsamixer
            send "m"
            send "{volume}"
            send "%"
            send "q"
            expect eof
            """
            self._run_command(["expect", "-c", script])

        return set_volume

    @staticmethod
    def check_dependencies() -> bool:
        """
        检查并报告缺少的依赖.
        """
        system = platform.system()
        missing = []

        # 检查Python模块依赖
        VolumeController._check_python_modules(system, missing)

        # 检查Linux工具依赖
        if system == "Linux":
            VolumeController._check_linux_tools(missing)

        # 报告缺少的依赖
        return VolumeController._report_missing_dependencies(system, missing)

    @staticmethod
    def _check_python_modules(system: str, missing: List[str]) -> None:
        """
        检查Python模块依赖.
        """
        if system == "Windows":
            for module in ["pycaw", "comtypes"]:
                try:
                    __import__(module)
                except ImportError:
                    missing.append(module)
        elif system == "Darwin":  # macOS
            try:
                __import__("applescript")
            except ImportError:
                missing.append("applescript")

    @staticmethod
    def _check_linux_tools(missing: List[str]) -> None:
        """
        检查Linux工具依赖.
        """
        tools = ["pactl", "wpctl", "amixer", "alsamixer"]
        found = any(shutil.which(tool) for tool in tools)
        if not found:
            missing.append("pulseaudio-utils、wireplumber 或 alsa-utils")

    @staticmethod
    def _report_missing_dependencies(system: str, missing: List[str]) -> bool:
        """
        报告缺少的依赖.
        """
        if missing:
            print(f"警告: 音量控制需要以下依赖，但未找到: {', '.join(missing)}")
            print("请使用以下命令安装缺少的依赖:")
            if system in ["Windows", "Darwin"]:
                print("pip install " + " ".join(missing))
            elif system == "Linux":
                print("sudo apt-get install " + " ".join(missing))
            return False
        return True
