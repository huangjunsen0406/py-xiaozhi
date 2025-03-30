import opuslib
import asyncio
from edge_tts import Communicate
import soundfile as sf
import io
from pydub import AudioSegment
import numpy as np


class TtsUtility:
    def __init__(self, audio_config):
        self.audio_config = audio_config

    async def generate_tts(self, text: str) -> bytes:
        """使用 Edge TTS 生成语音"""
        communicate = Communicate(text, "zh-CN-XiaoxiaoNeural")
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data

    async def text_to_opus_audio(self, text: str) -> list:
        """将文本转换为 Opus 音频"""

        # 1. 生成 TTS 语音
        audio_data = await self.generate_tts(text)

        try:
            # 2. 将 MP3 数据转换为 PCM 数据
            audio = AudioSegment.from_mp3(io.BytesIO(audio_data))

            # 修改采样率与通道数，以匹配录音数据格式
            audio = audio.set_frame_rate(self.audio_config.INPUT_SAMPLE_RATE)
            audio = audio.set_channels(self.audio_config.CHANNELS)

            wav_data = io.BytesIO()
            audio.export(wav_data, format='wav')
            wav_data.seek(0)

            # 使用 soundfile 读取 WAV 数据
            data, samplerate = sf.read(wav_data)

            # 确保数据是 16 位整数格式
            if data.dtype != np.int16:
                data = (data * 32767).astype(np.int16)

            # 转换为字节序列
            raw_data = data.tobytes()

        except Exception as e:
            print(f"[ERROR] 音频转换失败: {e}")
            return None

        # 3. 初始化Opus编码器
        encoder = opuslib.Encoder(
            self.audio_config.INPUT_SAMPLE_RATE,
            self.audio_config.CHANNELS,
            opuslib.APPLICATION_VOIP
        )

        # 4. 分帧编码
        frame_size = self.audio_config.INPUT_FRAME_SIZE  # 与录音时的帧大小保持一致
        opus_frames = []

        # 按帧处理所有音频数据
        for i in range(0, len(raw_data), frame_size * 2):  # 16bit = 2bytes/sample
            chunk = raw_data[i:i + frame_size * 2]
            if len(chunk) < frame_size * 2:
                # 填充最后一帧
                chunk += b'\x00' * (frame_size * 2 - len(chunk))
            opus_frame = encoder.encode(chunk, frame_size)
            opus_frames.append(opus_frame)

        return opus_frames
