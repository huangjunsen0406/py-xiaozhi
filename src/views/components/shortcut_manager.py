import asyncio

from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class ShortcutManager:
    """全局快捷键管理器"""
    
    def __init__(self):
        """初始化快捷键管理器"""
        self.config = ConfigManager.get_instance()
        self.shortcuts_config = self.config.get_config("SHORTCUTS", {})
        self.enabled = self.shortcuts_config.get("ENABLED", True)
        self.pressed_keys = set()
        self.application = None
        self.display = None
        self.running = False
        self._listener = None
        self._main_loop = None
        # 添加一个标志来跟踪按住说话状态
        self.manual_press_active = False
        
    async def start(self):
        """启动快捷键监听"""
        if not self.enabled:
            logger.info("全局快捷键已禁用")
            return False
            
        try:
            # 保存主事件循环引用
            self._main_loop = asyncio.get_running_loop()
            
            # 导入pynput库
            from pynput import keyboard

            # 获取Application实例
            from src.application import Application
            self.application = Application.get_instance()
            self.display = self.application.display
            
            # 定义按键回调
            def on_press(key):
                if not self.running:
                    return
                    
                try:
                    key_name = self._get_key_name(key)
                    if key_name:
                        self.pressed_keys.add(key_name)
                        self._check_shortcuts(True)
                except Exception as e:
                    logger.error(f"按键处理错误: {e}")
                    
            def on_release(key):
                if not self.running:
                    return
                    
                try:
                    key_name = self._get_key_name(key)
                    if key_name:
                        if key_name in self.pressed_keys:
                            self.pressed_keys.remove(key_name)
                        self._check_shortcuts(False)
                except Exception as e:
                    logger.error(f"释放键处理错误: {e}")
            
            # 启动监听器
            self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            self._listener.start()
            self.running = True
            logger.info("全局快捷键监听已启动")
            return True
            
        except ImportError:
            logger.error("未安装pynput库，无法使用全局快捷键功能")
            return False
        except Exception as e:
            logger.error(f"启动全局快捷键监听失败: {e}")
            return False
    
    def _get_key_name(self, key):
        """获取按键名称"""
        try:
            if hasattr(key, 'name'):
                return key.name.lower()
            elif hasattr(key, 'char') and key.char:
                return key.char.lower()
            return None
        except Exception:
            return None
            
    def _check_shortcuts(self, is_press):
        """检查快捷键组合"""
        # 检查修饰键状态
        ctrl_pressed = "ctrl" in self.pressed_keys or "ctrl_l" in self.pressed_keys or "ctrl_r" in self.pressed_keys
        
        if not ctrl_pressed:
            # 如果Ctrl键被释放，且按住说话功能处于激活状态，则停止监听
            if not is_press and self.manual_press_active:
                self._handle_manual_press(False)
            return
            
        # 获取快捷键配置
        manual_press = self.shortcuts_config.get("MANUAL_PRESS", {})
        auto_toggle = self.shortcuts_config.get("AUTO_TOGGLE", {})
        abort = self.shortcuts_config.get("ABORT", {})
        mode_toggle = self.shortcuts_config.get("MODE_TOGGLE", {})
        window_toggle = self.shortcuts_config.get("WINDOW_TOGGLE", {})
        
        # 检查各个快捷键
        if self._check_shortcut_key(manual_press):
            self._handle_manual_press(is_press)
        # 其他快捷键仅在按下时触发
        elif is_press:
            if self._check_shortcut_key(auto_toggle):
                self._handle_auto_toggle()
            elif self._check_shortcut_key(abort):
                self._handle_abort()
            elif self._check_shortcut_key(mode_toggle):
                self._handle_mode_toggle()
            elif self._check_shortcut_key(window_toggle):
                self._handle_window_toggle()
        # 如果没有检测到任何快捷键组合，但按住说话功能处于激活状态，则停止监听
        elif not is_press and self.manual_press_active:
            self._handle_manual_press(False)
    
    def _check_shortcut_key(self, shortcut_config):
        """检查特定快捷键是否被按下"""
        key = shortcut_config.get("key", "").lower()
        return key in self.pressed_keys 
    
    def _run_coroutine_threadsafe(self, coro):
        """
        线程安全地运行协程
        """
        if not self._main_loop or not self.running:
            logger.warning("事件循环未运行或快捷键管理器已停止")
            return
            
        try:
            asyncio.run_coroutine_threadsafe(coro, self._main_loop)
        except Exception as e:
            logger.error(f"线程安全运行协程失败: {e}")
        
    def _handle_manual_press(self, is_press):
        """
        处理按住说话快捷键
        
        按住快捷键时开始监听（保持监听状态直到松开）
        松开快捷键后停止监听并发送语音内容
        
        Args:
            is_press: 是否为按下事件，True表示按下，False表示释放
        """
        if not self.application:
            return
            
        if is_press and not self.manual_press_active:
            # 按下开始监听
            logger.debug("快捷键：开始监听")
            self._run_coroutine_threadsafe(self.application.start_listening())
            self.manual_press_active = True
        elif not is_press and self.manual_press_active:
            # 松开时停止监听并发送
            logger.debug("快捷键：停止监听")
            self._run_coroutine_threadsafe(self.application.stop_listening())
            self.manual_press_active = False
    
    def _handle_auto_toggle(self):
        """处理自动对话快捷键"""
        if self.application:
            self._run_coroutine_threadsafe(self.application.toggle_chat_state())
    
    def _handle_abort(self):
        """处理中断对话快捷键"""
        if self.application:
            from src.constants.constants import AbortReason
            self._run_coroutine_threadsafe(self.application.abort_speaking(AbortReason.NONE))
    
    def _handle_mode_toggle(self):
        """处理模式切换快捷键"""
        if self.display:
            self._run_coroutine_threadsafe(self.display.toggle_mode())
    
    def _handle_window_toggle(self):
        """处理窗口显示/隐藏快捷键"""
        if self.display:
            self._run_coroutine_threadsafe(self.display.toggle_window_visibility())
    
    async def stop(self):
        """停止快捷键监听"""
        self.running = False
        # 确保清理按住说话状态
        self.manual_press_active = False
        if self._listener:
            self._listener.stop()
            self._listener = None
        logger.info("全局快捷键监听已停止")


# 异步启动函数
async def start_global_shortcuts_async(logger_instance=None):
    """
    异步启动全局快捷键管理器
    
    返回:
        ShortcutManager实例或None（如果启动失败）
    """
    try:
        shortcut_manager = ShortcutManager()
        success = await shortcut_manager.start()
        
        if success:
            if logger_instance:
                logger_instance.info("全局快捷键管理器启动成功")
            return shortcut_manager
        else:
            if logger_instance:
                logger_instance.warning("全局快捷键管理器启动失败")
            return None
    except Exception as e:
        if logger_instance:
            logger_instance.error(f"启动全局快捷键管理器时出错: {e}")
        return None
