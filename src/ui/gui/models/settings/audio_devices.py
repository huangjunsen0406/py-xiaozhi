"""音频设备枚举、选择与测试."""

from __future__ import annotations

import asyncio
import time

import numpy as np
import sounddevice as sd
from PySide6.QtCore import Slot

from src.i18n import t
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
        """普通枚举在后台执行；同一时刻只允许一次扫描/热刷新。"""
        if self._closed or self._audio_devices_loading or self._audio_devices_refreshing:
            return
        if self._audio_devices_loaded and not force:
            return
        self._audio_devices_loading = True
        self._audio_generation += 1
        generation = self._audio_generation

        def scan():
            try:
                from src.utils.audio_utils import list_audio_devices

                devices = list_audio_devices(include_virtual=True)
                error = None
            except Exception as exc:
                logger.error("加载音频设备失败: %s", exc, exc_info=True)
                devices, error = None, str(exc)
            self._schedule_ui(
                lambda: self._finish_audio_devices(generation, devices, error)
            )

        self._run_worker(scan, name="settings:scan_audio")

    def _finish_audio_devices(self, generation, devices, error, *, refreshed=False):
        if self._closed or generation != self._audio_generation:
            return
        self._audio_devices_loading = False
        self._audio_devices_refreshing = False
        if error is not None:
            self.statusMessage.emit(t("settings.audio.scan_failed", error=error))
            return
        self._apply_device_lists(devices if isinstance(devices, dict) else {})
        if refreshed:
            self.statusMessage.emit(
                t(
                    "settings.audio.refreshed_counts",
                    inputs=len(self._input_devices),
                    outputs=len(self._output_devices),
                )
            )

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
        """停流热刷新；结果通过 QObject 排队信号返回 Qt 主线程。"""
        if self._closed:
            return
        if self._audio_devices_loading or self._audio_devices_refreshing:
            self.statusMessage.emit(t("settings.audio.refresh_in_progress"))
            return
        event_bus = self._event_bus
        task_manager = self._task_manager
        if event_bus is None or task_manager is None:
            self.statusMessage.emit(t("settings.audio.bg_scanning"))
            self._load_audio_devices(force=True)
            return

        self._audio_devices_refreshing = True
        self._audio_generation += 1
        generation = self._audio_generation
        self.statusMessage.emit(t("settings.audio.refreshing_interrupt"))

        async def _refresh():
            from src.ui.shared.settings_helpers import request_audio_devices_refresh

            return await request_audio_devices_refresh(event_bus)

        def _on_task_done(task):
            try:
                devices, error = task.result(), None
            except asyncio.CancelledError:
                devices, error = None, t("settings.audio.refresh_cancelled")
            except Exception as exc:
                logger.error("设备刷新任务异常: %s", exc, exc_info=True)
                devices, error = None, str(exc)
            self._schedule_ui(
                lambda: self._finish_audio_devices(
                    generation, devices, error, refreshed=True
                )
            )

        coroutine = _refresh()
        try:
            task = task_manager.spawn(coroutine, name="ui:audio_devices_refresh")
            if task is None:
                coroutine.close()
                self._finish_audio_devices(
                    generation, None, t("settings.audio.app_closing")
                )
                return
            task.add_done_callback(_on_task_done)
        except Exception as exc:
            coroutine.close()
            self._finish_audio_devices(generation, None, str(exc))

    def _device_list(self, direction: str) -> list[dict]:
        return self._input_devices if direction == "input" else self._output_devices

    def _selected_device_index(self, direction: str) -> int:
        from src.ui.shared.settings_helpers import match_audio_device

        current_id = self._get_value(f"AUDIO_DEVICES.{direction}_device_id", -1)
        current_name = self._get_value(f"AUDIO_DEVICES.{direction}_device_name", "")
        idx, _ = match_audio_device(
            self._device_list(direction),
            current_name=current_name,
            current_id=current_id,
        )
        return idx if idx >= 0 else 0

    def _select_device(self, direction: str, index: int) -> None:
        devices = self._device_list(direction)
        if not (0 <= index < len(devices)):
            return
        device = devices[index]
        max_channels = 1 if direction == "input" else 2
        self._set_value(f"AUDIO_DEVICES.{direction}_device_id", device["index"])
        self._set_value(f"AUDIO_DEVICES.{direction}_device_name", device["raw_name"])
        self._set_value(
            f"AUDIO_DEVICES.{direction}_sample_rate", device["sample_rate"]
        )
        self._set_value(
            f"AUDIO_DEVICES.{direction}_channels",
            min(device["channels"], max_channels),
        )
        label = "输入" if direction == "input" else "输出"
        logger.info(f"选择{label}设备: {device['name']}")

    def _device_info(self, direction: str) -> str:
        devices = self._device_list(direction)
        idx = self._selected_device_index(direction)
        if 0 <= idx < len(devices):
            d = devices[idx]
            return t(
                "settings.audio.info_fmt",
                sample_rate=d["sample_rate"],
                channels=d["channels"],
            )
        return t("settings.audio.none_selected")

    def _get_selectedInputIndex(self) -> int:
        return self._selected_device_index("input")

    def _set_selectedInputIndex(self, index: int):
        self._select_device("input", index)

    def _get_selectedOutputIndex(self) -> int:
        return self._selected_device_index("output")

    def _set_selectedOutputIndex(self, index: int):
        self._select_device("output", index)

    def _get_inputDeviceInfo(self) -> str:
        return self._device_info("input")

    def _get_outputDeviceInfo(self) -> str:
        return self._device_info("output")

    # 音频测试
    @Slot()
    def testInputDevice(self):
        """测试输入设备（录音）."""
        if self._testing_input:
            return

        idx = self._get_selectedInputIndex()
        if idx < 0 or idx >= len(self._input_devices):
            self.statusMessage.emit(t("settings.audio.select_input"))
            return

        device = self._input_devices[idx]
        self._testing_input = True
        self.statusMessage.emit(t("settings.audio.start_input_test"))

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

        self.statusMessage.emit(
            t("settings.audio.speak_prompt", duration=duration)
        )
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
            self.statusMessage.emit(t("settings.audio.input_no_signal"))
            self.testComplete.emit("input", False)
        elif max_amplitude > 0.8:
            self.statusMessage.emit(t("settings.audio.input_overload"))
            self.testComplete.emit("input", True)
        else:
            self.statusMessage.emit(
                t("settings.audio.input_ok", level=f"{max_amplitude:.1%}")
            )
            self.testComplete.emit("input", True)

    @Slot()
    def testOutputDevice(self):
        """测试输出设备（播放）."""
        if self._testing_output:
            return

        idx = self._get_selectedOutputIndex()
        if idx < 0 or idx >= len(self._output_devices):
            self.statusMessage.emit(t("settings.audio.select_output"))
            return

        device = self._output_devices[idx]
        self._testing_output = True
        self.statusMessage.emit(t("settings.audio.start_output_test"))

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

        self.statusMessage.emit(t("settings.audio.playing_tone"))
        time.sleep(0.5)

        t_arr = np.linspace(0, duration, int(sample_rate * duration))
        audio = 0.3 * np.sin(2 * np.pi * frequency * t_arr)

        fade_samples = int(0.1 * sample_rate)
        audio[:fade_samples] *= np.linspace(0, 1, fade_samples)
        audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)

        sd.play(audio, samplerate=sample_rate, device=device_id)
        sd.wait()

        self.statusMessage.emit(t("settings.audio.output_ok"))
        self.testComplete.emit("output", True)
