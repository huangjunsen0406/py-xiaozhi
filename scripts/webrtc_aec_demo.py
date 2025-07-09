"""WebRTC回声消除(AEC)演示脚本.

该脚本用于演示WebRTC APM库的回声消除功能:
1. 播放指定的音频文件(作为参考信号)
2. 同时录制麦克风输入(包含回声和环境声音)
3. 应用WebRTC回声消除处理
4. 保存原始录音和处理后的录音，以便比较

用法:
    python webrtc_aec_demo.py [音频文件路径]

示例:
    python webrtc_aec_demo.py 鞠婧祎.wav
"""

import ctypes
import os
import sys
import threading
import time
import wave
from ctypes import POINTER, Structure, byref, c_bool, c_float, c_int, c_short, c_void_p

import numpy as np
import pyaudio
import pygame
import soundfile as sf
from pygame import mixer

# 获取DLL文件的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
dll_path = os.path.join(
    project_root, "libs", "webrtc_apm", "win", "x86_64", "libwebrtc_apm.dll"
)

# 加载DLL
try:
    apm_lib = ctypes.CDLL(dll_path)
    print(f"成功加载WebRTC APM库: {dll_path}")
except Exception as e:
    print(f"加载WebRTC APM库失败: {e}")
    sys.exit(1)


# 定义结构体和枚举类型
class DownmixMethod(ctypes.c_int):
    AverageChannels = 0
    UseFirstChannel = 1


class NoiseSuppressionLevel(ctypes.c_int):
    Low = 0
    Moderate = 1
    High = 2
    VeryHigh = 3


class GainControllerMode(ctypes.c_int):
    AdaptiveAnalog = 0
    AdaptiveDigital = 1
    FixedDigital = 2


class ClippingPredictorMode(ctypes.c_int):
    ClippingEventPrediction = 0
    AdaptiveStepClippingPeakPrediction = 1
    FixedStepClippingPeakPrediction = 2


# 定义Pipeline结构体
class Pipeline(Structure):
    _fields_ = [
        ("MaximumInternalProcessingRate", c_int),
        ("MultiChannelRender", c_bool),
        ("MultiChannelCapture", c_bool),
        ("CaptureDownmixMethod", c_int),
    ]


# 定义PreAmplifier结构体
class PreAmplifier(Structure):
    _fields_ = [("Enabled", c_bool), ("FixedGainFactor", c_float)]


# 定义AnalogMicGainEmulation结构体
class AnalogMicGainEmulation(Structure):
    _fields_ = [("Enabled", c_bool), ("InitialLevel", c_int)]


# 定义CaptureLevelAdjustment结构体
class CaptureLevelAdjustment(Structure):
    _fields_ = [
        ("Enabled", c_bool),
        ("PreGainFactor", c_float),
        ("PostGainFactor", c_float),
        ("MicGainEmulation", AnalogMicGainEmulation),
    ]


# 定义HighPassFilter结构体
class HighPassFilter(Structure):
    _fields_ = [("Enabled", c_bool), ("ApplyInFullBand", c_bool)]


# 定义EchoCanceller结构体
class EchoCanceller(Structure):
    _fields_ = [
        ("Enabled", c_bool),
        ("MobileMode", c_bool),
        ("ExportLinearAecOutput", c_bool),
        ("EnforceHighPassFiltering", c_bool),
    ]


# 定义NoiseSuppression结构体
class NoiseSuppression(Structure):
    _fields_ = [
        ("Enabled", c_bool),
        ("NoiseLevel", c_int),
        ("AnalyzeLinearAecOutputWhenAvailable", c_bool),
    ]


# 定义TransientSuppression结构体
class TransientSuppression(Structure):
    _fields_ = [("Enabled", c_bool)]


