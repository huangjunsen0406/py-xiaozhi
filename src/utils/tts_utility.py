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

    async def text_to_opus_audio(self, text: str):
        """将文本转换为 Opus 音频"""
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

        except Exception as e:
            logger.error("音频转换失败: %s", e, exc_info=True)
            return None

        try:
            # 初始化 Opus 编码器
            logger.debug("初始化Opus编码器")
            encoder = opuslib.Encoder(
                self.audio_config.INPUT_SAMPLE_RATE,
                self.audio_config.CHANNELS,
                opuslib.APPLICATION_VOIP
            )

            # 分帧编码
            frame_size = self.audio_config.INPUT_FRAME_SIZE
            opus_frames = []

            # 16bit = 2bytes/sample
            total_frames = (len(raw_data) + frame_size * 2 - 1) // (frame_size * 2)
            logger.debug("开始编码音频，总帧数：%d", total_frames)
            
            for i in range(0, len(raw_data), frame_size * 2):
                chunk = raw_data[i:i + frame_size * 2]
                if len(chunk) < frame_size * 2:
                    # 填充最后一帧
                    padding_size = frame_size * 2 - len(chunk)
                    logger.debug("填充最后一帧，添加%d字节", padding_size)
                    chunk += b'\x00' * padding_size
                opus_frame = encoder.encode(chunk, frame_size)
                opus_frames.append(opus_frame)

            logger.info("Opus编码完成，生成%d个音频帧", len(opus_frames))
            return opus_frames
        except Exception as e:
            logger.error("Opus编码失败: %s", e, exc_info=True)
            return None
