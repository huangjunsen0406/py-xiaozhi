import asyncio
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import sherpa_onnx

from src.constants.constants import AudioConfig
from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class WakeWordDetector:

    def __init__(self):
        # 基本属性
        self.audio_codec = None
        self.is_running_flag = False
        self.paused = False
        self.detection_task = None

        # 防重复触发机制 - 缩短冷却时间提高响应
        self.last_detection_time = 0
        self.detection_cooldown = 1.5  # 1.5秒冷却时间

        # 回调函数
        self.on_detected_callback: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

        # 配置检查
        config = ConfigManager.get_instance()
        if not config.get_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False):
            logger.info("唤醒词功能已禁用")
            self.enabled = False
            return

        # 基本参数初始化
        self.enabled = True
        self.sample_rate = AudioConfig.INPUT_SAMPLE_RATE

        # Sherpa-ONNX KWS组件
        self.keyword_spotter = None
        self.stream = None

        # 初始化配置
        self._load_config(config)
        self._init_kws_model()
        self._validate_config()

    def _load_config(self, config):
        """加载配置参数"""
        # 模型路径配置
        self.model_dir = Path(config.get_config("WAKE_WORD_OPTIONS.MODEL_PATH", "models"))
        
        # KWS参数配置 - 优化速度
        self.num_threads = config.get_config("WAKE_WORD_OPTIONS.NUM_THREADS", 4)  # 增加线程数
        self.provider = config.get_config("WAKE_WORD_OPTIONS.PROVIDER", "cpu")
        self.max_active_paths = config.get_config("WAKE_WORD_OPTIONS.MAX_ACTIVE_PATHS", 2)  # 减少搜索路径
        self.keywords_score = config.get_config("WAKE_WORD_OPTIONS.KEYWORDS_SCORE", 1.8)  # 降低分数提升速度
        self.keywords_threshold = config.get_config("WAKE_WORD_OPTIONS.KEYWORDS_THRESHOLD", 0.2)  # 降低阈值提高灵敏度
        self.num_trailing_blanks = config.get_config("WAKE_WORD_OPTIONS.NUM_TRAILING_BLANKS", 1)

        logger.info(f"KWS配置加载完成 - 阈值: {self.keywords_threshold}, 分数: {self.keywords_score}")

    def _init_kws_model(self):
        """初始化Sherpa-ONNX KeywordSpotter模型"""
        try:
            # 检查模型文件
            encoder_path = self.model_dir / "encoder.onnx"
            decoder_path = self.model_dir / "decoder.onnx"
            joiner_path = self.model_dir / "joiner.onnx"
            tokens_path = self.model_dir / "tokens.txt"
            keywords_path = self.model_dir / "keywords.txt"

            required_files = [encoder_path, decoder_path, joiner_path, tokens_path, keywords_path]
            for file_path in required_files:
                if not file_path.exists():
                    raise FileNotFoundError(f"模型文件不存在: {file_path}")

            logger.info(f"加载Sherpa-ONNX KeywordSpotter模型: {self.model_dir}")

            # 创建KeywordSpotter
            self.keyword_spotter = sherpa_onnx.KeywordSpotter(
                tokens=str(tokens_path),
                encoder=str(encoder_path),
                decoder=str(decoder_path),
                joiner=str(joiner_path),
                keywords_file=str(keywords_path),
                num_threads=self.num_threads,
                sample_rate=self.sample_rate,
                feature_dim=80,
                max_active_paths=self.max_active_paths,
                keywords_score=self.keywords_score,
                keywords_threshold=self.keywords_threshold,
                num_trailing_blanks=self.num_trailing_blanks,
                provider=self.provider,
            )

            logger.info("Sherpa-ONNX KeywordSpotter模型加载成功")

        except Exception as e:
            logger.error(f"Sherpa-ONNX KeywordSpotter初始化失败: {e}", exc_info=True)
            self.enabled = False

    def on_detected(self, callback: Callable):
        """设置检测到唤醒词的回调函数"""
        self.on_detected_callback = callback

    async def start(self, audio_codec) -> bool:
        """启动唤醒词检测器"""
        if not self.enabled:
            logger.warning("唤醒词功能未启用")
            return False

        if not self.keyword_spotter:
            logger.error("KeywordSpotter未初始化")
            return False

        try:
            self.audio_codec = audio_codec
            self.is_running_flag = True
            self.paused = False

            # 创建检测流
            self.stream = self.keyword_spotter.create_stream()
            
            # 启动检测任务
            self.detection_task = asyncio.create_task(self._detection_loop())

            logger.info("Sherpa-ONNX KeywordSpotter检测器启动成功")
            return True
        except Exception as e:
            logger.error(f"启动KeywordSpotter检测器失败: {e}")
            self.enabled = False
            return False

    async def _detection_loop(self):
        """检测循环"""
        error_count = 0
        MAX_ERRORS = 5

        while self.is_running_flag:
            try:
                if self.paused:
                    await asyncio.sleep(0.1)
                    continue

                if not self.audio_codec:
                    await asyncio.sleep(0.5)
                    continue

                # 处理音频数据
                await self._process_audio()

                # 减少延迟提高响应速度
                await asyncio.sleep(0.005)
                error_count = 0

            except asyncio.CancelledError:
                break
            except Exception as e:
                error_count += 1
                logger.error(f"KWS检测循环错误({error_count}/{MAX_ERRORS}): {e}")
                
                # 调用错误回调
                if self.on_error:
                    try:
                        if asyncio.iscoroutinefunction(self.on_error):
                            await self.on_error(e)
                        else:
                            self.on_error(e)
                    except Exception as callback_error:
                        logger.error(f"执行错误回调时失败: {callback_error}")

                if error_count >= MAX_ERRORS:
                    logger.critical("达到最大错误次数，停止KWS检测")
                    break
                await asyncio.sleep(1)

    async def _process_audio(self):
        """处理音频数据 - 批量处理优化"""
        try:
            if not self.audio_codec or not self.stream:
                return

            # 批量获取多个音频帧以提高效率
            audio_batches = []
            for _ in range(3):  # 一次处理最多3帧
                data = await self.audio_codec.get_raw_audio_for_detection()
                if data:
                    audio_batches.append(data)

            if not audio_batches:
                return

            # 批量处理音频数据
            for data in audio_batches:
                # 转换音频格式
                if isinstance(data, bytes):
                    samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                else:
                    samples = np.array(data, dtype=np.float32)

                # 提供音频数据给KeywordSpotter
                self.stream.accept_waveform(sample_rate=self.sample_rate, waveform=samples)

            # 处理检测结果
            while self.keyword_spotter.is_ready(self.stream):
                self.keyword_spotter.decode_stream(self.stream)
                result = self.keyword_spotter.get_result(self.stream)
                
                if result and result.strip():
                    await self._handle_detection_result(result.strip())
                    # 重置流状态
                    self.keyword_spotter.reset_stream(self.stream)
                    break  # 检测到后立即处理，不继续批量处理

        except Exception as e:
            logger.debug(f"KWS音频处理错误: {e}")

    async def _handle_detection_result(self, result):
        """处理检测结果"""
        # 防重复触发检查
        current_time = time.time()
        if current_time - self.last_detection_time < self.detection_cooldown:
            return

        self.last_detection_time = current_time
        
        logger.info(f"🎯 检测到唤醒词: '{result}'")

        # 触发回调
        if self.on_detected_callback:
            try:
                if asyncio.iscoroutinefunction(self.on_detected_callback):
                    await self.on_detected_callback(result, result)
                else:
                    self.on_detected_callback(result, result)
            except Exception as e:
                logger.error(f"唤醒词回调执行失败: {e}")

    async def stop(self):
        """停止检测器"""
        self.is_running_flag = False

        if self.detection_task:
            self.detection_task.cancel()
            try:
                await self.detection_task
            except asyncio.CancelledError:
                pass

        logger.info("Sherpa-ONNX KeywordSpotter检测器已停止")

    async def pause(self):
        """暂停检测"""
        self.paused = True
        logger.debug("KWS检测已暂停")

    async def resume(self):
        """恢复检测"""
        self.paused = False
        logger.debug("KWS检测已恢复")

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.is_running_flag and not self.paused

    def _validate_config(self):
        """验证配置参数"""
        if not self.enabled:
            return

        # 验证阈值参数
        if not 0.1 <= self.keywords_threshold <= 1.0:
            logger.warning(f"关键词阈值 {self.keywords_threshold} 超出范围，重置为0.25")
            self.keywords_threshold = 0.25

        if not 0.1 <= self.keywords_score <= 10.0:
            logger.warning(f"关键词分数 {self.keywords_score} 超出范围，重置为2.0")
            self.keywords_score = 2.0

        logger.info(f"KWS配置验证完成 - 阈值: {self.keywords_threshold}, 分数: {self.keywords_score}")

    def get_performance_stats(self):
        """获取性能统计信息"""
        return {
            "enabled": self.enabled,
            "engine": "sherpa-onnx-kws",
            "provider": self.provider,
            "num_threads": self.num_threads,
            "keywords_threshold": self.keywords_threshold,
            "keywords_score": self.keywords_score,
            "is_running": self.is_running(),
        }

    def clear_cache(self):
        """清空缓存"""
        pass