# 定义ClippingPredictor结构体
class ClippingPredictor(Structure):
    _fields_ = [
        ("Enabled", c_bool),
        ("PredictorMode", c_int),
        ("WindowLength", c_int),
        ("ReferenceWindowLength", c_int),
        ("ReferenceWindowDelay", c_int),
        ("ClippingThreshold", c_float),
        ("CrestFactorMargin", c_float),
        ("UsePredictedStep", c_bool),
    ]


# 定义AnalogGainController结构体
class AnalogGainController(Structure):
    _fields_ = [
        ("Enabled", c_bool),
        ("StartupMinVolume", c_int),
        ("ClippedLevelMin", c_int),
        ("EnableDigitalAdaptive", c_bool),
        ("ClippedLevelStep", c_int),
        ("ClippedRatioThreshold", c_float),
        ("ClippedWaitFrames", c_int),
        ("Predictor", ClippingPredictor),
    ]


# 定义GainController1结构体
class GainController1(Structure):
    _fields_ = [
        ("Enabled", c_bool),
        ("ControllerMode", c_int),
        ("TargetLevelDbfs", c_int),
        ("CompressionGainDb", c_int),
        ("EnableLimiter", c_bool),
        ("AnalogController", AnalogGainController),
    ]


# 定义InputVolumeController结构体
class InputVolumeController(Structure):
    _fields_ = [("Enabled", c_bool)]


# 定义AdaptiveDigital结构体
class AdaptiveDigital(Structure):
    _fields_ = [
        ("Enabled", c_bool),
        ("HeadroomDb", c_float),
        ("MaxGainDb", c_float),
        ("InitialGainDb", c_float),
        ("MaxGainChangeDbPerSecond", c_float),
        ("MaxOutputNoiseLevelDbfs", c_float),
    ]


# 定义FixedDigital结构体
class FixedDigital(Structure):
    _fields_ = [("GainDb", c_float)]


# 定义GainController2结构体
class GainController2(Structure):
    _fields_ = [
        ("Enabled", c_bool),
        ("VolumeController", InputVolumeController),
        ("AdaptiveController", AdaptiveDigital),
        ("FixedController", FixedDigital),
    ]


# 定义完整的Config结构体
class Config(Structure):
    _fields_ = [
        ("PipelineConfig", Pipeline),
        ("PreAmp", PreAmplifier),
        ("LevelAdjustment", CaptureLevelAdjustment),
        ("HighPass", HighPassFilter),
        ("Echo", EchoCanceller),
        ("NoiseSuppress", NoiseSuppression),
        ("TransientSuppress", TransientSuppression),
        ("GainControl1", GainController1),
        ("GainControl2", GainController2),
    ]


# 定义DLL函数原型
apm_lib.WebRTC_APM_Create.restype = c_void_p
apm_lib.WebRTC_APM_Create.argtypes = []

apm_lib.WebRTC_APM_Destroy.restype = None
apm_lib.WebRTC_APM_Destroy.argtypes = [c_void_p]

apm_lib.WebRTC_APM_CreateStreamConfig.restype = c_void_p
apm_lib.WebRTC_APM_CreateStreamConfig.argtypes = [c_int, c_int]

apm_lib.WebRTC_APM_DestroyStreamConfig.restype = None
apm_lib.WebRTC_APM_DestroyStreamConfig.argtypes = [c_void_p]

apm_lib.WebRTC_APM_ApplyConfig.restype = c_int
apm_lib.WebRTC_APM_ApplyConfig.argtypes = [c_void_p, POINTER(Config)]

apm_lib.WebRTC_APM_ProcessReverseStream.restype = c_int
apm_lib.WebRTC_APM_ProcessReverseStream.argtypes = [
    c_void_p,
    POINTER(c_short),
    c_void_p,
    c_void_p,
    POINTER(c_short),
]

apm_lib.WebRTC_APM_ProcessStream.restype = c_int
apm_lib.WebRTC_APM_ProcessStream.argtypes = [
    c_void_p,
    POINTER(c_short),
    c_void_p,
    c_void_p,
    POINTER(c_short),
]

