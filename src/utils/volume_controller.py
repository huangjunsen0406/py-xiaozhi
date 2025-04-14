import logging
import platform
import subprocess
import re
import shutil


class VolumeController:
    """跨平台音量控制器"""
    
    def __init__(self):
        self.logger = logging.getLogger("VolumeController")
        self.system = platform.system()
        self.is_arm = platform.machine().startswith(('arm', 'aarch'))
        
        # 初始化特定平台的控制器
        if self.system == "Windows":
            self._init_windows()
        elif self.system == "Darwin":  # macOS
            self._init_macos()
        elif self.system == "Linux":
            self._init_linux()
        else:
            self.logger.warning(f"不支持的操作系统: {self.system}")
            raise NotImplementedError(f"不支持的操作系统: {self.system}")
    
    def _init_windows(self):
        """初始化Windows音量控制"""
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            
            self.devices = AudioUtilities.GetSpeakers()
            interface = self.devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self.volume_control = cast(interface, POINTER(IAudioEndpointVolume))
            self.logger.debug("Windows音量控制初始化成功")
        except Exception as e:
            self.logger.error(f"Windows音量控制初始化失败: {e}")
            raise
    
    def _init_macos(self):
        """初始化macOS音量控制"""
        try:
            import applescript
            # 测试是否可以访问音量控制
            result = applescript.run('get volume settings')
            if not result or result.code != 0:
                raise Exception("无法访问macOS音量控制")
            self.logger.debug("macOS音量控制初始化成功")
        except Exception as e:
            self.logger.error(f"macOS音量控制初始化失败: {e}")
            raise
    
    def _init_linux(self):
        """初始化Linux音量控制"""
        # 检测可用的音量控制工具
        self.linux_tool = None
        
        def cmd_exists(cmd):
            return shutil.which(cmd) is not None
        
        # 按优先级检查工具
        if cmd_exists("pactl"):
            self.linux_tool = "pactl"
        elif cmd_exists("wpctl"):
            self.linux_tool = "wpctl"
        elif cmd_exists("amixer"):
            self.linux_tool = "amixer"
        elif cmd_exists("alsamixer") and cmd_exists("expect"):
            self.linux_tool = "alsamixer"
        
        if not self.linux_tool:
            self.logger.error("未找到可用的Linux音量控制工具")
            raise Exception("未找到可用的Linux音量控制工具")
        
        self.logger.debug(f"Linux音量控制初始化成功，使用: {self.linux_tool}")
    
    def get_volume(self):
        """获取当前音量 (0-100)"""
        if self.system == "Windows":
            return self._get_windows_volume()
        elif self.system == "Darwin":
            return self._get_macos_volume()
        elif self.system == "Linux":
            return self._get_linux_volume()
        return 70  # 默认音量
    
    def set_volume(self, volume):
        """设置音量 (0-100)"""
        # 确保音量在有效范围内
        volume = max(0, min(100, volume))
        
        if self.system == "Windows":
            self._set_windows_volume(volume)
        elif self.system == "Darwin":
            self._set_macos_volume(volume)
        elif self.system == "Linux":
            self._set_linux_volume(volume)
    
    def _get_windows_volume(self):
        """获取Windows音量"""
        try:
            # 获取音量百分比
            volume_scalar = self.volume_control.GetMasterVolumeLevelScalar()
            return int(volume_scalar * 100)
        except Exception as e:
            self.logger.warning(f"获取Windows音量失败: {e}")
            return 70
    
    def _set_windows_volume(self, volume):
        """设置Windows音量"""
        try:
            # 直接设置音量百分比
            self.volume_control.SetMasterVolumeLevelScalar(volume / 100.0, None)
        except Exception as e:
            self.logger.warning(f"设置Windows音量失败: {e}")
    
    def _get_macos_volume(self):
        """获取macOS音量"""
        try:
            import applescript
            result = applescript.run('output volume of (get volume settings)')
            if result and result.out:
                return int(result.out.strip())
            return 70
        except Exception as e:
            self.logger.warning(f"获取macOS音量失败: {e}")
            return 70
    
    def _set_macos_volume(self, volume):
        """设置macOS音量"""
        try:
            import applescript
            applescript.run(f'set volume output volume {volume}')
        except Exception as e:
            self.logger.warning(f"设置macOS音量失败: {e}")
    
    def _get_linux_volume(self):
        """获取Linux音量"""
        if self.linux_tool == "pactl":
            return self._get_pactl_volume()
        elif self.linux_tool == "wpctl":
            return self._get_wpctl_volume()
        elif self.linux_tool == "amixer":
            return self._get_amixer_volume()
        return 70
    
    def _set_linux_volume(self, volume):
        """设置Linux音量"""
        if self.linux_tool == "pactl":
            self._set_pactl_volume(volume)
        elif self.linux_tool == "wpctl":
            self._set_wpctl_volume(volume)
        elif self.linux_tool == "amixer":
            self._set_amixer_volume(volume)
        elif self.linux_tool == "alsamixer":
            self._set_alsamixer_volume(volume)
    
    def _get_pactl_volume(self):
        """使用pactl获取音量"""
        try:
            result = subprocess.run(
                ["pactl", "list", "sinks"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Volume:' in line and 'front-left:' in line:
                        match = re.search(r'(\d+)%', line)
                        if match:
                            return int(match.group(1))
        except Exception as e:
            self.logger.debug(f"通过pactl获取音量失败: {e}")
        return 70
    
    def _set_pactl_volume(self, volume):
        """使用pactl设置音量"""
        try:
            subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{volume}%"],
                capture_output=True,
                text=True
            )
        except Exception as e:
            self.logger.warning(f"通过pactl设置音量失败: {e}")

    def _get_wpctl_volume(self):
        """使用wpctl获取音量"""
        try:
            result = subprocess.run(
                ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
                capture_output=True,
                text=True,
                check=True
            )
            return int(float(result.stdout.split(' ')[1]) * 100)
        except Exception as e:
            self.logger.debug(f"通过wpctl获取音量失败: {e}")
        return 70

    def _set_wpctl_volume(self, volume):
        """使用wpctl设置音量"""
        try:
            subprocess.run(
                ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{volume}%"],
                capture_output=True,
                text=True,
                check=True
            )
        except Exception as e:
            self.logger.warning(f"通过wpctl设置音量失败: {e}")
    
    def _get_amixer_volume(self):
        """使用amixer获取音量"""
        try:
            result = subprocess.run(
                ["amixer", "get", "Master"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                match = re.search(r'(\d+)%', result.stdout)
                if match:
                    return int(match.group(1))
        except Exception as e:
            self.logger.debug(f"通过amixer获取音量失败: {e}")
        return 70
    
    def _set_amixer_volume(self, volume):
        """使用amixer设置音量"""
        try:
            subprocess.run(
                ["amixer", "sset", "Master", f"{volume}%"],
                capture_output=True,
                text=True
            )
        except Exception as e:
            self.logger.warning(f"通过amixer设置音量失败: {e}")
    
    def _set_alsamixer_volume(self, volume):
        """使用alsamixer设置音量"""
        try:
            script = f"""
            spawn alsamixer
            send "m"
            send "{volume}"
            send "%"
            send "q"
            expect eof
            """
            subprocess.run(
                ["expect", "-c", script],
                capture_output=True,
                text=True
            )
        except Exception as e:
            self.logger.warning(f"通过alsamixer设置音量失败: {e}")

    @staticmethod
    def check_dependencies():
        """检查并报告缺少的依赖"""
        import platform
        system = platform.system()
        missing = []
        
        if system == "Windows":
            try:
                import pycaw
            except ImportError:
                missing.append("pycaw")
            try:
                import comtypes
            except ImportError:
                missing.append("comtypes")
        
        elif system == "Darwin":  # macOS
            try:
                import applescript
            except ImportError:
                missing.append("applescript")
        
        elif system == "Linux":
            import shutil
            tools = ["pactl", "wpctl", "amixer", "alsamixer"]
            found = False
            for tool in tools:
                if shutil.which(tool):
                    found = True
                    break
            if not found:
                missing.append("pulseaudio-utils、wireplumber 或 alsa-utils")
        
        if missing:
            print(f"警告: 音量控制需要以下依赖，但未找到: {', '.join(missing)}")
            print("请使用以下命令安装缺少的依赖:")
            if system == "Windows":
                print("pip install " + " ".join(missing))
            elif system == "Darwin":
                print("pip install " + " ".join(missing))
            elif system == "Linux":
                print("sudo apt-get install " + " ".join(missing))
            return False
        
        return True 