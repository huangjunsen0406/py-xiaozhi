import asyncio
import json
from asyncio import Task
from typing import Any, Dict

from src.iot.thing import Parameter, Thing
from src.iot.thing_manager import ThingManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class CountdownTimer(Thing):
    """
    一个用于延迟执行命令的倒计时器设备。
    """

    DEFAULT_DELAY = 5  # seconds

    def __init__(self):
        super().__init__("CountdownTimer", "一个用于延迟执行命令的倒计时器")
        # 使用字典存储活动的计时器，键是 timer_id，值是 asyncio.Task 对象
        self._timers: Dict[int, Task] = {}
        self._next_timer_id = 0
        # 使用锁来保护对 _timers 和 _next_timer_id 的访问，确保线程安全
        self._lock = asyncio.Lock()

        # 定义方法 - 使用 Parameter 对象
        self.add_method(
            "StartCountdown",
            "启动一个倒计时，结束后执行指定命令",
            [
                Parameter(
                    "command",
                    "要执行的IoT命令 (JSON格式字符串"
                    "{'name': '设备名', 'method': '方法名', "
                    "'parameters': {'参数名': '参数值'}})",
                    "string",
                    required=True,
                ),
                Parameter(
                    "delay", "延迟时间（秒），默认为5秒", "integer", required=False
                ),  # 使用 required=False 标记可选参数
            ],
            self._start_countdown,  # 直接使用方法引用，不用 lambda
        )
        self.add_method(
            "CancelCountdown",
            "取消指定的倒计时",
            [Parameter("timer_id", "要取消的计时器ID", "integer", required=True)],
            self._cancel_countdown,  # 直接使用方法引用，不用 lambda
        )

    async def _execute_command(self, timer_id: int, command_str: str) -> None:
        """
        计时器到期时执行的回调函数。
        """
        # 首先从活动计时器列表中移除自己
        async with self._lock:
            if timer_id not in self._timers:
                # 可能已经被取消
                logger.info(f"倒计时 {timer_id} 在执行前已被取消或不存在。")
                return
            del self._timers[timer_id]

        logger.info(f"倒计时 {timer_id} 结束，准备执行命令: {command_str}")

        try:
            # 命令应该是 JSON 格式的字符串，代表一个命令字典
            command_dict = json.loads(command_str)
            # 获取 ThingManager 单例并执行命令
            thing_manager = ThingManager.get_instance()
            result = await thing_manager.invoke(command_dict)
            logger.info(f"倒计时 {timer_id} 执行命令 '{command_str}' 结果: {result}")
        except json.JSONDecodeError:
            logger.error(
                f"倒计时 {timer_id}: 命令 '{command_str}' 格式错误，无法解析JSON。"
            )
        except Exception as e:
            logger.error(
                f"倒计时 {timer_id} 执行命令 '{command_str}' 时出错: {e}", exc_info=True
            )

    async def _delayed_execution(
        self, delay: int, timer_id: int, command_str: str
    ) -> None:
        """
        异步延迟执行函数.
        """
        try:
            await asyncio.sleep(delay)
            await self._execute_command(timer_id, command_str)
        except asyncio.CancelledError:
            logger.info(f"倒计时 {timer_id} 被取消")
        except Exception as e:
            logger.error(f"倒计时 {timer_id} 执行过程中出错: {e}", exc_info=True)

    async def _start_countdown(
        self, params_dict: Dict[str, Parameter]
    ) -> Dict[str, Any]:
        """
        处理 StartCountdown 方法调用。注意: params 现在是 Parameter 对象的字典.
        """
        # 从 Parameter 对象字典中获取值
        command_param = params_dict.get("command")
        delay_param = params_dict.get("delay")

        command_str = command_param.get_value() if command_param else None
        # 处理可选参数 delay
        delay = (
            delay_param.get_value()
            if delay_param and delay_param.get_value() is not None
            else self.DEFAULT_DELAY
        )

        if not command_str:
            logger.error("启动倒计时失败：缺少 'command' 参数值。")
            return {"status": "error", "message": "缺少 'command' 参数值"}

        # 验证延迟时间
        try:
            # 确保 delay 是整数类型
            if not isinstance(delay, int):
                delay = int(delay)

            if delay <= 0:
                logger.warning(
                    f"提供的延迟时间 {delay} 无效，使用默认值 "
                    f"{self.DEFAULT_DELAY} 秒。"
                )
                delay = self.DEFAULT_DELAY
        except (ValueError, TypeError):
            logger.warning(
                f"提供的延迟时间 '{delay}' 无效，使用默认值 "
                f"{self.DEFAULT_DELAY} 秒。"
            )
            delay = self.DEFAULT_DELAY

        # 尝试解析命令字符串以进行早期验证
        try:
            json.loads(command_str)
        except json.JSONDecodeError:
            logger.error(f"启动倒计时失败：命令格式错误，无法解析JSON: {command_str}")
            return {
                "status": "error",
                "message": f"命令格式错误，无法解析JSON: {command_str}",
            }

        # 获取当前事件循环
        loop = asyncio.get_running_loop()

        async with self._lock:
            timer_id = self._next_timer_id
            self._next_timer_id += 1
            # 创建异步任务并确保它在当前事件循环中运行
            task = loop.create_task(
                self._delayed_execution(delay, timer_id, command_str)
            )
            self._timers[timer_id] = task

        logger.info(f"启动倒计时 {timer_id}，将在 {delay} 秒后执行命令: {command_str}")
        return {
            "status": "success",
            "message": f"倒计时 {timer_id} 已启动，将在 {delay} 秒后执行。",
            "timer_id": timer_id,
        }

    async def _cancel_countdown(
        self, params_dict: Dict[str, Parameter]
    ) -> Dict[str, Any]:
        """
        处理 CancelCountdown 方法调用。注意: params 现在是 Parameter 对象的字典.
        """
        timer_id_param = params_dict.get("timer_id")
        timer_id = timer_id_param.get_value() if timer_id_param else None

        if timer_id is None:
            logger.error("取消倒计时失败：缺少 'timer_id' 参数值。")
            return {"status": "error", "message": "缺少 'timer_id' 参数值"}

        try:
            # 确保 timer_id 是整数
            if not isinstance(timer_id, int):
                timer_id = int(timer_id)
        except (ValueError, TypeError):
            logger.error(f"取消倒计时失败：无效的 'timer_id' {timer_id}。")
            return {"status": "error", "message": f"无效的 'timer_id': {timer_id}"}

        async with self._lock:
            if timer_id in self._timers:
                task = self._timers.pop(timer_id)
                task.cancel()
                logger.info(f"倒计时 {timer_id} 已成功取消。")
                return {"status": "success", "message": f"倒计时 {timer_id} 已取消"}
            else:
                logger.warning(f"尝试取消不存在或已完成的倒计时 {timer_id}。")
                return {
                    "status": "error",
                    "message": f"找不到ID为 {timer_id} 的活动倒计时",
                }

    async def cleanup(self) -> None:
        """
        在应用程序关闭时清理所有活动的计时器。
        """
        logger.info("正在清理倒计时器...")
        async with self._lock:
            active_timer_ids = list(self._timers.keys())  # 创建键的副本以安全迭代
            for timer_id in active_timer_ids:
                if timer_id in self._timers:
                    task = self._timers.pop(timer_id)
                    task.cancel()
                    logger.info(f"已取消后台计时器 {timer_id}")
        logger.info("倒计时器清理完成。")


# 注意：这个 cleanup 方法需要在应用程序关闭时被显式调用。
# ThingManager 或 Application 类可以负责在 shutdown 过程中调用其管理的 Things 的 cleanup 方法。