apm_lib.WebRTC_APM_SetStreamDelayMs.restype = None
apm_lib.WebRTC_APM_SetStreamDelayMs.argtypes = [c_void_p, c_int]


def create_apm_config():
    """创建WebRTC APM配置 - 优化为保留自然语音，减少错误码-11问题"""
    config = Config()

    # 设置Pipeline配置 - 使用标准采样率避免重采样问题
    config.PipelineConfig.MaximumInternalProcessingRate = 16000  # WebRTC优化频率
    config.PipelineConfig.MultiChannelRender = False
    config.PipelineConfig.MultiChannelCapture = False
    config.PipelineConfig.CaptureDownmixMethod = DownmixMethod.AverageChannels

    # 设置PreAmplifier配置 - 减少预放大干扰
    config.PreAmp.Enabled = False  # 关闭预放大，避免失真
    config.PreAmp.FixedGainFactor = 1.0  # 不增益

    # 设置LevelAdjustment配置 - 简化电平调整
    config.LevelAdjustment.Enabled = False  # 禁用电平调整以减少处理冲突
    config.LevelAdjustment.PreGainFactor = 1.0
    config.LevelAdjustment.PostGainFactor = 1.0
    config.LevelAdjustment.MicGainEmulation.Enabled = False
    config.LevelAdjustment.MicGainEmulation.InitialLevel = 100  # 降低初始电平避免过饱和

    # 设置HighPassFilter配置 - 使用标准高通滤波
    config.HighPass.Enabled = True  # 启用高通滤波器移除低频噪声
    config.HighPass.ApplyInFullBand = True  # 在全频段应用，更好的兼容性

    # 设置EchoCanceller配置 - 优化回声消除
    config.Echo.Enabled = True  # 启用回声消除
    config.Echo.MobileMode = False  # 使用标准模式而非移动模式以获取更好效果
    config.Echo.ExportLinearAecOutput = False
    config.Echo.EnforceHighPassFiltering = True  # 启用强制高通滤波，帮助消除低频回声

    # 设置NoiseSuppression配置 - 中等强度噪声抑制
    config.NoiseSuppress.Enabled = True
    config.NoiseSuppress.NoiseLevel = NoiseSuppressionLevel.Moderate  # 中等级别抑制
    config.NoiseSuppress.AnalyzeLinearAecOutputWhenAvailable = True

    # 设置TransientSuppression配置
    config.TransientSuppress.Enabled = False  # 关闭瞬态抑制，避免切割语音

    # 设置GainController1配置 - 轻度增益控制
    config.GainControl1.Enabled = True  # 启用增益控制
    config.GainControl1.ControllerMode = GainControllerMode.AdaptiveDigital
    config.GainControl1.TargetLevelDbfs = 3  # 降低目标电平(更积极的控制)
    config.GainControl1.CompressionGainDb = 9  # 适中的压缩增益
    config.GainControl1.EnableLimiter = True  # 启用限制器

    # AnalogGainController
    config.GainControl1.AnalogController.Enabled = False  # 关闭模拟增益控制
    config.GainControl1.AnalogController.StartupMinVolume = 0
    config.GainControl1.AnalogController.ClippedLevelMin = 70
    config.GainControl1.AnalogController.EnableDigitalAdaptive = False
    config.GainControl1.AnalogController.ClippedLevelStep = 15
    config.GainControl1.AnalogController.ClippedRatioThreshold = 0.1
    config.GainControl1.AnalogController.ClippedWaitFrames = 300

    # ClippingPredictor
    predictor = config.GainControl1.AnalogController.Predictor
    predictor.Enabled = False
    predictor.PredictorMode = ClippingPredictorMode.ClippingEventPrediction
    predictor.WindowLength = 5
    predictor.ReferenceWindowLength = 5
    predictor.ReferenceWindowDelay = 5
    predictor.ClippingThreshold = -1.0
    predictor.CrestFactorMargin = 3.0
    predictor.UsePredictedStep = True

    # 设置GainController2配置 - 禁用以避免冲突
    config.GainControl2.Enabled = False
    config.GainControl2.VolumeController.Enabled = False
    config.GainControl2.AdaptiveController.Enabled = False
    config.GainControl2.AdaptiveController.HeadroomDb = 5.0
    config.GainControl2.AdaptiveController.MaxGainDb = 30.0
    config.GainControl2.AdaptiveController.InitialGainDb = 15.0
    config.GainControl2.AdaptiveController.MaxGainChangeDbPerSecond = 6.0
    config.GainControl2.AdaptiveController.MaxOutputNoiseLevelDbfs = -50.0
    config.GainControl2.FixedController.GainDb = 0.0

    return config


