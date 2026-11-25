import asyncio
import threading
import time
from collections.abc import Callable
from typing import Protocol

import numpy as np

from src.audio_codecs.audio_converter import AudioConverter
from src.audio_codecs.mixer import AudioMixer, AudioTrackHandle
from src.audio_codecs.opus_codec import OpusCodec, parse_opus_toc
from src.audio_codecs.stream_manager import AudioStreamManager
from src.constants.constants import AudioConfig
from src.logging import get_logger
from src.utils.audio_device import AudioDeviceManager, DeviceConfig
from src.utils.config_manager import ConfigManager

logger = get_logger()


class AudioListener(Protocol):
    """音频监听器协议"""

    def on_audio_data(self, audio_data: np.ndarray) -> None:
        """接收音频数据

        Args:
            audio_data: float32 音频数据
        """
        ...


class AudioCodec:
    """音频编解码器 - 协调器模式

    组合各个组件，协调数据流

    数据流：
    - 输入：设备(float32) → 下混+重采样(float32) → Opus编码(float32→bytes) → 网络
    - 输出：网络 → Opus解码(bytes→float32) → 重采样+上混(float32) → 设备(float32)
    """

    def __init__(self, config=None, audio_config: AudioConfig | None = None):
        """Initialize without loading or mutating process configuration."""
        self.config = config if config is not None else ConfigManager.from_dict()
        self.audio_config = (
            audio_config
            if audio_config is not None
            else AudioConfig.from_config(self.config)
        )

        # 组件（依赖注入）
        self.device_manager = AudioDeviceManager(self.config, self.audio_config)
        self.opus_codec = OpusCodec(
            input_sample_rate=self.audio_config.INPUT_SAMPLE_RATE,
            output_sample_rate=self.audio_config.OUTPUT_SAMPLE_RATE,
            channels=self.audio_config.CHANNELS,
        )
        self.converter = AudioConverter()
        self.stream_manager = None

        # 多轨输出混音（前景：TTS/通知；背景：外部媒体自动闪避）
        self._output_lock = threading.RLock()
        self._tts_output_frames = 0.0
        self._tts_playback_until = 0.0
        self._tts_clear_generation = 0
        self.mixer = AudioMixer(self.audio_config.OUTPUT_SAMPLE_RATE)
        self._mix_chunk = int(self.audio_config.OUTPUT_SAMPLE_RATE * 0.02)  # 20ms

        # 监听器（线程安全）
        self._encoded_callback: Callable | None = None
        self._encode_gate: Callable[[], bool] | None = None
        self._audio_listeners: list[AudioListener] = []
        self._listeners_lock = threading.Lock()

        # 设备配置（初始化后填充）
        self.device_config: DeviceConfig | None = None

        # AEC（Self far：播放回调最终 PCM 作参考），initialize 时按配置创建
        self._aec = None

        # 状态标记
        self._is_closing = False
        self._closed = False
        self._server_opus_logged = False
        self._last_output_status_log = 0.0

    def _rebuild_pipeline_components(self) -> None:
        """重新加载音频配置并重建 Opus / 转换管线 / AEC."""
        self.audio_config.reload(self.config)
        self.device_config = self.device_manager.load_or_detect_devices()

        self.opus_codec.close()
        self.opus_codec = OpusCodec(
            input_sample_rate=self.audio_config.INPUT_SAMPLE_RATE,
            output_sample_rate=self.audio_config.OUTPUT_SAMPLE_RATE,
            channels=self.audio_config.CHANNELS,
        )
        self.opus_codec.initialize()

        self._configure_pipeline()
        self._setup_aec()

    async def initialize(self):
        """初始化所有组件

        流程：
        1. 加载/检测设备、刷新协议配置并构建 Opus/转换/AEC 管线
        2. 创建并启动音频流
        """
        try:
            self._rebuild_pipeline_components()

            self.stream_manager = AudioStreamManager(self.device_config)
            self.stream_manager.create_streams(
                input_callback=self._input_callback,
                output_callback=self._output_callback,
            )
            self.stream_manager.start()

            logger.info("AudioCodec 初始化完成")

        except Exception as e:
            logger.error(f"初始化音频设备失败: {e}", exc_info=True)
            await self.close()
            raise

    def _input_callback(self, indata, frames, time_info, status):
        """输入回调：设备 → 编码 → 发送

        数据流：多声道/高采样率 → 下混 → 重采样 → Opus编码 → 网络

        Args:
            indata: float32 音频数据，shape (frames, channels)
            frames: 帧数
            time_info: 时间信息
            status: 状态标志
        """
        if status and "overflow" not in str(status).lower():
            logger.warning(f"输入流状态: {status}")

        if self._is_closing:
            return

        try:
            # 1. 格式转换（下混 + 重采样）
            # 保留 indata 的 (frames, channels) 形状，让 downmix_to_mono 正确下混
            audio_converted = self.converter.convert_input(
                indata, self.audio_config.INPUT_FRAME_SIZE
            )
            if audio_converted is None:
                return  # 数据不足，等待下一帧

            # 1.5 AEC：以播放回调抽取的 far 参考消回声（旁路时原样返回）
            if self._aec is not None and self._aec.active:
                audio_converted = self._aec.process_near(audio_converted)

            # 2. Opus 编码（float32 输入）
            if self._encoded_callback and (
                self._encode_gate is None or self._encode_gate()
            ):
                try:
                    opus_data = self.opus_codec.encode(
                        audio_converted, self.audio_config.INPUT_FRAME_SIZE
                    )
                    self._encoded_callback(opus_data)
                except Exception as e:
                    logger.warning(f"编码失败: {e}", exc_info=True)

            # 3. 通知监听器（线程安全）
            with self._listeners_lock:
                for listener in self._audio_listeners:
                    try:
                        listener.on_audio_data(audio_converted.copy())
                    except Exception as e:
                        logger.warning(f"监听器处理失败: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"输入回调错误: {e}", exc_info=True)

    def _output_callback(self, outdata, frames, time_info, status):
        # Clear/abort must not race a device callback rebuilding converter PCM.
        with self._output_lock:
            self._render_output(outdata, frames, time_info, status)

    def _render_output(self, outdata, frames, time_info, status):
        """输出回调：解码 → 转换 → 播放

        数据流：队列 → 重采样 → 上混 → 设备

        循环从队列取 chunk 喂给 convert_output，直到 resampler
        内部缓冲区凑够 frames 或队列耗尽。解决采样率非整除
        （如 16kHz→44100Hz）或服务器帧时长不匹配时的卡顿问题。

        Args:
            outdata: float32 输出缓冲区，shape (frames, channels)
            frames: 帧数
            time_info: 时间信息
            status: 状态标志
        """
        if status:
            # 限流：回调内写日志（文件 IO）本身会加剧欠载，2 秒最多一条
            now = time.monotonic()
            if now - self._last_output_status_log > 2.0:
                self._last_output_status_log = now
                logger.warning(f"输出流状态: {status}")

        try:
            audio_converted = None
            output_rate = (
                self.device_config.output_sample_rate
                if self.device_config is not None
                else self.audio_config.OUTPUT_SAMPLE_RATE
            )
            while audio_converted is None:
                mixed = self.mixer.pull(
                    self._mix_chunk,
                    flush_silence=self._tts_output_frames > 0,
                )
                if mixed.pcm is None:
                    break
                if mixed.tts_samples:
                    if self._tts_output_frames <= 0:
                        self._tts_output_frames = self.converter.pending_output_samples
                    self._tts_output_frames += (
                        mixed.tts_samples
                        * output_rate
                        / self.audio_config.OUTPUT_SAMPLE_RATE
                    )
                audio_converted = self.converter.convert_output(mixed.pcm, frames)

            if audio_converted is None:
                audio_converted = self.converter.drain_output_buffer(frames)

            if audio_converted is None or len(audio_converted) < frames:
                outdata.fill(0.0)
                if audio_converted is not None and len(audio_converted) > 0:
                    outdata[: len(audio_converted)] = audio_converted
            else:
                outdata[:] = audio_converted[:frames]

            if self._tts_output_frames > 0:
                # PortAudio times share its own clock, so only their delta is
                # combined with monotonic time. Include Bluetooth/device lead.
                device_lead = max(
                    0.0,
                    float(getattr(time_info, "outputBufferDacTime", 0.0))
                    - float(getattr(time_info, "currentTime", 0.0)),
                )
                self._tts_playback_until = (
                    time.monotonic() + device_lead + frames / output_rate
                )
                self._tts_output_frames = max(
                    0.0,
                    self._tts_output_frames
                    - (len(audio_converted) if audio_converted is not None else 0),
                )

            # AEC far：设备实际写出的最终 PCM（全部轨道混合，含静音保持连续）
            if self._aec is not None and self._aec.active:
                self._aec.feed_far(outdata)

            self.mixer.notify_output_rendered()

        except Exception as e:
            logger.error(f"输出回调错误: {e}", exc_info=True)
            outdata.fill(0.0)

    def _configure_pipeline(self):
        """配置格式转换管线（设备 ↔ 协议）。

        根据设备原生参数和协议要求参数，设置输入/输出转换链。
        输入：设备(f32, device_rate, device_ch) → 协议(f32, 16kHz, 1ch)
        输出：协议(f32, opus_out_rate, 1ch) → 设备(f32, device_rate, device_ch)
        """
        self.converter.setup_input_converter(
            from_rate=self.device_config.input_sample_rate,
            to_rate=self.audio_config.INPUT_SAMPLE_RATE,
            from_channels=self.device_config.input_channels,
            to_channels=1,
        )
        self.converter.setup_output_converter(
            from_rate=self.audio_config.OUTPUT_SAMPLE_RATE,
            to_rate=self.device_config.output_sample_rate,
            from_channels=1,
            to_channels=self.device_config.output_channels,
        )

        # 协议输出采样率可能随配置热重载变化，混音器与块大小随之重建
        # （此时音频流已停止，无并发读取）
        self.mixer.reset(self.audio_config.OUTPUT_SAMPLE_RATE)
        self._mix_chunk = int(self.audio_config.OUTPUT_SAMPLE_RATE * 0.02)
        self._tts_clear_generation += 1
        self._tts_output_frames = 0.0
        self._tts_playback_until = 0.0

    def _setup_aec(self):
        """按 AEC_OPTIONS.ENABLED 创建/重建 AEC 引擎（Self far）。

        设备热重载后 far 采样率可能变化，须随 device_config 重建；
        创建失败不抛出，引擎自身旁路（active=False）。
        """
        if self._aec is not None:
            self._aec.close()
            self._aec = None

        try:
            config = self.config
            if not bool(config.get_config("AEC_OPTIONS.ENABLED", False)):
                logger.info("AEC 未启用（AEC_OPTIONS.ENABLED=false）")
                return

            from src.audio_processing.aec_engine import AecEngine

            frame_delay = config.get_config("AEC_OPTIONS.FRAME_DELAY", 3)
            self._aec = AecEngine(
                near_rate=self.audio_config.INPUT_SAMPLE_RATE,
                far_rate=self.device_config.output_sample_rate,
                # FRAME_DELAY 以协议帧为单位，换算毫秒后叠加基础输出延迟
                delay_ms=40 + int(frame_delay) * self.audio_config.FRAME_DURATION,
                enable_preprocess=bool(
                    config.get_config("AEC_OPTIONS.ENABLE_PREPROCESS", True)
                ),
            )
        except Exception as e:
            logger.warning(f"创建 AEC 引擎失败，已旁路: {e}", exc_info=True)
            self._aec = None

    # === 对外接口（保持兼容） ===

    @property
    def aec_active(self) -> bool:
        """AEC 引擎是否在位且工作中（音乐并行策略等依赖此判断）."""
        aec = self._aec
        return bool(aec is not None and aec.active)

    def set_encode_gate(self, gate: Callable[[], bool] | None) -> None:
        """Skip network encoding while retaining PCM listeners and AEC."""
        self._encode_gate = gate

    def set_encoded_callback(self, callback: Callable[[bytes], None]):
        """设置编码回调

        Args:
            callback: 回调函数，接收 Opus 编码数据
        """
        self._encoded_callback = callback
        if callback:
            logger.info("已设置编码音频回调")
        else:
            logger.info("已清除编码音频回调")

    def add_audio_listener(self, listener: AudioListener):
        """添加音频监听器（线程安全）

        Args:
            listener: 实现 AudioListener 协议的监听器对象
        """
        with self._listeners_lock:
            if listener not in self._audio_listeners:
                self._audio_listeners.append(listener)
                logger.info(f"已添加音频监听器: {listener.__class__.__name__}")

    def remove_audio_listener(self, listener: AudioListener):
        """移除音频监听器（线程安全）

        Args:
            listener: 要移除的监听器对象
        """
        with self._listeners_lock:
            if listener in self._audio_listeners:
                self._audio_listeners.remove(listener)
                logger.info(f"已移除音频监听器: {listener.__class__.__name__}")

    async def write_audio(self, opus_data: bytes):
        """解码并播放音频（Opus → 扬声器）

        自动从 Opus TOC 字节检测帧时长，无需依赖客户端配置。

        Args:
            opus_data: Opus 编码数据
        """
        try:
            toc_info = parse_opus_toc(opus_data)
            if toc_info is None:
                return

            if not self._server_opus_logged:
                self._server_opus_logged = True
                logger.info(
                    f"服务端 Opus 参数: "
                    f"{toc_info['mode']} {toc_info['bandwidth_hz']} | "
                    f"帧时长 {toc_info['duration_ms']}ms "
                    f"({toc_info['frame_ms']}ms×{toc_info['num_frames']})"
                )

            frame_size = int(
                self.audio_config.OUTPUT_SAMPLE_RATE * toc_info["duration_ms"] / 1000
            )
            audio_float32 = self.opus_codec.decode(opus_data, frame_size)

            self.mixer.push_tts(audio_float32)

        except Exception as e:
            logger.warning(f"音频写入失败: {e}", exc_info=True)

    def get_background_track(self) -> AudioTrackHandle:
        """获取背景媒体轨道句柄（前景发声时自动闪避）."""
        return self.mixer.get_track_handle(
            "background", is_closing=lambda: self._is_closing
        )

    def get_notification_track(self) -> AudioTrackHandle:
        """获取通知轨道句柄（与 TTS 同级前景优先级）."""
        return self.mixer.get_track_handle(
            "notification", is_closing=lambda: self._is_closing
        )

    async def write_background_pcm(self, pcm_float32: np.ndarray):
        """写入背景轨道 PCM（float32），带水位背压."""
        await self.mixer.push_with_backpressure(
            "background", pcm_float32, is_closing=lambda: self._is_closing
        )

    def set_notification_playback_callbacks(
        self,
        progress_callback: Callable[[int], None] | None = None,
        drained_callback: Callable[[], None] | None = None,
    ) -> None:
        """设置通知播放回调（由音频线程调用，回调必须自行线程安全地转发）."""
        self.mixer.set_notification_callbacks(progress_callback, drained_callback)

    async def write_notification_pcm(self, pcm_float32: np.ndarray):
        """写入通知 PCM，并按通知队列水位提供解码背压."""
        await self.mixer.push_with_backpressure(
            "notification", pcm_float32, is_closing=lambda: self._is_closing
        )

    async def wait_for_tts_playback(self) -> None:
        """Wait for FIFO, converted output and the final device buffer to drain.

        A generation change releases an obsolete waiter when the user aborts;
        it must never wait for audio belonging to the next reply.
        """
        generation = self._tts_clear_generation
        while not self._is_closing:
            with self._output_lock:
                if generation != self._tts_clear_generation:
                    return
                if (
                    self.mixer.track_size("tts") == 0
                    and self._tts_output_frames <= 0
                    and time.monotonic() >= self._tts_playback_until
                ):
                    return
            await asyncio.sleep(0.01)

    async def clear_audio_queue(self):
        """清空 TTS 播放队列（打断/中止时用；背景/通知队列不受影响）."""
        with self._output_lock:
            self._tts_clear_generation += 1
            self._tts_output_frames = 0.0
            self._tts_playback_until = 0.0
            self._server_opus_logged = False
            self.converter.clear_output_buffer()
            count = self.mixer.clear_track("tts")
        if count > 0:
            logger.info(f"清空 TTS 队列，丢弃 {count} 样本")

    async def clear_background_queue(self):
        """清空背景媒体播放队列（停止/跳转时用；TTS 队列不受影响）."""
        count = self.mixer.clear_track("background")
        if count > 0:
            logger.info(f"清空背景媒体队列，丢弃 {count} 样本")

    async def clear_notification_queue(self):
        """清空通知播放队列（取消通知时用；TTS/背景队列不受影响）."""
        count = self.mixer.clear_track("notification")
        if count > 0:
            logger.info(f"清空通知队列，丢弃 {count} 样本")

    def stop_streams_for_enumeration(self) -> None:
        """停掉本编解码器占用的 sounddevice 流，供热插拔枚举前调用.

        调用后必须再 ``reload_devices()`` 或自行 ``create_streams``，否则无采集/播放。
        """
        if self.stream_manager:
            if self.stream_manager.stop() is False:
                raise RuntimeError("音频流尚未关闭，无法重新枚举设备")
            logger.info("AudioCodec: 已停止音频流（供设备枚举）")

    async def reload_devices(self, *, reenumerate: bool = True):
        """热重载音频设备配置

        流程：
        1. 停止当前音频流
        2. （可选）重初始化 PortAudio 并重新枚举（利于后连蓝牙出现）
        3. 重新加载设备配置 + 协议配置
        4. 重建格式转换器 + Opus 编解码器
        5. 重新创建并启动音频流

        Args:
            reenumerate: 是否在停流后强制刷新 PortAudio 设备表

        Returns:
            bool: 是否成功
        """
        logger.info("AudioCodec: 开始热重载音频设备...")
        replacement = None

        try:
            # 1. 停止当前流（必须在 PortAudio reinit 之前）
            if self.stream_manager:
                if self.stream_manager.stop() is False:
                    raise RuntimeError("旧音频流尚未关闭，无法重载设备")
                logger.debug("AudioCodec: 已停止当前音频流")
            self.stream_manager = None
            await self.clear_audio_queue()

            # 2. 热插拔：重建 PortAudio 上下文后再按名称匹配
            if reenumerate:
                from src.utils.audio_utils import refresh_portaudio_devices

                refresh_portaudio_devices(reinitialize=True)

            # 3. 重新加载设备配置并重建 Opus / 转换器 / AEC
            self.device_manager.config.reload_config(apply_paths=False)
            self._rebuild_pipeline_components()
            logger.info(
                "AudioCodec: 新设备配置 - 输入ID: "
                f"{self.device_config.input_device_id}, 输出ID: "
                f"{self.device_config.output_device_id}"
            )

            # 4. 重新创建并启动音频流，成功后才安装替换 manager。
            replacement = AudioStreamManager(self.device_config)
            replacement.create_streams(
                input_callback=self._input_callback,
                output_callback=self._output_callback,
            )

            # 7. 启动音频流
            replacement.start()
            self.stream_manager = replacement
            self._closed = False

            logger.info("AudioCodec: 音频设备热重载完成")
            return True

        except Exception as e:
            logger.error(f"AudioCodec: 热重载音频设备失败: {e}", exc_info=True)
            if replacement is not None:
                # Preserve ownership if native close itself fails, so later
                # close/reload can retry without releasing live callback DSP.
                self.stream_manager = replacement
                if replacement.stop() is not False:
                    self.stream_manager = None
            return False

    def _release_resources_sync(self, *, emergency: bool = False) -> None:
        """在音频流已停止后，同步释放 AEC / 转换器 / Opus / 监听器."""
        if self._aec is not None:
            self._aec.close()
            self._aec = None

        if self.converter:
            self.converter.close()

        if self.opus_codec:
            self.opus_codec.close()

        try:
            with self._listeners_lock:
                self._audio_listeners.clear()
        except Exception as e:
            if emergency:
                logger.warning(
                    f"清理音频监听器失败（锁可能已损坏）: {e}", exc_info=True
                )
            else:
                raise

    async def close(self):
        """关闭音频编解码器"""
        self._is_closing = True

        try:
            # 1. 停止音频流；close 失败时保留 DSP 供仍存活的回调使用。
            if self.stream_manager:
                if self.stream_manager.stop() is False:
                    raise RuntimeError("音频流尚未关闭，保留编解码资源供重试")

            # 2. 清空队列
            await self.clear_audio_queue()
            await self.clear_background_queue()
            await self.clear_notification_queue()

            # 3. 释放 AEC、转换器、Opus 与监听器（须在流停止后）
            self._release_resources_sync()

            logger.info("AudioCodec 已关闭")
            self._closed = True

        except Exception as e:
            logger.error(f"关闭音频编解码器失败: {e}", exc_info=True)
        finally:
            self._is_closing = False

    def __del__(self):
        """析构函数 - 执行同步清理"""
        # 如果已正确关闭或正在关闭，跳过
        if getattr(self, "_closed", False) or getattr(self, "_is_closing", False):
            return

        logger.warning("AudioCodec 未正确关闭，执行紧急清理（建议使用 async close()）")

        try:
            # 1. 停止音频流（同步）
            if self.stream_manager:
                if self.stream_manager.stop() is False:
                    logger.error("音频流关闭失败，不能释放回调仍使用的编解码资源")
                    return

            # 2. 清空队列（同步版本）
            count = self.mixer.clear_all()
            if count > 0:
                logger.debug(f"析构函数清空了 {count} 样本音频")

            # 3. 释放 AEC、转换器、Opus 与监听器
            self._release_resources_sync(emergency=True)

            logger.debug("AudioCodec 析构清理完成")

        except Exception as e:
            logger.error(f"析构函数清理失败: {e}", exc_info=True)
