"""音频设备枚举、选择与测试."""

import time

import numpy as np
import sounddevice as sd
from PySide6.QtCore import Slot

from src.logging import get_logger

logger = get_logger()


class SettingsAudioDevicesMixin:
    # ========== 音频设备设置 ==========

    def _load_audio_devices(self, force: bool = False):
        """加载可用的音频设备列表.

        Args:
            force: True 时强制重新枚举（刷新/打开设置）
        """
        if self._audio_devices_loaded and not force:
            return
        try:
            devices = list(sd.query_devices())
            self._input_devices = []
            self._output_devices = []

            default_input = sd.default.device[0] if sd.default.device else None
            default_output = sd.default.device[1] if sd.default.device else None

            for i, d in enumerate(devices):
                device_name = d.get("name", "Unknown")
                sample_rate = int(d.get("default_samplerate", 48000))

                # 输入设备
                if int(d.get("max_input_channels", 0)) > 0:
                    default_mark = " (默认)" if i == default_input else ""
                    self._input_devices.append(
                        {
                            "index": i,
                            "name": device_name + default_mark,
                            "raw_name": device_name,
                            "sample_rate": sample_rate,
                            "channels": int(d.get("max_input_channels", 0)),
                        }
                    )

                # 输出设备
                if int(d.get("max_output_channels", 0)) > 0:
                    default_mark = " (默认)" if i == default_output else ""
                    self._output_devices.append(
                        {
                            "index": i,
                            "name": device_name + default_mark,
                            "raw_name": device_name,
                            "sample_rate": sample_rate,
                            "channels": int(d.get("max_output_channels", 0)),
                        }
                    )

            self._audio_devices_loaded = True
            logger.debug(
                f"加载了 {len(self._input_devices)} 个输入设备, {len(self._output_devices)} 个输出设备"
            )
            self.devicesChanged.emit()
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
        """刷新设备列表."""
        self._load_audio_devices(force=True)
        self.statusMessage.emit("设备列表已刷新")

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
            self.statusMessage.emit(
                f"[成功] 录音测试通过 (音量: {max_amplitude:.1%})"
            )
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