# 参考音频缓冲区（用于存储扬声器输出）
reference_buffer = []
reference_lock = threading.Lock()


def record_playback_audio(chunk_size, sample_rate, channels):
    """
    录制扬声器输出的音频（更准确的参考信号）
    """
    global reference_buffer

    # 注：这是理想情况下的实现，但Windows下PyAudio通常无法直接录制扬声器输出
    # 实际应用中，需要使用其他方法捕获系统音频输出
    try:
        p = pyaudio.PyAudio()

        # 尝试创建一个从默认输出设备录制的流（部分系统支持）
        # 注意：这在大多数系统上不起作用，这里只是作为示例
        loopback_stream = p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=sample_rate,
            input=True,
            frames_per_buffer=chunk_size,
            input_device_index=None,  # 尝试使用默认输出设备作为输入源
        )

        # 开始录制
        while True:
            try:
                data = loopback_stream.read(chunk_size, exception_on_overflow=False)
                with reference_lock:
                    reference_buffer.append(data)
            except OSError:
                break

            # 保持缓冲区大小合理
            with reference_lock:
                if len(reference_buffer) > 100:  # 保持约2秒的缓冲
                    reference_buffer = reference_buffer[-100:]
    except Exception as e:
        print(f"无法录制系统音频: {e}")
    finally:
        try:
            if "loopback_stream" in locals() and loopback_stream:
                loopback_stream.stop_stream()
                loopback_stream.close()
            if "p" in locals() and p:
                p.terminate()
        except Exception:
            pass


