import os
import pyttsx3
import io
import numpy as np
import opuslib
from pydub import AudioSegment
import soundfile as sf
import tempfile

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class TtsUtility:
    def __init__(self, audio_config):
        self.audio_config = audio_config
        logger.debug("初始化TTS工具，配置采样率: %s, 通道数: %s", 
                    audio_config.INPUT_SAMPLE_RATE, 
                    audio_config.CHANNELS)
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 150)  # 设置语速
            self.engine.setProperty('volume', 1)  # 设置音量
            voices = self.engine.getProperty('voices')
            self.engine.setProperty('voice', voices[0].id)  # 选择男性声音
            logger.info("TTS引擎初始化成功")
        except Exception as e:
            logger.error("TTS引擎初始化失败: %s", e)
            raise

    def generate_tts(self, text: str) -> bytes:
        """使用 pyttsx3 生成语音并返回音频数据"""
        logger.debug("开始生成TTS音频，文本长度: %d 字符", len(text))
        try:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix='.wav'
            ) as temp_file:
                temp_path = temp_file.name
                temp_file.close()  # 关闭文件，以便其他进程访问
                
                logger.debug("保存TTS音频到临时文件: %s", temp_path)
                self.engine.save_to_file(text, temp_path)
                self.engine.runAndWait()
                
                with open(temp_path, 'rb') as audio_file:
                    audio_data = audio_file.read()
                    
                logger.debug("TTS音频生成完成，大小: %d 字节", len(audio_data))
                os.remove(temp_path)  # 删除临时文件
                return audio_data
        except Exception as e:
            logger.error("生成TTS音频失败: %s", e, exc_info=True)
            return None

    def generate_silence(self, duration_ms: int, sample_rate: int, channels: int) -> AudioSegment:
        """生成指定时长的静音"""
        logger.debug(f"生成 {duration_ms}ms 的静音预缓冲")
        try:
            # 创建指定时长的静音
            silence = AudioSegment.silent(
                duration=duration_ms,  # 时长（毫秒）
                frame_rate=sample_rate  # 采样率
            )
            # 设置通道数
            silence = silence.set_channels(channels)
            return silence
        except Exception as e:
            logger.error(f"生成静音失败: {e}", exc_info=True)
            return None

    async def text_to_opus_audio(self, text: str):
        """将文本转换为 Opus 音频，添加静音预缓冲"""
        logger.debug("开始将文本转换为Opus音频")
        try:
            audio_data = self.generate_tts(text)
            if audio_data is None:
                logger.error("无法生成TTS音频，终止转换过程")
                return None

            # 将音频数据加载为 AudioSegment
            logger.debug("将原始音频数据加载为AudioSegment")
            audio = AudioSegment.from_file(
                io.BytesIO(audio_data), format='wav'
            )

            # 修改采样率与通道数，以匹配录音数据格式
            logger.debug("调整音频参数为目标格式: 采样率=%d, 通道数=%d", 
                        self.audio_config.INPUT_SAMPLE_RATE, 
                        self.audio_config.CHANNELS)
            audio = audio.set_frame_rate(self.audio_config.INPUT_SAMPLE_RATE)
            audio = audio.set_channels(self.audio_config.CHANNELS)
            
            # 创建150ms的静音前导
            silence = self.generate_silence(
                150,  # 150毫秒的静音
                self.audio_config.INPUT_SAMPLE_RATE,
                self.audio_config.CHANNELS
            )
            
            # 合并静音和TTS音频
            if silence:
                logger.debug("添加静音预缓冲到TTS音频开头")
                audio = silence + audio

            wav_data = io.BytesIO()
            audio.export(wav_data, format='wav')
            wav_data.seek(0)

            # 使用 soundfile 读取 WAV 数据
            logger.debug("使用soundfile读取WAV数据")
            data, samplerate = sf.read(wav_data)
            logger.debug("读取到音频: 采样率=%d, 形状=%s, 类型=%s", 
                        samplerate, data.shape, data.dtype)

            # 确保数据是 16 位整数格式
            if data.dtype != np.int16:
                logger.debug("转换音频格式为16位整数")
                data = (data * 32767).astype(np.int16)

            # 转换为字节序列
            raw_data = data.tobytes()
            logger.debug("原始音频字节大小: %d", len(raw_data))

            # 初始化 Opus 编码器
            opus_encoder = opuslib.Encoder(
                self.audio_config.INPUT_SAMPLE_RATE,
                self.audio_config.CHANNELS,
                opuslib.APPLICATION_AUDIO
            )

            # 分帧并编码
            opus_frames = []
            frame_size_bytes = 2 * self.audio_config.CHANNELS * self.audio_config.FRAME_SIZE
            
            for i in range(0, len(raw_data), frame_size_bytes):
                frame = raw_data[i:i + frame_size_bytes]
                
                # 确保帧大小正确
                if len(frame) < frame_size_bytes:
                    # 如果最后一帧不足，则用静音补充
                    frame = frame + b'\x00' * (frame_size_bytes - len(frame))
                
                # 编码为 Opus 格式
                opus_frame = opus_encoder.encode(frame, self.audio_config.FRAME_SIZE)
                opus_frames.append(opus_frame)

            logger.debug("编码为 %d 个 Opus 帧", len(opus_frames))
            return opus_frames

        except Exception as e:
            logger.error("音频转换失败: %s", e, exc_info=True)
            return None
