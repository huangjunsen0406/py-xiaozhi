import asyncio
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from src.constants.constants import AudioConfig
from src.logging import get_logger
from src.utils.config_manager import ConfigManager
from src.utils.resource_finder import get_app_root, get_user_keywords_path

logger = get_logger()

_STOP_SENTINEL = object()


class WakeWordDetector:

    def __init__(self):
        self.audio_codec = None
        self._running = False
        self._paused = False
        self._detection_task = None
        self._audio_queue: Optional[asyncio.Queue] = None

        self._last_detection_time = 0
        self._detection_cooldown = 1.5

        self.on_detected_callback: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

        self.enabled = False
        self._model_loaded = False
        self._model_dir: Optional[Path] = None
        self._keyword_spotter = None
        self._stream = None

        # 添加锁保护 sherpa-onnx 对象的访问
        self._onnx_lock = threading.Lock()
        self._stopping = False  # 标记是否正在停止

        self._sample_rate = AudioConfig.INPUT_SAMPLE_RATE
        self._num_threads = 4
        self._provider = "cpu"
        self._max_active_paths = 2
        self._keywords_score = 1.8
        self._keywords_threshold = 0.2
        self._num_trailing_blanks = 1

    async def initialize(self, model_path: Optional[str] = None) -> bool:
        try:
            # 1. 检查配置是否启用
            config = ConfigManager.get_instance()
            if not config.get_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False):
                logger.info("唤醒词功能已禁用")
                self.enabled = False
                return False

            # 2. 加载配置参数
            self._load_config(config)

            # 3. 确定模型路径
            if model_path is None:
                model_path = config.get_config("WAKE_WORD_OPTIONS.MODEL_PATH", "models")

            self._model_dir = get_app_root() / model_path

            if not self._model_dir.exists():
                logger.error(f"模型目录不存在: {self._model_dir}")
                self.enabled = False
                return False

            # 4. 停止旧检测循环并释放旧模型
            if self._running:
                await self.stop()
            self._release_model()

            # 5. 加载新模型
            if not self._load_model():
                self.enabled = False
                return False

            self.enabled = True
            self._model_loaded = True
            logger.info(f"唤醒词检测器初始化成功: {self._model_dir}")
            return True

        except Exception as e:
            logger.error(f"唤醒词检测器初始化失败: {e}", exc_info=True)
            self.enabled = False
            return False

    def _load_config(self, config: ConfigManager):
        self._num_threads = config.get_config("WAKE_WORD_OPTIONS.NUM_THREADS", 4)
        self._provider = config.get_config("WAKE_WORD_OPTIONS.PROVIDER", "cpu")
        self._max_active_paths = config.get_config("WAKE_WORD_OPTIONS.MAX_ACTIVE_PATHS", 2)
        self._keywords_score = config.get_config("WAKE_WORD_OPTIONS.KEYWORDS_SCORE", 1.8)
        self._keywords_threshold = config.get_config("WAKE_WORD_OPTIONS.KEYWORDS_THRESHOLD", 0.2)
        self._num_trailing_blanks = config.get_config("WAKE_WORD_OPTIONS.NUM_TRAILING_BLANKS", 1)

        # Validate
        if not 0.1 <= self._keywords_threshold <= 1.0:
            logger.warning(f"关键词阈值 {self._keywords_threshold} 超出范围，重置为0.25")
            self._keywords_threshold = 0.25

        if not 0.1 <= self._keywords_score <= 10.0:
            logger.warning(f"关键词分数 {self._keywords_score} 超出范围，重置为2.0")
            self._keywords_score = 2.0

        logger.debug(f"KWS配置: 阈值={self._keywords_threshold}, 分数={self._keywords_score}")

    def _load_model(self) -> bool:
        """Load sherpa-onnx KeywordSpotter model."""
        try:
            import sherpa_onnx

        # Check required files
            encoder_path = self._model_dir / "encoder.onnx"
            decoder_path = self._model_dir / "decoder.onnx"
            joiner_path = self._model_dir / "joiner.onnx"
            tokens_path = self._model_dir / "tokens.txt"

            # keywords.txt 优先使用用户目录下的自定义文件
            lang = ConfigManager.get_instance().get_config("WAKE_WORD_OPTIONS.WAKE_WORD_LANG", "zh")
            keywords_path = get_user_keywords_path(lang)

            required_files = [encoder_path, decoder_path, joiner_path, tokens_path, keywords_path]
            for file_path in required_files:
                if not file_path.exists():
                    logger.error(f"模型文件不存在: {file_path}")
                    return False

            logger.info(f"加载 KeywordSpotter 模型: {self._model_dir}")

            # Create KeywordSpotter（加锁保护，与 _release_model/_process_audio 一致）
            with self._onnx_lock:
                self._keyword_spotter = sherpa_onnx.KeywordSpotter(
                    tokens=str(tokens_path),
                    encoder=str(encoder_path),
                    decoder=str(decoder_path),
                    joiner=str(joiner_path),
                    keywords_file=str(keywords_path),
                    num_threads=self._num_threads,
                    sample_rate=self._sample_rate,
                    feature_dim=80,
                    max_active_paths=self._max_active_paths,
                    keywords_score=self._keywords_score,
                    keywords_threshold=self._keywords_threshold,
                    num_trailing_blanks=self._num_trailing_blanks,
                    provider=self._provider,
                )

            logger.info("KeywordSpotter 模型加载成功")
            return True

        except ImportError as e:
            logger.error(f"sherpa_onnx 导入失败: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"加载模型失败: {e}", exc_info=True)
            return False

    def _release_model(self):
        if not self._model_loaded:
            return
        with self._onnx_lock:
            try:
                # 先置空引用，再删除，避免竞态
                stream = self._stream
                spotter = self._keyword_spotter
                self._stream = None
                self._keyword_spotter = None

                if stream is not None:
                    del stream

                if spotter is not None:
                    del spotter

                self._model_loaded = False
                logger.debug("模型资源已释放")

            except Exception as e:
                logger.debug(f"释放模型资源时出错: {e}")

    def on_detected(self, callback: Callable):
        self.on_detected_callback = callback

    def on_audio_data(self, audio_data: np.ndarray):
        if not self.enabled or not self._running or self._paused:
            return

        if self._audio_queue is None:
            return

        try:
            self._audio_queue.put_nowait(audio_data.copy())
        except asyncio.QueueFull:
            try:
                self._audio_queue.get_nowait()
                self._audio_queue.put_nowait(audio_data.copy())
            except (asyncio.QueueEmpty, asyncio.QueueFull):
                pass
        except Exception as e:
            logger.debug(f"音频数据入队失败: {type(e).__name__}: {e}")

    async def start(self, audio_codec) -> bool:
        if not self.enabled:
            logger.warning("唤醒词功能未启用")
            return False

        if not self._keyword_spotter:
            logger.error("模型未加载，请先调用 initialize()")
            return False

        try:
            self.audio_codec = audio_codec
            self._running = True
            self._paused = False

            # Create queue in event loop
            self._audio_queue = asyncio.Queue(maxsize=100)

            # Create detection stream
            self._stream = self._keyword_spotter.create_stream()

            # Register as audio listener
            self.audio_codec.add_audio_listener(self)

            # Start detection task
            self._detection_task = asyncio.create_task(self._detection_loop())

            logger.info("唤醒词检测器已启动")
            return True

        except Exception as e:
            logger.error(f"启动检测器失败: {e}", exc_info=True)
            return False

    async def stop(self):
        self._stopping = True
        self._running = False

        # Remove audio listener
        if self.audio_codec:
            self.audio_codec.remove_audio_listener(self)
            self.audio_codec = None

        # 用哨兵唤醒阻塞在 queue.get() 上的检测循环
        if self._audio_queue:
            try:
                self._audio_queue.put_nowait(_STOP_SENTINEL)
            except asyncio.QueueFull:
                try:
                    self._audio_queue.get_nowait()
                    self._audio_queue.put_nowait(_STOP_SENTINEL)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

        # 等待检测循环自然退出（由哨兵触发）
        if self._detection_task:
            try:
                await asyncio.wait_for(self._detection_task, timeout=1.0)
            except asyncio.TimeoutError:
                self._detection_task.cancel()
                try:
                    await self._detection_task
                except asyncio.CancelledError:
                    pass
            self._detection_task = None

        # Clear queue
        if self._audio_queue:
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            self._audio_queue = None

        with self._onnx_lock:
            if self._stream is not None:
                _stream = self._stream  # noqa: F841
                self._stream = None
                del _stream

        self._stopping = False
        logger.info("唤醒词检测器已停止")

    async def reload(self, model_path: Optional[str] = None) -> bool:
        was_running = self._running
        codec = self.audio_codec

        logger.info(f"热重载唤醒词模型: {model_path}")

        # Re-initialize with new model
        if not await self.initialize(model_path):
            return False

        # Restart if was running
        if was_running and codec:
            return await self.start(codec)

        return True

    async def shutdown(self):
        """Fully shutdown and release all resources."""
        await self.stop()
        self._release_model()
        self.enabled = False
        logger.info("唤醒词检测器已关闭")

    def pause(self):
        """Pause detection (keeps model loaded)."""
        self._paused = True

    def resume(self):
        """Resume detection."""
        self._paused = False

    async def _detection_loop(self):
        error_count = 0
        MAX_ERRORS = 5

        while self._running and not self._stopping:
            try:
                if self._paused or self._stopping:
                    await asyncio.sleep(0.1)
                    continue

                if not self._audio_queue:
                    await asyncio.sleep(0.1)
                    continue

                # 事件驱动：阻塞等待音频数据，避免 wait_for 在 Python 3.10
                # 取消 task 时产生 "Task was destroyed but it is pending!" 错误
                try:
                    audio_data = await self._audio_queue.get()
                except RuntimeError:
                    break

                # 停止哨兵：stop() 放入的特殊值，用于唤醒阻塞的 get()
                if audio_data is _STOP_SENTINEL:
                    break

                if audio_data is None or len(audio_data) == 0:
                    continue

                # 实时处理：收到一帧立刻送入模型，不累积
                await self._process_frame(audio_data)
                error_count = 0

            except asyncio.CancelledError:
                break
            except RuntimeError as e:
                if "no running event loop" in str(e) or "Event loop is closed" in str(e):
                    break
                error_count += 1
                logger.error(f"检测循环错误 ({error_count}/{MAX_ERRORS}): {e}")

                if error_count >= MAX_ERRORS:
                    logger.critical("达到最大错误次数，停止检测")
                    break

                await asyncio.sleep(1)
            except Exception as e:
                error_count += 1
                logger.error(f"检测循环错误 ({error_count}/{MAX_ERRORS}): {e}")

                if self.on_error:
                    try:
                        if asyncio.iscoroutinefunction(self.on_error):
                            await self.on_error(e)
                        else:
                            self.on_error(e)
                    except Exception as cb_error:
                        logger.error(f"错误回调失败: {cb_error}")

                if error_count >= MAX_ERRORS:
                    logger.critical("达到最大错误次数，停止检测")
                    break

                await asyncio.sleep(1)

    async def _process_frame(self, audio_data):
        if self._stopping:
            return

        detected_result = None

        with self._onnx_lock:
            if self._stopping or self._stream is None or self._keyword_spotter is None:
                return

            try:
                self._stream.accept_waveform(
                    sample_rate=self._sample_rate, waveform=audio_data
                )

                if not self._keyword_spotter.is_ready(self._stream):
                    return

                self._keyword_spotter.decode_stream(self._stream)
                result = self._keyword_spotter.get_result(self._stream)

                if result:
                    detected_result = result
                    self._keyword_spotter.reset_stream(self._stream)

            except Exception as e:
                logger.debug(f"处理音频帧时出错: {e}")

        if detected_result is not None:
            await self._handle_detection(detected_result)

    async def _handle_detection(self, result):
        # Anti-repeat check
        current_time = time.time()
        if current_time - self._last_detection_time < self._detection_cooldown:
            return

        self._last_detection_time = current_time

        # 短暂暂停检测，让打断流程完成，避免旧音频触发重复检测
        self._paused = True
        try:
            if self.on_detected_callback:
                try:
                    if asyncio.iscoroutinefunction(self.on_detected_callback):
                        await self.on_detected_callback(result, result)
                    else:
                        self.on_detected_callback(result, result)
                except Exception as e:
                    logger.error(f"唤醒词回调执行失败: {e}")
        finally:
            # 延迟后恢复检测（等待 abort + clear_audio_queue 完成）
            await asyncio.sleep(0.3)
            # 排空队列中残留的旧音频帧
            if self._audio_queue:
                while True:
                    try:
                        self._audio_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
            self._paused = False