def aec_demo(audio_file):
    """
    WebRTC回声消除演示主函数.
    """
    # 检查音频文件是否存在
    if not os.path.exists(audio_file):
        print(f"错误: 找不到音频文件 {audio_file}")
        return

    # 音频参数设置 - 使用WebRTC优化的音频参数
    SAMPLE_RATE = 16000  # 采样率16kHz (WebRTC AEC优化采样率)
    CHANNELS = 1  # 单声道
    CHUNK = 160  # 每帧样本数(10ms @ 16kHz，WebRTC的标准帧大小)
    FORMAT = pyaudio.paInt16  # 16位PCM格式

    # 初始化PyAudio
    p = pyaudio.PyAudio()

    # 列出所有可用的音频设备信息供参考
    print("\n可用音频设备:")
    for i in range(p.get_device_count()):
        dev_info = p.get_device_info_by_index(i)
        print(f"设备 {i}: {dev_info['name']}")
        print(f"  - 输入通道: {dev_info['maxInputChannels']}")
        print(f"  - 输出通道: {dev_info['maxOutputChannels']}")
        print(f"  - 默认采样率: {dev_info['defaultSampleRate']}")
    print("")

    # 打开麦克风输入流
    input_stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )

    # 初始化pygame用于播放音频
    pygame.init()
    mixer.init(frequency=SAMPLE_RATE, size=-16, channels=CHANNELS, buffer=CHUNK * 4)

    # 加载参考音频文件
    print(f"加载音频文件: {audio_file}")

    # 读取参考音频文件并转换采样率/通道数
    # 注意：这里使用soundfile库加载音频文件以支持多种格式并进行重采样
    try:
        print("加载参考音频...")
        # 使用soundfile库读取原始音频
        ref_audio_data, orig_sr = sf.read(audio_file, dtype="int16")
        print(
            f"原始音频: 采样率={orig_sr}, 通道数="
            f"{ref_audio_data.shape[1] if len(ref_audio_data.shape) > 1 else 1}"
        )

        # 转换为单声道(如果是立体声)
        if len(ref_audio_data.shape) > 1 and ref_audio_data.shape[1] > 1:
            ref_audio_data = ref_audio_data.mean(axis=1).astype(np.int16)

        # 转换采样率(如果需要)
        if orig_sr != SAMPLE_RATE:
            print(f"重采样参考音频从{orig_sr}Hz到{SAMPLE_RATE}Hz...")
            # 使用librosa或scipy进行重采样
            from scipy import signal

            ref_audio_data = signal.resample(
                ref_audio_data, int(len(ref_audio_data) * SAMPLE_RATE / orig_sr)
            ).astype(np.int16)

        # 保存为临时wav文件供pygame播放
        temp_wav_path = os.path.join(current_dir, "temp_reference.wav")
        with wave.open(temp_wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 2字节(16位)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(ref_audio_data.tobytes())

        # 将参考音频分成CHUNK大小的帧
        ref_audio_frames = []
        for i in range(0, len(ref_audio_data), CHUNK):
            if i + CHUNK <= len(ref_audio_data):
                ref_audio_frames.append(ref_audio_data[i : i + CHUNK])
            else:
                # 最后一帧不足CHUNK大小，补零
                last_frame = np.zeros(CHUNK, dtype=np.int16)
                last_frame[: len(ref_audio_data) - i] = ref_audio_data[i:]
                ref_audio_frames.append(last_frame)

        print(f"参考音频准备完成，共{len(ref_audio_frames)}帧")

        # 加载处理后的临时WAV文件
        mixer.music.load(temp_wav_path)
    except Exception as e:
        print(f"加载参考音频时出错: {e}")
        sys.exit(1)

    # 创建WebRTC APM实例
    apm = apm_lib.WebRTC_APM_Create()

    # 应用APM配置
    config = create_apm_config()
    result = apm_lib.WebRTC_APM_ApplyConfig(apm, byref(config))
    if result != 0:
        print(f"警告: APM配置应用失败，错误码: {result}")

    # 创建流配置
    stream_config = apm_lib.WebRTC_APM_CreateStreamConfig(SAMPLE_RATE, CHANNELS)

    # 设置较小的延迟时间以更准确匹配参考信号和麦克风信号
    apm_lib.WebRTC_APM_SetStreamDelayMs(apm, 50)

    # 创建录音缓冲区
    original_frames = []
    processed_frames = []
    reference_frames = []

    # 等待一会让音频系统准备好
    time.sleep(0.5)

    print("开始录制和处理...")
    print("播放参考音频...")

    mixer.music.play()

    # 录制持续时间(根据音频文件长度)
    try:
        sound_length = mixer.Sound(temp_wav_path).get_length()
        recording_time = sound_length if sound_length > 0 else 10
    except Exception:
        recording_time = 10  # 如果无法获取长度，默认10秒

    recording_time += 1  # 额外1秒确保捕获所有音频

    start_time = time.time()
    current_ref_frame_index = 0
    try:
        while time.time() - start_time < recording_time:
            # 从麦克风读取一帧数据
            input_data = input_stream.read(CHUNK, exception_on_overflow=False)

            # 保存原始录音
            original_frames.append(input_data)

            # 将输入数据转换为short数组
            input_array = np.frombuffer(input_data, dtype=np.int16)
            input_ptr = input_array.ctypes.data_as(POINTER(c_short))

            # 获取当前参考音频帧
            if current_ref_frame_index < len(ref_audio_frames):
                ref_array = ref_audio_frames[current_ref_frame_index]
                reference_frames.append(ref_array.tobytes())
                current_ref_frame_index += 1
            else:
                # 如果参考音频播放完毕，使用静音帧
                ref_array = np.zeros(CHUNK, dtype=np.int16)
                reference_frames.append(ref_array.tobytes())

            ref_ptr = ref_array.ctypes.data_as(POINTER(c_short))

            # 创建输出缓冲区
            output_array = np.zeros(CHUNK, dtype=np.int16)
            output_ptr = output_array.ctypes.data_as(POINTER(c_short))

            # 重要：先处理参考信号（扬声器输出）
            # 创建参考信号的输出缓冲区（虽然不使用但必须提供）
            ref_output_array = np.zeros(CHUNK, dtype=np.int16)
            ref_output_ptr = ref_output_array.ctypes.data_as(POINTER(c_short))

            result_reverse = apm_lib.WebRTC_APM_ProcessReverseStream(
                apm, ref_ptr, stream_config, stream_config, ref_output_ptr
            )

            if result_reverse != 0:
                print(f"\r警告: 参考信号处理失败，错误码: {result_reverse}")

            # 然后处理麦克风信号，应用回声消除
            result = apm_lib.WebRTC_APM_ProcessStream(
                apm, input_ptr, stream_config, stream_config, output_ptr
            )

            if result != 0:
                print(f"\r警告: 处理失败，错误码: {result}")

            # 保存处理后的音频帧
            processed_frames.append(output_array.tobytes())

            # 计算并显示进度
            progress = (time.time() - start_time) / recording_time * 100
            sys.stdout.write(f"\r处理进度: {progress:.1f}%")
            sys.stdout.flush()

    except KeyboardInterrupt:
        print("\n录制被用户中断")
    finally:
        print("\n录制和处理完成")

        # 停止播放
        mixer.music.stop()

        # 关闭音频流
        input_stream.stop_stream()
        input_stream.close()

        # 释放APM资源
        apm_lib.WebRTC_APM_DestroyStreamConfig(stream_config)
        apm_lib.WebRTC_APM_Destroy(apm)

        # 关闭PyAudio
        p.terminate()

        # 保存原始录音
        original_output_path = os.path.join(current_dir, "original_recording.wav")
        save_wav(original_output_path, original_frames, SAMPLE_RATE, CHANNELS)

        # 保存处理后的录音
        processed_output_path = os.path.join(current_dir, "processed_recording.wav")
        save_wav(processed_output_path, processed_frames, SAMPLE_RATE, CHANNELS)

        # 保存参考音频（播放的音频）
        reference_output_path = os.path.join(current_dir, "reference_playback.wav")
        save_wav(reference_output_path, reference_frames, SAMPLE_RATE, CHANNELS)

        # 删除临时文件
        if os.path.exists(temp_wav_path):
            try:
                os.remove(temp_wav_path)
            except Exception:
                pass

        print(f"原始录音已保存至: {original_output_path}")
        print(f"处理后的录音已保存至: {processed_output_path}")
        print(f"参考音频已保存至: {reference_output_path}")

        # 退出pygame
        pygame.quit()


def save_wav(file_path, frames, sample_rate, channels):
    """
    将音频帧保存为WAV文件.
    """
    with wave.open(file_path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 2字节(16位)
        wf.setframerate(sample_rate)
        if isinstance(frames[0], bytes):
            wf.writeframes(b"".join(frames))
        else:
            wf.writeframes(b"".join([f for f in frames if isinstance(f, bytes)]))


if __name__ == "__main__":
    # 获取命令行参数
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
    else:
        # 默认使用scripts目录下的鞠婧祎.wav
        audio_file = os.path.join(current_dir, "鞠婧祎.wav")

        # 如果默认文件不存在，尝试MP3版本
        if not os.path.exists(audio_file):
            audio_file = os.path.join(current_dir, "鞠婧祎.mp3")
            if not os.path.exists(audio_file):
                print("错误: 找不到默认音频文件，请指定要播放的音频文件路径")
                print("用法: python webrtc_aec_demo.py [音频文件路径]")
                sys.exit(1)

    # 运行演示
    aec_demo(audio_file)
