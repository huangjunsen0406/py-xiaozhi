"""
Screenshot camera implementation for capturing desktop screens.
"""

import io
import sys
import threading

from src.mcp.tools.camera.base_camera import BaseCamera
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class ScreenshotCamera(BaseCamera):
    """
    桌面截图摄像头实现.
    """

    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        """
        获取单例实例.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self):
        """
        初始化截图摄像头.
        """
        super().__init__()
        logger.info("Initializing ScreenshotCamera")
        
        # 导入依赖库
        self._import_dependencies()
        
    def _import_dependencies(self):
        """
        导入必要的依赖库.
        """
        # 检测 PIL 是否可用（避免未使用导入的告警）
        try:
            import importlib.util
            self._pil_available = importlib.util.find_spec("PIL.ImageGrab") is not None
            if self._pil_available:
                logger.info("PIL ImageGrab available for screenshot capture")
            else:
                logger.warning("PIL not available, will try alternative screenshot methods")
        except Exception:
            self._pil_available = False
            logger.warning("Failed to check PIL availability, fallback methods will be used")
        
        # 平台特定导入
        if sys.platform == "darwin":  # macOS
            # 使用 which 检测系统 screencapture 命令是否可用
            try:
                import shutil
                self._subprocess_available = shutil.which("screencapture") is not None
                if self._subprocess_available:
                    logger.info("screencapture command available for macOS screenshot")
                else:
                    logger.warning("screencapture command not found on macOS")
            except Exception:
                self._subprocess_available = False
        elif sys.platform == "win32":  # Windows
            try:
                import ctypes
                self._win32_available = hasattr(ctypes, "windll")
                logger.info("Win32 API available for Windows screenshot")
            except ImportError:
                self._win32_available = False

    def capture(self, display_id=None) -> bool:
        """
        截取桌面画面.
        
        Args:
            display_id: 显示器ID，None=所有显示器，"main"=主屏，"secondary"=副屏，1,2,3...=具体显示器
        
        Returns:
            成功返回True，失败返回False
        """
        try:
            logger.info("Starting desktop screenshot capture...")
            
            # 尝试不同的截图方法
            screenshot_data = None
            
            # 优先使用平台特定方法（更好的多显示器支持）
            if sys.platform == "darwin" and getattr(self, '_subprocess_available', False):
                screenshot_data = self._capture_macos(display_id)
            elif sys.platform == "win32" and getattr(self, '_win32_available', False):
                screenshot_data = self._capture_windows(display_id)
            elif sys.platform.startswith("linux"):
                screenshot_data = self._capture_linux(display_id)
            
            # 备用方法：使用PIL ImageGrab
            if not screenshot_data and self._pil_available:
                screenshot_data = self._capture_with_pil()
            
            if screenshot_data:
                self.set_jpeg_data(screenshot_data)
                logger.info(f"Screenshot captured successfully, size: {len(screenshot_data)} bytes")
                return True
            else:
                logger.error("All screenshot capture methods failed")
                return False
                
        except Exception as e:
            logger.error(f"Error capturing screenshot: {e}", exc_info=True)
            return False

    def _capture_with_pil(self) -> bytes:
        """
        使用PIL ImageGrab截图.
        
        Returns:
            JPEG格式的图片字节数据
        """
        try:
            import PIL.ImageGrab
            
            logger.debug("Capturing screenshot with PIL ImageGrab...")
            
            # 截取所有屏幕（包括多显示器）
            screenshot = PIL.ImageGrab.grab(all_screens=True)
            
            # 如果图片包含透明度通道(RGBA)，转换为RGB
            if screenshot.mode == 'RGBA':
                # 创建白色背景
                from PIL import Image
                background = Image.new('RGB', screenshot.size, (255, 255, 255))
                background.paste(screenshot, mask=screenshot.split()[3])  # 使用alpha通道作为mask
                screenshot = background
            elif screenshot.mode not in ['RGB', 'L']:
                # 确保图片格式兼容JPEG
                screenshot = screenshot.convert('RGB')
            
            # 转换为JPEG格式的字节数据
            byte_io = io.BytesIO()
            screenshot.save(byte_io, format='JPEG', quality=85)
            
            return byte_io.getvalue()
            
        except Exception as e:
            logger.error(f"PIL screenshot capture failed: {e}")
            return None

    def _capture_macos(self, display_id=None) -> bytes:
        """
        使用macOS系统命令截图（支持显示器选择）.
        
        Args:
            display_id: 显示器ID，None=所有显示器，"main"=主屏，"secondary"=副屏，1,2,3...=具体显示器
        
        Returns:
            JPEG格式的图片字节数据
        """
        try:
            from PIL import Image
            
            logger.debug(f"Capturing screenshot with macOS screencapture command, display_id: {display_id}")
            
            # 根据display_id决定截图策略
            if display_id is None:
                # 截取所有显示器并合成
                screenshot = self._capture_all_displays_macos()
            elif display_id == "main" or display_id == 1:
                # 截取主显示器
                screenshot = self._capture_single_display_macos(1)
            elif display_id == "secondary" or display_id == 2:
                # 截取副显示器
                screenshot = self._capture_single_display_macos(2)
            elif isinstance(display_id, int) and display_id > 0:
                # 截取指定显示器
                screenshot = self._capture_single_display_macos(display_id)
            else:
                logger.error(f"Invalid display_id: {display_id}")
                return None
            
            if not screenshot:
                logger.error("Failed to create composite screenshot")
                return None
            
            # 转换为JPEG
            if screenshot.mode == 'RGBA':
                # 创建白色背景
                background = Image.new('RGB', screenshot.size, (255, 255, 255))
                background.paste(screenshot, mask=screenshot.split()[3])
                screenshot = background
            elif screenshot.mode not in ['RGB', 'L']:
                screenshot = screenshot.convert('RGB')
            
            # 保存为JPEG字节数据
            byte_io = io.BytesIO()
            screenshot.save(byte_io, format='JPEG', quality=85)
            
            return byte_io.getvalue()
                
        except Exception as e:
            logger.error(f"macOS screenshot capture failed: {e}")
            return None
    
    def _composite_displays(self, displays):
        """
        将多个显示器的截图合成为一张图片.
        
        Args:
            displays: 显示器信息列表
            
        Returns:
            合成后的PIL Image对象
        """
        try:
            from PIL import Image

            # 计算合成后的尺寸
            # 假设显示器按上下或左右排列
            total_width = max(display['size'][0] for display in displays)
            total_height = sum(display['size'][1] for display in displays)
            
            # 也计算左右排列的尺寸
            horizontal_width = sum(display['size'][0] for display in displays)
            horizontal_height = max(display['size'][1] for display in displays)
            
            # 选择更紧凑的排列方式
            if total_width * total_height <= horizontal_width * horizontal_height:
                # 垂直排列更紧凑
                composite = Image.new('RGB', (total_width, total_height), (0, 0, 0))
                y_offset = 0
                for display in sorted(displays, key=lambda d: d['id']):
                    x_offset = (total_width - display['size'][0]) // 2  # 居中
                    composite.paste(display['image'], (x_offset, y_offset))
                    y_offset += display['size'][1]
                logger.debug(f"Created vertical composite: {composite.size}")
            else:
                # 水平排列更紧凑
                composite = Image.new('RGB', (horizontal_width, horizontal_height), (0, 0, 0))
                x_offset = 0
                for display in sorted(displays, key=lambda d: d['id']):
                    y_offset = (horizontal_height - display['size'][1]) // 2  # 居中
                    composite.paste(display['image'], (x_offset, y_offset))
                    x_offset += display['size'][0]
                logger.debug(f"Created horizontal composite: {composite.size}")
            
            return composite
            
        except Exception as e:
            logger.error(f"Failed to composite displays: {e}")
            return None

    def _capture_windows(self, display_id=None) -> bytes:
        """
        使用Windows API截图.
        
        Args:
            display_id: 显示器ID (暂未实现，使用虚拟屏幕)
        
        Returns:
            JPEG格式的图片字节数据
        """
        try:
            import ctypes
            import ctypes.wintypes

            from PIL import Image
            
            logger.debug(f"Capturing screenshot with Windows API, display_id: {display_id}")
            
            # 获取虚拟屏幕尺寸（包括所有显示器）
            user32 = ctypes.windll.user32
            # SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN
            virtual_left = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
            virtual_top = user32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
            virtual_width = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
            virtual_height = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
            
            screensize = (virtual_width, virtual_height)
            screen_offset = (virtual_left, virtual_top)
            
            # 创建设备上下文
            hdc = user32.GetDC(None)
            hcdc = ctypes.windll.gdi32.CreateCompatibleDC(hdc)
            hbmp = ctypes.windll.gdi32.CreateCompatibleBitmap(hdc, screensize[0], screensize[1])
            ctypes.windll.gdi32.SelectObject(hcdc, hbmp)
            
            # 复制虚拟屏幕到位图（包括所有显示器）
            ctypes.windll.gdi32.BitBlt(
                hcdc,
                0,
                0,
                screensize[0],
                screensize[1],
                hdc,
                screen_offset[0],
                screen_offset[1],
                0x00CC0020,
            )
            
            # 获取位图数据
            bmpinfo = ctypes.wintypes.BITMAPINFO()
            bmpinfo.bmiHeader.biSize = ctypes.sizeof(ctypes.wintypes.BITMAPINFOHEADER)
            bmpinfo.bmiHeader.biWidth = screensize[0]
            bmpinfo.bmiHeader.biHeight = -screensize[1]  # 负值表示从上到下
            bmpinfo.bmiHeader.biPlanes = 1
            bmpinfo.bmiHeader.biBitCount = 32
            bmpinfo.bmiHeader.biCompression = 0
            
            # 分配缓冲区
            buffer_size = screensize[0] * screensize[1] * 4
            buffer = ctypes.create_string_buffer(buffer_size)
            
            # 获取像素数据
            ctypes.windll.gdi32.GetDIBits(hcdc, hbmp, 0, screensize[1], buffer, ctypes.byref(bmpinfo), 0)
            
            # 清理资源
            ctypes.windll.gdi32.DeleteObject(hbmp)
            ctypes.windll.gdi32.DeleteDC(hcdc)
            user32.ReleaseDC(None, hdc)
            
            # 转换为PIL Image
            image = Image.frombuffer('RGBA', screensize, buffer, 'raw', 'BGRA', 0, 1)
            image = image.convert('RGB')
            
            # 转换为JPEG字节数据
            byte_io = io.BytesIO()
            image.save(byte_io, format='JPEG', quality=85)
            
            return byte_io.getvalue()
            
        except Exception as e:
            logger.error(f"Windows screenshot capture failed: {e}")
            return None

    def _capture_linux(self, display_id=None) -> bytes:
        """
        使用Linux系统命令截图.
        
        Args:
            display_id: 显示器ID (暂未实现，使用默认显示器)
        
        Returns:
            JPEG格式的图片字节数据
        """
        try:
            import os
            import subprocess
            import tempfile
            
            logger.debug(f"Capturing screenshot with Linux screenshot commands, display_id: {display_id}")
            
            # 尝试不同的Linux截图工具
            screenshot_commands = [
                ["gnome-screenshot", "-f"],  # GNOME
                ["scrot"],                   # scrot
                ["import", "-window", "root"],  # ImageMagick
            ]
            
            for cmd_base in screenshot_commands:
                try:
                    # 创建临时文件
                    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                        temp_path = temp_file.name
                    
                    # 构建完整命令
                    cmd = cmd_base + [temp_path]
                    
                    # 执行命令
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0 and os.path.exists(temp_path):
                        # 读取截图数据
                        with open(temp_path, 'rb') as f:
                            screenshot_data = f.read()
                        
                        # 清理临时文件
                        os.unlink(temp_path)
                        
                        logger.debug(f"Successfully captured screenshot with: {' '.join(cmd_base)}")
                        return screenshot_data
                    else:
                        # 清理临时文件
                        if os.path.exists(temp_path):
                            os.unlink(temp_path)
                        
                except subprocess.TimeoutExpired:
                    logger.warning(f"Screenshot command timed out: {' '.join(cmd_base)}")
                except FileNotFoundError:
                    logger.debug(f"Screenshot tool not found: {' '.join(cmd_base)}")
                except Exception as e:
                    logger.debug(f"Screenshot command failed {' '.join(cmd_base)}: {e}")
            
            return None
                
        except Exception as e:
            logger.error(f"Linux screenshot capture failed: {e}")
            return None

    def analyze(self, question: str) -> str:
        """
        分析截图内容.
        
        Args:
            question: 用户的问题或分析要求
            
        Returns:
            分析结果的JSON字符串
        """
        try:
            logger.info(f"Analyzing screenshot with question: {question}")
            
            # 获取现有的摄像头实例来复用分析能力
            from src.mcp.tools.camera import get_camera_instance
            
            camera_instance = get_camera_instance()
            
            # 将我们的截图数据传递给分析器
            original_jpeg_data = camera_instance.get_jpeg_data()
            camera_instance.set_jpeg_data(self.jpeg_data["buf"])
            
            try:
                # 使用现有的分析能力
                result = camera_instance.analyze(question)
                
                # 恢复原始数据
                camera_instance.set_jpeg_data(original_jpeg_data["buf"])
                
                return result
                
            except Exception as e:
                # 恢复原始数据
                camera_instance.set_jpeg_data(original_jpeg_data["buf"])
                raise e
                
        except Exception as e:
            logger.error(f"Error analyzing screenshot: {e}", exc_info=True)
            return f'{{"success": false, "message": "Failed to analyze screenshot: {str(e)}"}}'

    def _capture_single_display_macos(self, display_num):
        """
        截取macOS单个显示器.
        
        Args:
            display_num: 显示器编号 (1, 2, 3, ...)
            
        Returns:
            PIL Image对象
        """
        try:
            import os
            import subprocess
            import tempfile

            from PIL import Image
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_path = temp_file.name
            
            cmd = ["screencapture", "-D", str(display_num), "-x", "-t", "png", temp_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(temp_path):
                try:
                    img = Image.open(temp_path)
                    screenshot = img.copy()
                    os.unlink(temp_path)
                    logger.debug(f"Captured display {display_num}: {screenshot.size}")
                    return screenshot
                except Exception as e:
                    logger.error(f"Failed to read display {display_num}: {e}")
                    os.unlink(temp_path)
                    return None
            else:
                logger.error(f"screencapture failed for display {display_num}: {result.stderr}")
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                return None
                
        except Exception as e:
            logger.error(f"Single display capture failed: {e}")
            return None

    def _capture_all_displays_macos(self):
        """
        截取macOS所有显示器并合成.
        
        Returns:
            合成后的PIL Image对象
        """
        try:
            import os
            import subprocess
            import tempfile

            from PIL import Image

            # 检测所有可用的显示器
            displays = []
            for display_id in range(1, 5):  # 检测最多4个显示器
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                    temp_path = temp_file.name
                
                cmd = ["screencapture", "-D", str(display_id), "-x", "-t", "png", temp_path]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0 and os.path.exists(temp_path):
                    try:
                        img = Image.open(temp_path)
                        displays.append({
                            'id': display_id,
                            'size': img.size,
                            'image': img.copy(),
                            'path': temp_path
                        })
                        logger.debug(f"Found display {display_id}: {img.size}")
                    except Exception as e:
                        logger.debug(f"Failed to read display {display_id}: {e}")
                        os.unlink(temp_path)
                else:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
            
            if not displays:
                logger.error("No displays found")
                return None
            
            # 清理临时文件
            for display in displays:
                try:
                    os.unlink(display['path'])
                except Exception:
                    pass
            
            if len(displays) == 1:
                # 单显示器，直接返回
                return displays[0]['image']
            else:
                # 多显示器，需要合成
                logger.debug(f"Compositing {len(displays)} displays")
                return self._composite_displays(displays)
                
        except Exception as e:
            logger.error(f"All displays capture failed: {e}")
            return None
