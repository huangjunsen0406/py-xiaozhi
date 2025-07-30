import asyncio
import time
from typing import Optional

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class GPIOButtonManager:
    """
    GPIO按钮管理器，用于在树莓派上通过GPIO引脚控制按钮触发MANUAL_PRESS功能。
    支持LED指示灯功能。
    """

    def __init__(self, pin: int = 6, pull_up: bool = True, debounce_time: float = 0.05, led_pin: int = 5):
        """
        初始化GPIO按钮管理器。

        Args:
            pin: GPIO引脚号（BCM编号）
            pull_up: 是否启用上拉电阻（True表示按钮按下时为低电平）
            debounce_time: 防抖时间（秒）
            led_pin: LED指示灯GPIO引脚号（BCM编号）
        """
        self.pin = pin
        self.pull_up = pull_up
        self.debounce_time = debounce_time
        self.led_pin = led_pin

        # 状态管理
        self.running = False
        self.button_pressed = False
        self.last_change_time = 0

        # 组件引用
        self.application = None
        self.shortcut_manager = None

        # GPIO库引用
        self.button = None
        self.led = None

        # 事件循环引用
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        self._monitor_task = None

        # 错误恢复
        self._error_count = 0
        self._max_error_count = 5

    def _init_gpio(self) -> bool:
        """
        初始化GPIO库。

        Returns:
            bool: 初始化是否成功
        """
        try:
            from gpiozero import Button, LED

            # 创建Button对象
            # gpiozero的Button默认使用上拉电阻，按下时为False
            # pull_up参数控制是否使用内部上拉电阻
            self.button = Button(self.pin, pull_up=self.pull_up, bounce_time=self.debounce_time)

            # 创建LED对象
            self.led = LED(self.led_pin)
            # 确保LED初始状态为关闭
            self.led.off()

            logger.info(f"GPIO引脚 {self.pin} (按钮) 和 {self.led_pin} (LED) 初始化成功，上拉电阻: {self.pull_up}")
            return True

        except ImportError:
            logger.error("未找到gpiozero库，请确保在树莓派上运行并安装了gpiozero")
            logger.error("安装命令: pip install gpiozero")
            return False
        except Exception as e:
            logger.error(f"GPIO初始化失败: {e}")
            return False

    def _is_button_pressed(self) -> bool:
        """
        检查按钮是否被按下。

        Returns:
            bool: 按钮是否被按下
        """
        if not self.button:
            return False

        try:
            # gpiozero的Button.is_pressed属性直接返回按钮状态
            return self.button.is_pressed
        except Exception as e:
            logger.error(f"读取GPIO状态失败: {e}")
            self._error_count += 1
            return False

    async def start(self) -> bool:
        """
        启动GPIO按钮监听。

        Returns:
            bool: 启动是否成功
        """
        try:
            # 检查是否在树莓派上运行
            if not self._check_raspberry_pi():
                logger.warning("当前不在树莓派环境中，GPIO按钮功能将被禁用")
                return False

            # 初始化GPIO
            if not self._init_gpio():
                return False

            # 获取应用实例
            from src.application import Application

            self.application = Application.get_instance()

            # 获取快捷键管理器实例（用于状态同步）
            if hasattr(self.application, 'shortcut_manager'):
                self.shortcut_manager = self.application.shortcut_manager

            # 保存主事件循环引用
            self._main_loop = asyncio.get_running_loop()

            # 启动监控任务
            self._monitor_task = asyncio.create_task(self._monitor_button())

            self.running = True
            logger.info(f"GPIO按钮监听已启动，监听引脚: {self.pin}")
            return True

        except Exception as e:
            logger.error(f"启动GPIO按钮监听失败: {e}", exc_info=True)
            return False

    def _check_raspberry_pi(self) -> bool:
        """
        检查是否在树莓派上运行。

        Returns:
            bool: 是否在树莓派上
        """
        try:
            import platform

            # 检查系统架构
            machine = platform.machine()
            if machine not in ['armv7l', 'aarch64', 'armv6l']:
                logger.debug(f"当前架构 {machine} 不是ARM架构")
                return False

            # 检查是否存在树莓派特有的文件
            import os

            if os.path.exists('/proc/device-tree/model'):
                with open('/proc/device-tree/model', 'r') as f:
                    model = f.read().strip()
                    if 'Raspberry Pi' in model:
                        logger.info(f"检测到树莓派型号: {model}")
                        return True

            # 检查/proc/cpuinfo
            if os.path.exists('/proc/cpuinfo'):
                with open('/proc/cpuinfo', 'r') as f:
                    cpuinfo = f.read()
                    if 'BCM' in cpuinfo or 'Raspberry Pi' in cpuinfo:
                        logger.info("通过/proc/cpuinfo检测到树莓派")
                        return True

            logger.debug("未检测到树莓派环境")
            return False

        except Exception as e:
            logger.error(f"检查树莓派环境时出错: {e}")
            return False

    async def _monitor_button(self):
        """
        监控按钮状态的主循环。
        """
        logger.info("开始监控GPIO按钮状态")

        while self.running:
            try:
                current_time = time.time()
                is_pressed = self._is_button_pressed()

                # 防抖处理
                if current_time - self.last_change_time < self.debounce_time:
                    await asyncio.sleep(0.01)  # 10ms
                    continue

                # 检查状态变化
                if is_pressed != self.button_pressed:
                    self.last_change_time = current_time
                    self.button_pressed = is_pressed

                    logger.debug(f"GPIO按钮状态变化: {'按下' if is_pressed else '释放'}")

                    # 触发相应的动作
                    if is_pressed:
                        await self._handle_button_press()
                    else:
                        await self._handle_button_release()

                    # 重置错误计数
                    self._error_count = 0

                # 检查错误计数
                if self._error_count >= self._max_error_count:
                    logger.error(f"GPIO错误次数过多({self._error_count})，停止监控")
                    break

                await asyncio.sleep(0.01)  # 10ms轮询间隔

            except Exception as e:
                logger.error(f"监控GPIO按钮时出错: {e}", exc_info=True)
                self._error_count += 1
                await asyncio.sleep(0.1)  # 错误时等待更长时间

        logger.info("GPIO按钮监控已停止")

    async def _handle_button_press(self):
        """
        处理按钮按下事件。
        """
        if not self.application:
            logger.warning("应用实例未初始化")
            return

        try:
            logger.info("GPIO按钮按下，开始监听")

            # 点亮LED指示灯
            if self.led:
                self.led.on()
                logger.debug("LED指示灯已点亮")

            # 同步快捷键管理器状态（如果存在）
            if self.shortcut_manager:
                self.shortcut_manager.manual_press_active = True
                self.shortcut_manager.key_states["MANUAL_PRESS"] = True

            # 开始监听
            await self.application.start_listening()

        except Exception as e:
            logger.error(f"处理按钮按下时出错: {e}", exc_info=True)

    async def _handle_button_release(self):
        """
        处理按钮释放事件。
        """
        if not self.application:
            logger.warning("应用实例未初始化")
            return

        try:
            logger.info("GPIO按钮释放，停止监听")

            # 熄灭LED指示灯
            if self.led:
                self.led.off()
                logger.debug("LED指示灯已熄灭")

            # 同步快捷键管理器状态（如果存在）
            if self.shortcut_manager:
                self.shortcut_manager.manual_press_active = False
                self.shortcut_manager.key_states["MANUAL_PRESS"] = False

            # 停止监听
            await self.application.stop_listening()

        except Exception as e:
            logger.error(f"处理按钮释放时出错: {e}", exc_info=True)

    async def stop(self):
        """
        停止GPIO按钮监听。
        """
        logger.info("正在停止GPIO按钮监听...")

        self.running = False

        # 停止监控任务
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # 清理GPIO
        if self.button:
            try:
                self.button.close()
                logger.info(f"GPIO引脚 {self.pin} (按钮) 已清理")
            except Exception as e:
                logger.warning(f"清理按钮GPIO时出错: {e}")

        if self.led:
            try:
                self.led.off()  # 确保LED熄灭
                self.led.close()
                logger.info(f"GPIO引脚 {self.led_pin} (LED) 已清理")
            except Exception as e:
                logger.warning(f"清理LED GPIO时出错: {e}")

        # 重置状态
        self.button_pressed = False
        self._error_count = 0

        logger.info("GPIO按钮监听已停止")

    def get_status(self) -> dict:
        """
        获取GPIO按钮管理器状态。

        Returns:
            dict: 状态信息
        """
        led_status = False
        if self.led:
            try:
                led_status = self.led.is_lit
            except:
                led_status = False

        return {
            "running": self.running,
            "pin": self.pin,
            "led_pin": self.led_pin,
            "pull_up": self.pull_up,
            "button_pressed": self.button_pressed,
            "led_on": led_status,
            "error_count": self._error_count,
            "debounce_time": self.debounce_time,
        }


async def start_gpio_button_async(
    pin: int = 18, pull_up: bool = True, debounce_time: float = 0.05, led_pin: int = 5
) -> Optional[GPIOButtonManager]:
    """
    异步启动GPIO按钮管理器。

    Args:
        pin: GPIO引脚号（BCM编号）
        pull_up: 是否启用上拉电阻
        debounce_time: 防抖时间（秒）
        led_pin: LED指示灯GPIO引脚号（BCM编号）

    Returns:
        GPIOButtonManager实例或None（如果启动失败）
    """
    try:
        gpio_manager = GPIOButtonManager(pin=pin, pull_up=pull_up, debounce_time=debounce_time, led_pin=led_pin)
        success = await gpio_manager.start()

        if success:
            logger.info("GPIO按钮管理器启动成功")
            return gpio_manager
        else:
            logger.warning("GPIO按钮管理器启动失败")
            return None
    except Exception as e:
        logger.error(f"启动GPIO按钮管理器时出错: {e}")
        return None
