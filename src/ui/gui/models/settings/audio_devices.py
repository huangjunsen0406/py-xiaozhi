"""音频设备枚举、选择与测试."""

from __future__ import annotations

import asyncio
import time

import numpy as np
import sounddevice as sd
from PySide6.QtCore import Slot

from src.logging import get_logger

logger = get_logger()


class SettingsAudioDevicesMixin:
    # ========== 音频设备设置 ==========

    def _apply_device_lists(self, devices: dict) -> None:
        """用枚举结果填充输入/输出列表并通知 QML."""
        self._input_devices = list(devices.get("input") or [])
        self._output_devices = list(devices.get("output") or [])
        self._audio_devices_loaded = True
        logger.debug(
            f"加载了 {len(self._input_devices)} 个输入设备, "
            f"{len(self._output_devices)} 个输出设备"
        )
        self.devicesChanged.emit()

    def _load_audio_devices(self, force: bool = False):
        """加载可用的音频设备列表（普通枚举，不重初始化 PortAudio）.

        Args:
            force: True 时强制重新枚举（打开设置时）
        """
        if self._audio_devices_loaded and not force:
            return
        try:
            from src.utils.audio_utils import list_audio_devices

            devices = list_audio_devices(include_virtual=True)
            self._apply_device_lists(devices)
        except Exception as e:
            logger.error(f"加载音频设备失败: {e}", exc_info=True)
            self._input_devices = []
            self._output_devices = []

    @Slot(result=list)
    def getInputDevices(self) -> list:
        """获取输入设备列表（首次调用时再枚举）."""
        self._load_audio_devices()
        return [d["name"] for d in self._input_devices]

    @Slot(result=list)
    def getOutputDevices(self) -> list:
        """获取输出设备列表（首次调用时再枚举）."""
        self._load_audio_devices()
        return [d["name"] for d in self._output_devices]

    @Slot()
    def refreshDevices(self):
        """热刷新设备列表（停流 → PortAudio 重枚举 → 再开流）.

        运行中后连蓝牙时，需经 AudioPlugin 先停流再 ``refresh_portaudio_devices``。
        无 EventBus 时降级为本地普通枚举。
        """
        if getattr(self, "_audio_devices_refreshing", False):
            self.statusMessage.emit("设备刷新进行中…")
            return

        event_bus = getattr(self, "_event_bus", None)
        task_manager = getattr(self, "_task_manager", None)

        if event_bus is None or task_manager is None:
            logger.warning("SettingsModel: 无 EventBus/TaskManager，降级为本地设备枚举")
            self._load_audio_devices(force=True)
            self.statusMessage.emit(
                "设备列表已刷新（未协调音频流；后连蓝牙可能仍不可见）"
            )
            return

        self._audio_devices_refreshing = True
        self.statusMessage.emit("正在刷新音频设备（会短暂中断麦克风/播放）…")

        async def _refresh():
            from src.core.event_bus import Events
            from src.utils.audio_utils import list_audio_devices

            # Future 作 payload：AudioPlugin 在 handler 里 set_result(设备列表)
            # emit 会 await 所有 handler，返回时 future 通常已完成
            loop = asyncio.get_running_loop()
            fut: asyncio.Future = loop.create_future()
            await event_bus.emit(Events.AUDIO_DEVICES_REFRESH_REQUEST, fut)
            if fut.done():
                result = fut.result()
            else:
                logger.warning("AudioPlugin 未完成设备刷新 Future，本地枚举兜底")
                result = list_audio_devices(include_virtual=True)
                if not fut.done():
                    fut.set_result(result)
            return result if isinstance(result, dict) else {"input": [], "output": []}

        def _on_task_done(task: asyncio.Task):
            def _apply():
                try:
                    if task.cancelled():
                        devices = {"input": [], "output": []}
                    else:
                        exc = task.exception()
                        if exc is not None:
                            logger.error(f"设备刷新任务异常: {exc}", exc_info=exc)
                            devices = {"input": [], "output": []}
                        else:
                            devices = task.result()
                except Exception as e:
                    logger.error(f"读取刷新结果失败: {e}", exc_info=True)
                    devices = {"input": [], "output": []}
                try:
                    if not isinstance(devices, dict):
                        devices = {"input": [], "output": []}
                    self._apply_device_lists(devices)
                    n_in = len(self._input_devices)
                    n_out = len(self._output_devices)
                    self.statusMessage.emit(
                        f"设备列表已刷新（输入 {n_in} / 输出 {n_out}）"
                    )
                finally:
                    self._audio_devices_refreshing = False

            self._schedule_ui(_apply)

        try:
            task = task_manager.spawn(_refresh(), name="ui:audio_devices_refresh")
            if task is None:
                self._audio_devices_refreshing = False
                self._load_audio_devices(force=True)
                self.statusMessage.emit("应用正在关闭，已本地枚举")
                return
            task.add_done_callback(_on_task_done)
        except Exception as e:
            self._audio_devices_refreshing = False
            logger.error(f"无法调度设备刷新: {e}", exc_info=True)
            self._load_audio_devices(force=True)
            self.statusMessage.emit(f"设备刷新失败，已本地枚举: {e}")

    def _schedule_ui(self, fn) -> None:
        """把回调丢回 Qt 主线程（spawn 的 done 可能在 loop 线程）."""
        try:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(0, fn)
        except Exception:
            try:
                fn()
            except Exception as e:
                logger.error(f"UI 回调失败: {e}", exc_info=True)

    def _get_selectedInputIndex(self) -> int:
        """获取当前选中的输入设备索引."""
        current_id = self._get_value("AUDIO_DEVICES.input_device_id", -1)
        current_name = self._get_value("AUDIO_DEVICES.input_device_name", "")

        # 优先按设备名称匹配
        if current_name:
            for i, d in enumerate(self._input_devices):
                if d["raw_name"] == current_name:
                    return i

        # 其次按设备ID匹配
        for i, d in enumerate(self._input_devices):
            if d["index"] == current_id:
                return i
        return 0

    def _set_selectedInputIndex(self, index: int):
        """设置选中的输入设备."""
        if 0 <= index < len(self._input_devices):
            device = self._input_devices[index]
            self._set_value("AUDIO_DEVICES.input_device_id", device["index"])
            self._set_value("AUDIO_DEVICES.input_device_name", device["raw_name"])
            self._set_value("AUDIO_DEVICES.input_sample_rate", device["sample_rate"])
            self._set_value("AUDIO_DEVICES.input_channels", min(device["channels"], 1))
            logger.info(f"选择输入设备: {device['name']}")

    def _get_selectedOutputIndex(self) -> int:
        """获取当前选中的输出设备索引."""
        current_id = self._get_value("AUDIO_DEVICES.output_device_id", -1)
        current_name = self._get_value("AUDIO_DEVICES.output_device_name", "")

        # 优先按设备名称匹配
        if current_name:
            for i, d in enumerate(self._output_devices):
                if d["raw_name"] == current_name:
                    return i

        # 其次按设备ID匹配
        for i, d in enumerate(self._output_devices):
            if d["index"] == current_id:
                return i
        return 0

    def _set_selectedOutputIndex(self, index: int):
        """设置选中的输出设备."""
        if 0 <= index < len(self._output_devices):
            device = self._output_devices[index]
            self._set_value("AUDIO_DEVICES.output_device_id", device["index"])
            self._set_value("AUDIO_DEVICES.output_device_name", device["raw_name"])
            self._set_value("AUDIO_DEVICES.output_sample_rate", device["sample_rate"])
            self._set_value("AUDIO_DEVICES.output_channels", min(device["channels"], 2))
            logger.info(f"选择输出设备: {device['name']}")

    # 设备信息显示
    def _get_inputDeviceInfo(self) -> str:
        idx = self._get_selectedInputIndex()
        if 0 <= idx < len(self._input_devices):
            d = self._input_devices[idx]
            return f"采样率: {d['sample_rate']}Hz, 通道: {d['channels']}"
        return "未选择设备"

    def _get_outputDeviceInfo(self) -> str:
        idx = self._get_selectedOutputIndex()
        if 0 <= idx < len(self._output_devices):
            d = self._output_devices[idx]
            return f"采样率: {d['sample_rate']}Hz, 通道: {d['channels']}"
        return "未选择设备"

    # Opus 输出采样率
    def _get_opusOutputSampleRate(self) -> int:
        return self._get_value("AUDIO_DEVICES.opus_output_sample_rate", 24000)

    def _set_opusOutputSampleRate(self, value: int):
        self._set_value("AUDIO_DEVICES.opus_output_sample_rate", value)

    # 音频帧长度
    def _get_frameDuration(self) -> int:
        return self._get_value("AUDIO_DEVICES.frame_duration", 20)

    def _set_frameDuration(self, value: int):
        if value in [20, 40, 60]:
            self._set_value("AUDIO_DEVICES.frame_duration", value)

    # 音频测试
    @Slot()
    def testInputDevice(self):
        """测试输入设备（录音）."""
        if self._testing_input:
            return

        idx = self._get_selectedInputIndex()
        if idx < 0 or idx >= len(self._input_devices):
            self.statusMessage.emit("请先选择输入设备")
            return

        device = self._input_devices[idx]
        self._testing_input = True
        self.statusMessage.emit("开始录音测试...")

        self._run_worker(
            self._do_input_test,
            device,
            name="settings:input_test",
            test_kind="input",
            clear_flags=lambda: setattr(self, "_testing_input", False),
        )

    def _do_input_test(self, device: dict):
        """执行录音测试（异常由 _run_worker 兜底）."""
        device_id = device["index"]
        sample_rate = device["sample_rate"]
        duration = 3

        self.statusMessage.emit(f"请对着麦克风说话 ({duration}秒)...")
        time.sleep(1)

        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            device=device_id,
            dtype=np.float32,
        )
        sd.wait()

        max_amplitude = np.max(np.abs(recording))

        if max_amplitude < 0.001:
            self.statusMessage.emit("[失败] 未检测到音频信号")
            self.testComplete.emit("input", False)
        elif max_amplitude > 0.8:
            self.statusMessage.emit("[警告] 音频信号过载")
            self.testComplete.emit("input", True)
        else:
            self.statusMessage.emit(f"[成功] 录音测试通过 (音量: {max_amplitude:.1%})")
            self.testComplete.emit("input", True)

    @Slot()
    def testOutputDevice(self):
        """测试输出设备（播放）."""
        if self._testing_output:
            return

        idx = self._get_selectedOutputIndex()
        if idx < 0 or idx >= len(self._output_devices):
            self.statusMessage.emit("请先选择输出设备")
            return

        device = self._output_devices[idx]
        self._testing_output = True
        self.statusMessage.emit("开始播放测试...")

        self._run_worker(
            self._do_output_test,
            device,
            name="settings:output_test",
            test_kind="output",
            clear_flags=lambda: setattr(self, "_testing_output", False),
        )

    def _do_output_test(self, device: dict):
        """执行播放测试（异常由 _run_worker 兜底）."""
        device_id = device["index"]
        sample_rate = device["sample_rate"]
        duration = 2.0
        frequency = 440

        self.statusMessage.emit("播放 440Hz 测试音...")
        time.sleep(0.5)

        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = 0.3 * np.sin(2 * np.pi * frequency * t)

        fade_samples = int(0.1 * sample_rate)
        audio[:fade_samples] *= np.linspace(0, 1, fade_samples)
        audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)

        sd.play(audio, samplerate=sample_rate, device=device_id)
        sd.wait()

        self.statusMessage.emit("[成功] 播放测试完成")
        self.testComplete.emit("output", True)
