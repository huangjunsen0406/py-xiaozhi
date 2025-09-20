import asyncio
import gc
import time
from collections import deque
from typing import Optional

import numpy as np
import opuslib
import sounddevice as sd
import soxr

from src.audio_codecs.aec_processor import AECProcessor
from src.constants.constants import AudioConfig
from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class AudioCodec:
    """
    音频编解码器，负责录音编码和播放解码
    主要功能：
    1. 录音：麦克风 -> 重采样16kHz -> Opus编码 -> 发送
    2. 播放：接收 -> Opus解码24kHz -> 播放队列 -> 扬声器
    """

    def __init__(self):
        # 获取配置管理器
        self.config = ConfigManager.get_instance()

        # Opus编解码器：录音16kHz编码，播放24kHz解码
        self.opus_encoder = None
        self.opus_decoder = None

        # 设备信息
        self.device_input_sample_rate = None
        self.device_output_sample_rate = None
        self.mic_device_id = None  # 麦克风设备ID（固定索引，一经写入配置不再覆盖）
        self.speaker_device_id = None  # 扬声器设备ID（固定索引）

        # 重采样器：录音重采样到16kHz，播放重采样到设备采样率
        self.input_resampler = None  # 设备采样率 -> 16kHz
        self.output_resampler = None  # 24kHz -> 设备采样率(播放用)

        # 重采样缓冲区
        self._resample_input_buffer = deque()
        self._resample_output_buffer = deque()

        self._device_input_frame_size = None
        self._is_closing = False

        # 音频流对象
        self.input_stream = None  # 录音流
        self.output_stream = None  # 播放流

        # 队列：唤醒词检测和播放缓冲
        self._wakeword_buffer = asyncio.Queue(maxsize=100)
        self._output_buffer = asyncio.Queue(maxsize=500)

        # 实时编码回调（直接发送，不走队列）
        self._encoded_audio_callback = None

        # AEC处理器
        self.aec_processor = AECProcessor()
        self._aec_enabled = False

    # -----------------------
    # 自动选择设备的辅助方法
    # -----------------------
    def _auto_pick_device(self, kind: str) -> Optional[int]:
        """
        自动挑选一个稳定的设备索引（优先 WASAPI）。
        kind: 'input' 或 'output'
        """
        assert kind in ("input", "output")
        try:
            devices = sd.query_devices()
            hostapis = sd.query_hostapis()
        except Exception as e:
            logger.warning(f"枚举设备失败：{e}")
            return None

        # 1) 优先使用 WASAPI HostAPI 的默认设备（如果有）
        wasapi_index = None
        for idx, ha in enumerate(hostapis):
            name = ha.get("name", "")
            if "WASAPI" in name:
                key = "default_input_device" if kind == "input" else "default_output_device"
                cand = ha.get(key, -1)
                if isinstance(cand, int) and 0 <= cand < len(devices):
                    d = devices[cand]
                    if (kind == "input" and d["max_input_channels"] > 0) or (
                        kind == "output" and d["max_output_channels"] > 0
                    ):
                        wasapi_index = cand
                        break
        if wasapi_index is not None:
            return wasapi_index

        # 2) 退而求其次：根据系统默认（kind）返回的名字匹配 + 优先 WASAPI
        try:
            default_info = sd.query_devices(kind=kind)  # 不会触发 -1
            default_name = default_info.get("name")
        except Exception:
            default_name = None

        scored = []
        for i, d in enumerate(devices):
            if kind == "input":
                ok = d["max_input_channels"] > 0
            else:
                ok = d["max_output_channels"] > 0
            if not ok:
                continue
            host_name = hostapis[d["hostapi"]]["name"]
            score = 0
            if "WASAPI" in host_name:
                score += 5
            if default_name and d["name"] == default_name:
                score += 10
            # 小加分：常见可用端点关键词
            if any(k in d["name"] for k in ["Speaker", "扬声器", "Realtek", "USB", "AMD", "HDMI", "Monitor"]):
                score += 1
            scored.append((score, i))

        if scored:
            scored.sort(reverse=True)
            return scored[0][1]

        # 3) 最后保底：第一个具备通道的设备
        for i, d in enumerate(devices):
            if (kind == "input" and d["max_input_channels"] > 0) or (
                kind == "output" and d["max_output_channels"] > 0
            ):
                return i
        return None

    async def initialize(self):
        """
        初始化音频设备.
        """
        try:
            # 显示并选择音频设备（首次自动选择并写入配置；之后不覆盖）
            await self._select_audio_devices()

            # 安全获取输入/输出默认信息（避免 -1）
            if self.mic_device_id is not None and self.mic_device_id >= 0:
                input_device_info = sd.query_devices(self.mic_device_id)
            else:
                input_device_info = sd.query_devices(kind="input")

            if self.speaker_device_id is not None and self.speaker_device_id >= 0:
                output_device_info = sd.query_devices(self.speaker_device_id)
            else:
                output_device_info = sd.query_devices(kind="output")

            self.device_input_sample_rate = int(input_device_info["default_samplerate"])
            self.device_output_sample_rate = int(output_device_info["default_samplerate"])

            frame_duration_sec = AudioConfig.FRAME_DURATION / 1000
            self._device_input_frame_size = int(self.device_input_sample_rate * frame_duration_sec)

            logger.info(
                f"输入采样率: {self.device_input_sample_rate}Hz, 输出: {self.device_output_sample_rate}Hz"
            )

            await self._create_resamplers()

            # 不强行改全局默认，让每个流自己带 device / samplerate
            sd.default.samplerate = None
            sd.default.channels = AudioConfig.CHANNELS
            sd.default.dtype = np.int16

            await self._create_streams()

            # Opus 编解码器
            self.opus_encoder = opuslib.Encoder(
                AudioConfig.INPUT_SAMPLE_RATE,
                AudioConfig.CHANNELS,
                opuslib.APPLICATION_AUDIO,
            )
            self.opus_decoder = opuslib.Decoder(
                AudioConfig.OUTPUT_SAMPLE_RATE, AudioConfig.CHANNELS
            )

            # 初始化AEC处理器
            try:
                await self.aec_processor.initialize()
                self._aec_enabled = True
                logger.info("AEC处理器启用")
            except Exception as e:
                logger.warning(f"AEC处理器初始化失败，将使用原始音频: {e}")
                self._aec_enabled = False

            logger.info("音频初始化完成")
        except Exception as e:
            logger.error(f"初始化音频设备失败: {e}")
            await self.close()
            raise

    async def _create_resamplers(self):
        """
        创建重采样器 输入：设备采样率 -> 16kHz（用于编码） 输出：24kHz -> 设备采样率（播放用）
        """
        # 输入重采样器：设备采样率 -> 16kHz（用于编码）
        if self.device_input_sample_rate != AudioConfig.INPUT_SAMPLE_RATE:
            self.input_resampler = soxr.ResampleStream(
                self.device_input_sample_rate,
                AudioConfig.INPUT_SAMPLE_RATE,
                AudioConfig.CHANNELS,
                dtype="int16",
                quality="QQ",
            )
            logger.info(f"输入重采样: {self.device_input_sample_rate}Hz -> 16kHz")

        # 输出重采样器：24kHz -> 设备采样率
        if self.device_output_sample_rate != AudioConfig.OUTPUT_SAMPLE_RATE:
            self.output_resampler = soxr.ResampleStream(
                AudioConfig.OUTPUT_SAMPLE_RATE,
                self.device_output_sample_rate,
                AudioConfig.CHANNELS,
                dtype="int16",
                quality="QQ",
            )
            logger.info(
                f"输出重采样: {AudioConfig.OUTPUT_SAMPLE_RATE}Hz -> {self.device_output_sample_rate}Hz"
            )

    async def _select_audio_devices(self):
        """
        显示并选择音频设备.
        优先使用配置文件中的设备，如果没有则自动选择并保存到配置（只在首次写入，之后不覆盖）。
        """
        try:
            audio_config = self.config.get_config("AUDIO_DEVICES", {}) or {}

            # 是否已有明确配置（决定是否写回）
            had_cfg_input = "input_device_id" in audio_config
            had_cfg_output = "output_device_id" in audio_config

            input_device_id = audio_config.get("input_device_id")
            output_device_id = audio_config.get("output_device_id")

            devices = sd.query_devices()

            # --- 验证配置中的输入设备 ---
            if input_device_id is not None:
                try:
                    if isinstance(input_device_id, int) and 0 <= input_device_id < len(devices):
                        d = devices[input_device_id]
                        if d["max_input_channels"] > 0:
                            self.mic_device_id = input_device_id
                            logger.info(f"使用配置的麦克风设备: [{input_device_id}] {d['name']}")
                        else:
                            logger.warning(f"配置的设备[{input_device_id}]不支持输入，将自动选择")
                            self.mic_device_id = None
                    else:
                        logger.warning(f"配置的输入设备ID[{input_device_id}]无效，将自动选择")
                        self.mic_device_id = None
                except Exception as e:
                    logger.warning(f"验证配置输入设备失败: {e}，将自动选择")
                    self.mic_device_id = None
            else:
                self.mic_device_id = None

            # --- 验证配置中的输出设备 ---
            if output_device_id is not None:
                try:
                    if isinstance(output_device_id, int) and 0 <= output_device_id < len(devices):
                        d = devices[output_device_id]
                        if d["max_output_channels"] > 0:
                            self.speaker_device_id = output_device_id
                            logger.info(f"使用配置的扬声器设备: [{output_device_id}] {d['name']}")
                        else:
                            logger.warning(f"配置的设备[{output_device_id}]不支持输出，将自动选择")
                            self.speaker_device_id = None
                    else:
                        logger.warning(f"配置的输出设备ID[{output_device_id}]无效，将自动选择")
                        self.speaker_device_id = None
                except Exception as e:
                    logger.warning(f"验证配置输出设备失败: {e}，将自动选择")
                    self.speaker_device_id = None
            else:
                self.speaker_device_id = None

            # --- 若任一为空，则自动选择（仅首次会写入配置） ---
            picked_input = self.mic_device_id
            picked_output = self.speaker_device_id

            if picked_input is None:
                picked_input = self._auto_pick_device("input")
                if picked_input is not None:
                    self.mic_device_id = picked_input
                    d = devices[picked_input]
                    logger.info(f"自动选择麦克风设备: [{picked_input}] {d['name']}")
                else:
                    logger.warning("未找到可用输入设备（将使用系统默认，且不写入索引）。")

            if picked_output is None:
                picked_output = self._auto_pick_device("output")
                if picked_output is not None:
                    self.speaker_device_id = picked_output
                    d = devices[picked_output]
                    logger.info(f"自动选择扬声器设备: [{picked_output}] {d['name']}")
                else:
                    logger.warning("未找到可用输出设备（将使用系统默认，且不写入索引）。")

            # --- 仅当配置原本缺少对应条目时，才写入（避免第二次覆盖） ---
            need_write = (not had_cfg_input and picked_input is not None) or (not had_cfg_output and picked_output is not None)
            if need_write:
                await self._save_default_audio_config(
                    input_device_id=picked_input if not had_cfg_input else None,
                    output_device_id=picked_output if not had_cfg_output else None,
                )

        except Exception as e:
            logger.warning(f"设备选择失败: {e}，将使用系统默认（不写入配置）")
            # 允许 None，让 PortAudio 用系统默认端点
            self.mic_device_id = self.mic_device_id if isinstance(self.mic_device_id, int) else None
            self.speaker_device_id = self.speaker_device_id if isinstance(self.speaker_device_id, int) else None

    async def _save_default_audio_config(self, input_device_id: Optional[int], output_device_id: Optional[int]):
        """
        保存默认音频设备配置到配置文件（仅针对传入的非空设备；不会覆盖已有字段）。
        """
        try:
            devices = sd.query_devices()
            audio_config_patch = {}

            # 保存输入设备配置
            if input_device_id is not None and 0 <= input_device_id < len(devices):
                d = devices[input_device_id]
                audio_config_patch.update({
                    "input_device_id": input_device_id,
                    "input_device_name": d["name"],
                    "input_sample_rate": int(d["default_samplerate"]),
                })

            # 保存输出设备配置
            if output_device_id is not None and 0 <= output_device_id < len(devices):
                d = devices[output_device_id]
                audio_config_patch.update({
                    "output_device_id": output_device_id,
                    "output_device_name": d["name"],
                    "output_sample_rate": int(d["default_samplerate"]),
                })

            if audio_config_patch:
                # merge：不覆盖已有键
                current = self.config.get_config("AUDIO_DEVICES", {}) or {}
                for k, v in audio_config_patch.items():
                    if k not in current:  # 只在原来没有时写入
                        current[k] = v
                success = self.config.update_config("AUDIO_DEVICES", current)
                if success:
                    logger.info("已写入默认音频设备到配置（首次）。")
                else:
                    logger.warning("保存音频设备配置失败")
        except Exception as e:
            logger.error(f"保存默认音频设备配置失败: {e}")

    async def _create_streams(self):
        """
        创建音频流.
        """
        try:
            # 麦克风输入流
            self.input_stream = sd.InputStream(
                device=self.mic_device_id,  # None=系统默认；或固定索引
                samplerate=self.device_input_sample_rate,
                channels=AudioConfig.CHANNELS,
                dtype=np.int16,
                blocksize=self._device_input_frame_size,
                callback=self._input_callback,
                finished_callback=self._input_finished_callback,
                latency="low",
            )

            # 根据设备支持的采样率选择输出采样率
            if self.device_output_sample_rate == AudioConfig.OUTPUT_SAMPLE_RATE:
                # 设备支持24kHz，直接使用
                output_sample_rate = AudioConfig.OUTPUT_SAMPLE_RATE
                device_output_frame_size = AudioConfig.OUTPUT_FRAME_SIZE
            else:
                # 设备不支持24kHz，使用设备默认采样率并启用重采样
                output_sample_rate = self.device_output_sample_rate
                device_output_frame_size = int(
                    self.device_output_sample_rate * (AudioConfig.FRAME_DURATION / 1000)
                )

            self.output_stream = sd.OutputStream(
                device=self.speaker_device_id,  # None=系统默认；或固定索引
                samplerate=output_sample_rate,
                channels=AudioConfig.CHANNELS,
                dtype=np.int16,
                blocksize=device_output_frame_size,
                callback=self._output_callback,
                finished_callback=self._output_finished_callback,
                latency="low",
            )

            self.input_stream.start()
            self.output_stream.start()

            logger.info("音频流已启动")

        except Exception as e:
            logger.error(f"创建音频流失败: {e}")
            raise

    def _input_callback(self, indata, frames, time_info, status):
        """
        录音回调，硬件驱动调用 处理流程：原始音频 -> 重采样16kHz -> 编码发送 + 唤醒词检测.
        """
        if status and "overflow" not in str(status).lower():
            logger.warning(f"输入流状态: {status}")

        if self._is_closing:
            return

        try:
            audio_data = indata.copy().flatten()

            # 重采样到16kHz（如果设备不是16kHz）
            if self.input_resampler is not None:
                audio_data = self._process_input_resampling(audio_data)
                if audio_data is None:
                    return

            # 应用AEC处理（仅 macOS 需要）
            if (self._aec_enabled and len(audio_data) == AudioConfig.INPUT_FRAME_SIZE and self.aec_processor._is_macos):
                try:
                    audio_data = self.aec_processor.process_audio(audio_data)
                except Exception as e:
                    logger.warning(f"AEC处理失败，使用原始音频: {e}")

            # 实时编码并发送（不走队列，减少延迟）
            if (
                self._encoded_audio_callback
                and len(audio_data) == AudioConfig.INPUT_FRAME_SIZE
            ):
                try:
                    pcm_data = audio_data.astype(np.int16).tobytes()
                    encoded_data = self.opus_encoder.encode(
                        pcm_data, AudioConfig.INPUT_FRAME_SIZE
                    )
                    if encoded_data:
                        self._encoded_audio_callback(encoded_data)
                except Exception as e:
                    logger.warning(f"实时录音编码失败: {e}")

            # 同时提供给唤醒词检测（走队列）
            self._put_audio_data_safe(self._wakeword_buffer, audio_data.copy())

        except Exception as e:
            logger.error(f"输入回调错误: {e}")

    def _process_input_resampling(self, audio_data):
        """
        输入重采样到16kHz.
        """
        try:
            resampled_data = self.input_resampler.resample_chunk(audio_data, last=False)
            if len(resampled_data) > 0:
                self._resample_input_buffer.extend(resampled_data.astype(np.int16))

            expected_frame_size = AudioConfig.INPUT_FRAME_SIZE
            if len(self._resample_input_buffer) < expected_frame_size:
                return None

            frame_data = []
            for _ in range(expected_frame_size):
                frame_data.append(self._resample_input_buffer.popleft())

            return np.array(frame_data, dtype=np.int16)

        except Exception as e:
            logger.error(f"输入重采样失败: {e}")
            return None

    def _put_audio_data_safe(self, queue, audio_data):
        """
        安全入队，队列满时丢弃最旧数据.
        """
        try:
            queue.put_nowait(audio_data)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
                queue.put_nowait(audio_data)
            except asyncio.QueueEmpty:
                queue.put_nowait(audio_data)

    def _output_callback(self, outdata: np.ndarray, frames: int, time_info, status):
        """
        播放回调，硬件驱动调用 从播放队列取数据输出到扬声器.
        """
        if status:
            if "underflow" not in str(status).lower():
                logger.warning(f"输出流状态: {status}")

        try:
            if self.output_resampler is not None:
                # 需要重采样：24kHz -> 设备采样率
                self._output_callback_with_resample(outdata, frames)
            else:
                # 直接播放：24kHz
                self._output_callback_direct(outdata, frames)

        except Exception as e:
            logger.error(f"输出回调错误: {e}")
            outdata.fill(0)

    def _output_callback_direct(self, outdata: np.ndarray, frames: int):
        """
        直接播放24kHz数据（设备支持24kHz时）
        """
        try:
            # 从播放队列获取音频数据
            audio_data = self._output_buffer.get_nowait()

            if len(audio_data) >= frames * AudioConfig.CHANNELS:
                output_frames = audio_data[: frames * AudioConfig.CHANNELS]
                outdata[:] = output_frames.reshape(-1, AudioConfig.CHANNELS)
            else:
                out_len = len(audio_data) // AudioConfig.CHANNELS
                if out_len > 0:
                    outdata[:out_len] = audio_data[: out_len * AudioConfig.CHANNELS].reshape(
                        -1, AudioConfig.CHANNELS
                    )
                if out_len < frames:
                    outdata[out_len:] = 0

        except asyncio.QueueEmpty:
            # 无数据时输出静音
            outdata.fill(0)

    def _output_callback_with_resample(self, outdata: np.ndarray, frames: int):
        """
        重采样播放（24kHz -> 设备采样率）
        """
        try:
            # 持续处理24kHz数据进行重采样
            while len(self._resample_output_buffer) < frames * AudioConfig.CHANNELS:
                try:
                    audio_data = self._output_buffer.get_nowait()
                    # 24kHz -> 设备采样率重采样
                    resampled_data = self.output_resampler.resample_chunk(
                        audio_data, last=False
                    )
                    if len(resampled_data) > 0:
                        self._resample_output_buffer.extend(
                            resampled_data.astype(np.int16)
                        )
                except asyncio.QueueEmpty:
                    break

            need = frames * AudioConfig.CHANNELS
            if len(self._resample_output_buffer) >= need:
                frame_data = [self._resample_output_buffer.popleft() for _ in range(need)]
                output_array = np.array(frame_data, dtype=np.int16)
                outdata[:] = output_array.reshape(-1, AudioConfig.CHANNELS)
            else:
                # 数据不足时输出静音
                outdata.fill(0)

        except Exception as e:
            logger.warning(f"重采样输出失败: {e}")
            outdata.fill(0)

    def _input_finished_callback(self):
        """
        输入流结束.
        """
        logger.info("输入流已结束")

    def _reference_finished_callback(self):
        """
        参考信号流结束.
        """
        logger.info("参考信号流已结束")

    def _output_finished_callback(self):
        """
        输出流结束.
        """
        logger.info("输出流已结束")

    async def reinitialize_stream(self, is_input=True):
        """
        重建音频流.
        """
        if self._is_closing:
            return False if is_input else None

        try:
            if is_input:
                if self.input_stream:
                    self.input_stream.stop()
                    self.input_stream.close()

                self.input_stream = sd.InputStream(
                    device=self.mic_device_id,  # <- 修复：带上设备索引，避免回落到可能不稳定的默认端点
                    samplerate=self.device_input_sample_rate,
                    channels=AudioConfig.CHANNELS,
                    dtype=np.int16,
                    blocksize=self._device_input_frame_size,
                    callback=self._input_callback,
                    finished_callback=self._input_finished_callback,
                    latency="low",
                )
                self.input_stream.start()
                logger.info("输入流重新初始化成功")
                return True
            else:
                if self.output_stream:
                    self.output_stream.stop()
                    self.output_stream.close()

                # 根据设备支持的采样率选择输出采样率
                if self.device_output_sample_rate == AudioConfig.OUTPUT_SAMPLE_RATE:
                    # 设备支持24kHz，直接使用
                    output_sample_rate = AudioConfig.OUTPUT_SAMPLE_RATE
                    device_output_frame_size = AudioConfig.OUTPUT_FRAME_SIZE
                else:
                    # 设备不支持24kHz，使用设备默认采样率并启用重采样
                    output_sample_rate = self.device_output_sample_rate
                    device_output_frame_size = int(
                        self.device_output_sample_rate
                        * (AudioConfig.FRAME_DURATION / 1000)
                    )

                self.output_stream = sd.OutputStream(
                    device=self.speaker_device_id,  # 指定扬声器设备ID
                    samplerate=output_sample_rate,
                    channels=AudioConfig.CHANNELS,
                    dtype=np.int16,
                    blocksize=device_output_frame_size,
                    callback=self._output_callback,
                    finished_callback=self._output_finished_callback,
                    latency="low",
                )
                self.output_stream.start()
                logger.info("输出流重新初始化成功")
                return None
        except Exception as e:
            stream_type = "输入" if is_input else "输出"
            logger.error(f"{stream_type}流重建失败: {e}")
            if is_input:
                return False
            else:
                raise

    async def get_raw_audio_for_detection(self) -> Optional[bytes]:
        """
        获取唤醒词音频数据.
        """
        try:
            if self._wakeword_buffer.empty():
                return None

            audio_data = self._wakeword_buffer.get_nowait()

            if hasattr(audio_data, "tobytes"):
                return audio_data.tobytes()
            elif hasattr(audio_data, "astype"):
                return audio_data.astype("int16").tobytes()
            else:
                return audio_data

        except asyncio.QueueEmpty:
            return None
        except Exception as e:
            logger.error(f"获取唤醒词音频数据失败: {e}")
            return None

    def set_encoded_audio_callback(self, callback):
        """
        设置编码回调.
        """
        self._encoded_audio_callback = callback

        if callback:
            logger.info("启用实时编码")
        else:
            logger.info("禁用编码回调")

    def is_aec_enabled(self) -> bool:
        """
        检查AEC是否启用.
        """
        return self._aec_enabled

    def get_aec_status(self) -> dict:
        """
        获取AEC状态信息.
        """
        if not self._aec_enabled or not self.aec_processor:
            return {"enabled": False, "reason": "AEC未启用或初始化失败"}
        
        try:
            return {
                "enabled": True,
                **self.aec_processor.get_status()
            }
        except Exception as e:
            return {"enabled": False, "reason": f"获取状态失败: {e}"}

    def toggle_aec(self, enabled: bool) -> bool:
        """
        切换AEC启用状态.
        
        Args:
            enabled: 是否启用AEC
            
        Returns:
            实际的AEC状态
        """
        if not self.aec_processor:
            logger.warning("AEC处理器未初始化，无法切换状态")
            return False
        
        self._aec_enabled = enabled and self.aec_processor._is_initialized
        
        if enabled and not self._aec_enabled:
            logger.warning("无法启用AEC，处理器未正确初始化")
        
        logger.info(f"AEC状态: {'启用' if self._aec_enabled else '禁用'}")
        return self._aec_enabled

    async def write_audio(self, opus_data: bytes):
        """
        解码音频并播放 网络接收的Opus数据 -> 解码24kHz -> 播放队列.
        """
        try:
            # Opus解码为24kHz PCM数据
            pcm_data = self.opus_decoder.decode(
                opus_data, AudioConfig.OUTPUT_FRAME_SIZE
            )

            audio_array = np.frombuffer(pcm_data, dtype=np.int16)

            expected_length = AudioConfig.OUTPUT_FRAME_SIZE * AudioConfig.CHANNELS
            if len(audio_array) != expected_length:
                logger.warning(
                    f"解码音频长度异常: {len(audio_array)}, 期望: {expected_length}"
                )
                return

            # 放入播放队列
            self._put_audio_data_safe(self._output_buffer, audio_array)

        except opuslib.OpusError as e:
            logger.warning(f"Opus解码失败，丢弃此帧: {e}")
        except Exception as e:
            logger.warning(f"音频写入失败，丢弃此帧: {e}")

    async def wait_for_audio_complete(self, timeout=10.0):
        """
        等待播放完成.
        """
        start = time.time()

        while not self._output_buffer.empty() and time.time() - start < timeout:
            await asyncio.sleep(0.05)

        await asyncio.sleep(0.3)

        if not self._output_buffer.empty():
            output_remaining = self._output_buffer.qsize()
            logger.warning(f"音频播放超时，剩余队列 - 输出: {output_remaining} 帧")

    async def clear_audio_queue(self):
        """
        清空音频队列.
        """
        cleared_count = 0

        queues_to_clear = [
            self._wakeword_buffer,
            self._output_buffer,
        ]

        for queue in queues_to_clear:
            while not queue.empty():
                try:
                    queue.get_nowait()
                    cleared_count += 1
                except asyncio.QueueEmpty:
                    break

        if self._resample_input_buffer:
            cleared_count += len(self._resample_input_buffer)
            self._resample_input_buffer.clear()

        if self._resample_output_buffer:
            cleared_count += len(self._resample_output_buffer)
            self._resample_output_buffer.clear()

        if cleared_count > 0:
            logger.info(f"清空音频队列，丢弃 {cleared_count} 帧音频数据")

        if cleared_count > 100:
            gc.collect()
            logger.debug("执行垃圾回收以释放内存")

    async def start_streams(self):
        """
        启动音频流.
        """
        try:
            if self.input_stream and not self.input_stream.active:
                try:
                    self.input_stream.start()
                except Exception as e:
                    logger.warning(f"启动输入流时出错: {e}")
                    await self.reinitialize_stream(is_input=True)

            if self.output_stream and not self.output_stream.active:
                try:
                    self.output_stream.start()
                except Exception as e:
                    logger.warning(f"启动输出流时出错: {e}")
                    await self.reinitialize_stream(is_input=False)

            logger.info("音频流已启动")
        except Exception as e:
            logger.error(f"启动音频流失败: {e}")

    async def stop_streams(self):
        """
        停止音频流.
        """
        try:
            if self.input_stream and self.input_stream.active:
                self.input_stream.stop()
        except Exception as e:
            logger.warning(f"停止输入流失败: {e}")

        try:
            if self.output_stream and self.output_stream.active:
                self.output_stream.stop()
        except Exception as e:
            logger.warning(f"停止输出流失败: {e}")

    async def _cleanup_resampler(self, resampler, name):
        """
        清理重采样器.
        """
        if resampler:
            try:
                if hasattr(resampler, "resample_chunk"):
                    empty_array = np.array([], dtype=np.int16)
                    resampler.resample_chunk(empty_array, last=True)
            except Exception as e:
                logger.warning(f"清理{name}重采样器失败: {e}")

    async def close(self):
        """
        关闭音频编解码器.
        """
        if self._is_closing:
            return

        self._is_closing = True
        logger.info("开始关闭音频编解码器...")

        try:
            await self.clear_audio_queue()

            if self.input_stream:
                try:
                    self.input_stream.stop()
                    self.input_stream.close()
                except Exception as e:
                    logger.warning(f"关闭输入流失败: {e}")
                finally:
                    self.input_stream = None

            if self.output_stream:
                try:
                    self.output_stream.stop()
                    self.output_stream.close()
                except Exception as e:
                    logger.warning(f"关闭输出流失败: {e}")
                finally:
                    self.output_stream = None

            await self._cleanup_resampler(self.input_resampler, "输入")
            await self._cleanup_resampler(self.output_resampler, "输出")
            self.input_resampler = None
            self.output_resampler = None

            self._resample_input_buffer.clear()
            self._resample_output_buffer.clear()

            # 关闭AEC处理器
            if self.aec_processor:
                try:
                    await self.aec_processor.close()
                except Exception as e:
                    logger.warning(f"关闭AEC处理器失败: {e}")
                finally:
                    self.aec_processor = None

            self.opus_encoder = None
            self.opus_decoder = None

            gc.collect()

            logger.info("音频资源已完全释放")
        except Exception as e:
            logger.error(f"关闭音频编解码器过程中发生错误: {e}")
        finally:
            self._is_closing = True

    def __del__(self):
        """
        析构函数.
        """
        if not self._is_closing:
            logger.warning("AudioCodec未正确关闭，请调用close()")
