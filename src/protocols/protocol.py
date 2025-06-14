import abc
import asyncio
import json
import weakref
from typing import Set

from src.constants.constants import AbortReason, ListeningMode


class Protocol(abc.ABC):
    def __init__(self):
        self.session_id = ""
        # 初始化回调函数为None
        self.on_incoming_json = None
        self.on_incoming_audio = None
        self.on_audio_channel_opened = None
        self.on_audio_channel_closed = None
        self.on_network_error = None

        # 通用任务管理
        self._tasks: Set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()

    def _create_task(self, coro, name: str) -> asyncio.Task:
        """创建并管理任务"""
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)

        # 使用弱引用避免循环引用
        weak_tasks = weakref.ref(self._tasks)

        def done_callback(t):
            tasks = weak_tasks()
            if tasks is not None:
                tasks.discard(t)

            if not t.cancelled() and t.exception():
                msg = f"协议任务 {name} 异常结束: {t.exception()}"
                # 使用 get_logger() 可能会引入循环依赖，暂时用print
                print(msg)

        task.add_done_callback(done_callback)
        return task

    # 抽象方法 - 需要在子类中实现
    @abc.abstractmethod
    async def connect(self):
        """连接到服务器的抽象方法，需要在子类中实现."""
        raise NotImplementedError("connect方法必须由子类实现")

    @abc.abstractmethod
    async def send_text(self, message):
        """发送文本消息的抽象方法，需要在子类中实现."""
        raise NotImplementedError("send_text方法必须由子类实现")

    @abc.abstractmethod
    async def send_audio(self, audio_data):
        """发送音频数据的抽象方法，需要在子类中实现."""
        raise NotImplementedError("send_audio方法必须由子类实现")

    @abc.abstractmethod
    async def open_audio_channel(self):
        """打开音频通道的抽象方法，需要在子类中实现."""
        raise NotImplementedError("open_audio_channel方法必须由子类实现")

    @abc.abstractmethod
    async def close_audio_channel(self):
        """关闭音频通道的抽象方法，需要在子类中实现."""
        raise NotImplementedError("close_audio_channel方法必须由子类实现")

    @abc.abstractmethod
    def is_audio_channel_opened(self) -> bool:
        """检查音频通道是否打开的抽象方法，需要在子类中实现."""
        raise NotImplementedError("is_audio_channel_opened方法必须由子类实现")

    # 基于抽象方法的通用实现
    async def send_abort_speaking(self, reason):
        """发送中止语音的消息."""
        message = {"session_id": self.session_id, "type": "abort"}
        if reason == AbortReason.WAKE_WORD_DETECTED:
            message["reason"] = "wake_word_detected"
        await self.send_text(json.dumps(message))

    async def send_wake_word_detected(self, wake_word):
        """发送检测到唤醒词的消息."""
        message = {
            "session_id": self.session_id,
            "type": "listen",
            "state": "detect",
            "text": wake_word,
        }
        await self.send_text(json.dumps(message))

    async def send_start_listening(self, mode):
        """发送开始监听的消息."""
        mode_map = {
            ListeningMode.ALWAYS_ON: "realtime",
            ListeningMode.AUTO_STOP: "auto",
            ListeningMode.MANUAL: "manual",
        }
        message = {
            "session_id": self.session_id,
            "type": "listen",
            "state": "start",
            "mode": mode_map[mode],
        }
        await self.send_text(json.dumps(message))

    async def send_stop_listening(self):
        """发送停止监听的消息."""
        message = {"session_id": self.session_id, "type": "listen", "state": "stop"}
        await self.send_text(json.dumps(message))

    async def send_iot_descriptors(self, descriptors):
        """发送物联网设备描述信息."""
        message = {
            "session_id": self.session_id,
            "type": "iot",
            "descriptors": (
                json.loads(descriptors) if isinstance(descriptors, str) else descriptors
            ),
        }
        await self.send_text(json.dumps(message))

    async def send_iot_states(self, states):
        """发送物联网设备状态信息."""
        message = {
            "session_id": self.session_id,
            "type": "iot",
            "states": json.loads(states) if isinstance(states, str) else states,
        }
        await self.send_text(json.dumps(message))

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close_audio_channel()
