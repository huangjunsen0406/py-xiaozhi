import json

from src.constants.constants import AbortReason, ListeningMode


class Protocol:
    def __init__(self):
        self.session_id = ""
        # 初始化回调函数为None
        self.on_incoming_json = None
        self.on_incoming_audio = None
        self.on_audio_channel_opened = None
        self.on_audio_channel_closed = None
        self.on_network_error = None

    def on_incoming_json(self, callback):
        """设置JSON消息接收回调函数"""
        self.on_incoming_json = callback

    def on_incoming_audio(self, callback):
        """设置音频数据接收回调函数"""
        self.on_incoming_audio = callback

    def on_audio_channel_opened(self, callback):
        """设置音频通道打开回调函数"""
        self.on_audio_channel_opened = callback

    def on_audio_channel_closed(self, callback):
        """设置音频通道关闭回调函数"""
        self.on_audio_channel_closed = callback

    def on_network_error(self, callback):
        """设置网络错误回调函数"""
        self.on_network_error = callback

    async def send_text(self, message):
        """发送文本消息的抽象方法，需要在子类中实现"""
        raise NotImplementedError("send_text方法必须由子类实现")

    async def send_abort_speaking(self, reason):
        """发送中止语音的消息"""
        message = {
            "session_id": self.session_id,
            "type": "abort"
        }
        if reason == AbortReason.WAKE_WORD_DETECTED:
            message["reason"] = "wake_word_detected"
        await self.send_text(json.dumps(message))

    async def send_wake_word_detected(self, wake_word):
        """发送检测到唤醒词的消息"""
        message = {
            "session_id": self.session_id,
            "type": "listen",
            "state": "detect",
            "text": wake_word
        }
        await self.send_text(json.dumps(message))

    async def send_start_listening(self, mode):
        """发送开始监听的消息"""
        mode_map = {
            ListeningMode.ALWAYS_ON: "realtime",
            ListeningMode.AUTO_STOP: "auto",
            ListeningMode.MANUAL: "manual"
        }
        message = {
            "session_id": self.session_id,
            "type": "listen",
            "state": "start",
            "mode": mode_map[mode]
        }
        await self.send_text(json.dumps(message))

    async def send_stop_listening(self):
        """发送停止监听的消息"""
        message = {
            "session_id": self.session_id,
            "type": "listen",
            "state": "stop"
        }
        await self.send_text(json.dumps(message))

    async def send_iot_descriptors(self, descriptors):
        """发送物联网设备描述信息"""
        message = {
            "session_id": self.session_id,
            "type": "iot",
            "descriptors": json.loads(descriptors) if isinstance(descriptors, str) else descriptors
        }
        await self.send_text(json.dumps(message))

    async def send_iot_states(self, states):
        """发送物联网设备状态信息"""
        message = {
            "session_id": self.session_id,
            "type": "iot",
            "states": json.loads(states) if isinstance(states, str) else states
        }
        await self.send_text(json.dumps(message))