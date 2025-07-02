import logging
import threading
import time

import numpy as np
import pyaudio
import webrtcvad

from src.constants.constants import AbortReason, DeviceState

# 配置日志
logger = logging.getLogger("VADDetector")


class VADDetector:
    """
    基于WebRTC VAD的语音活动检测器，用于检测用户打断.
    """

    def __init__(self, audio_codec, protocol, app_instance, loop):
        """初始化VAD检测器.

        参数:
            audio_codec: 音频编解码器实例
            protocol: 通信协议实例
            app_instance: 应用程序实例
            loop: 事件循环
        """
        self.audio_codec = audio_codec
        self.protocol = protocol
        self.app = app_instance
        self.loop = loop

        # VAD设置
        self.vad = webrtcvad.Vad()
        self.vad.set_mode(3)  # 设置最高灵敏度

        # 参数设置
        self.sample_rate = 16000
        self.frame_duration = 20  # 毫秒
        self.frame_size = int(self.sample_rate * self.frame_duration / 1000)
        self.speech_window = 5  # 连续检测到多少帧语音才触发打断
        self.energy_threshold = 300  # 能量阈值

        # 状态变量
        self.running = False
        self.paused = False
        self.thread = None
        self.speech_count = 0
        self.silence_count = 0
        self.triggered = False

        # 创建独立的PyAudio实例和流，避免与主音频流冲突
        self.pa = None
        self.stream = None

    def start(self):
        """
        启动VAD检测器.
        """
        if self.thread and self.thread.is_alive():
            logger.warning("VAD检测器已经在运行")
            return

        self.running = True
        self.paused = False

        # 初始化PyAudio和流
        self._initialize_audio_stream()

        # 启动检测线程
        self.thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.thread.start()
        logger.info("VAD检测器已启动")

    def stop(self):
        """
        停止VAD检测器.
        """
        self.running = False

        # 关闭音频流
        self._close_audio_stream()

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)

        logger.info("VAD检测器已停止")

    def pause(self):
        """
        暂停VAD检测.
        """
        self.paused = True
        logger.info("VAD检测器已暂停")

    def resume(self):
        """
        恢复VAD检测.
        """
        self.paused = False
        # 重置状态
        self.speech_count = 0
        self.silence_count = 0
        self.triggered = False
        logger.info("VAD检测器已恢复")

    def is_running(self):
        """
        检查VAD检测器是否正在运行.
        """
        return self.running and not self.paused

    def _initialize_audio_stream(self):
        """
        初始化独立的音频流.
        """
        try:
            # 创建PyAudio实例
            self.pa = pyaudio.PyAudio()

            # 获取默认输入设备
            device_index = None
            for i in range(self.pa.get_device_count()):
                device_info = self.pa.get_device_info_by_index(i)
                if device_info["maxInputChannels"] > 0:
                    device_index = i
                    break

            if device_index is None:
                logger.error("找不到可用的输入设备")
                return False

            # 创建输入流
            self.stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.frame_size,
                start=True,
            )

            logger.info(f"VAD检测器音频流已初始化，使用设备索引: {device_index}")
            return True

        except Exception as e:
            logger.error(f"初始化VAD音频流失败: {e}")
            return False

    def _close_audio_stream(self):
        """
        关闭音频流.
        """
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None

            if self.pa:
                self.pa.terminate()
                self.pa = None

            logger.info("VAD检测器音频流已关闭")
        except Exception as e:
            logger.error(f"关闭VAD音频流失败: {e}")

    def _detection_loop(self):
        """
        VAD检测主循环.
        """
        logger.info("VAD检测循环已启动")

        while self.running:
            # 如果暂停或者音频流未初始化，则跳过
            if self.paused or not self.stream:
                time.sleep(0.1)
                continue

            try:
                # 只在说话状态下进行检测
                if self.app.device_state == DeviceState.SPEAKING:
                    # 读取音频帧
                    frame = self._read_audio_frame()
                    if not frame:
                        time.sleep(0.01)
                        continue

                    # 检测是否是语音
                    is_speech = self._detect_speech(frame)

                    # 如果检测到语音并且达到触发条件，处理打断
                    if is_speech:
                        self._handle_speech_frame(frame)
                    else:
                        self._handle_silence_frame(frame)
                else:
                    # 不在说话状态，重置状态
                    self._reset_state()

            except Exception as e:
                logger.error(f"VAD检测循环出错: {e}")

            time.sleep(0.01)  # 小延迟，减少CPU使用

        logger.info("VAD检测循环已结束")

    def _read_audio_frame(self):
        """
        读取一帧音频数据.
        """
        try:
            if not self.stream or not self.stream.is_active():
                return None

            # 读取音频数据
            data = self.stream.read(self.frame_size, exception_on_overflow=False)
            return data
        except Exception as e:
            logger.error(f"读取音频帧失败: {e}")
            return None

    def _detect_speech(self, frame):
        """
        检测是否是语音.
        """
        try:
            # 确保帧长度正确
            if len(frame) != self.frame_size * 2:  # 16位音频，每个样本2字节
                return False

            # 使用VAD检测
            is_speech = self.vad.is_speech(frame, self.sample_rate)

            # 计算音频能量
            audio_data = np.frombuffer(frame, dtype=np.int16)
            energy = np.mean(np.abs(audio_data))

            # 结合VAD和能量阈值
            is_valid_speech = is_speech and energy > self.energy_threshold

            if is_valid_speech:
                logger.debug(
                    f"检测到语音 [能量: {energy:.2f}] [连续语音帧: {self.speech_count+1}]"
                )

            return is_valid_speech
        except Exception as e:
            logger.error(f"检测语音失败: {e}")
            return False

    def _handle_speech_frame(self, frame):
        """
        处理语音帧.
        """
        self.speech_count += 1
        self.silence_count = 0

        # 检测到足够的连续语音帧，触发打断
        if self.speech_count >= self.speech_window and not self.triggered:
            self.triggered = True
            logger.info("检测到持续语音，触发打断！")
            self._trigger_interrupt()

            # 立即暂停自己，防止重复触发
            self.paused = True
            logger.info("VAD检测器已自动暂停以防止重复触发")

            # 重置状态
            self.speech_count = 0
            self.silence_count = 0
            self.triggered = False

    def _handle_silence_frame(self, frame):
        """
        处理静音帧.
        """
        self.silence_count += 1
        self.speech_count = 0

    def _reset_state(self):
        """
        重置状态.
        """
        self.speech_count = 0
        self.silence_count = 0
        self.triggered = False

    def _trigger_interrupt(self):
        """
        触发打断.
        """
        # 通知应用程序中止当前语音输出
        self.app.schedule(
            lambda: self.app.abort_speaking(AbortReason.WAKE_WORD_DETECTED)
        )
