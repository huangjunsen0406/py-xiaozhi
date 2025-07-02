"""WebRTC音频处理模块.

该模块提供WebRTC APM库的回声消除(AEC)、噪声抑制(NS)等音频处理功能。
从webrtc_aec_demo.py提取并优化为实时处理模块。

主要功能:
1. 回声消除(AEC) - 消除扬声器输出对麦克风输入的干扰
2. 噪声抑制(NS) - 减少环境噪声
3. 增益控制(AGC) - 自动调整音频增益
4. 高通滤波 - 移除低频噪声

用法:
    processor = WebRTCProcessor()
    processed_audio = processor.process_capture_stream(input_audio, reference_audio)
"""

import ctypes
import os
import threading
from ctypes import POINTER, Structure, byref, c_bool, c_float, c_int, c_short, c_void_p

import numpy as np

from src.utils.logging_config import get_logger
from src.utils.path_resolver import find_resource

logger = get_logger(__name__)


# 获取DLL文件的绝对路径
def get_webrtc_dll_path():
    """
    获取WebRTC APM库的路径.
    """
    dll_path = find_resource("libs/webrtc_apm/win/x86_64/libwebrtc_apm.dll")
    if dll_path:
        return str(dll_path)

    # 备用方案：使用原有逻辑
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    fallback_path = os.path.join(
        project_root, "libs", "webrtc_apm", "win", "x86_64", "libwebrtc_apm.dll"
    )
    logger.warning(f"未找到WebRTC库，使用备用路径: {fallback_path}")
    return fallback_path


# 加载WebRTC APM库
try:
    dll_path = get_webrtc_dll_path()
    apm_lib = ctypes.CDLL(dll_path)
    logger.info(f"成功加载WebRTC APM库: {dll_path}")
except Exception as e:
    logger.error(f"加载WebRTC APM库失败: {e}")
    apm_lib = None


# 定义枚举类型
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


# 定义结构体
class Pipeline(Structure):
    _fields_ = [
        ("MaximumInternalProcessingRate", c_int),
        ("MultiChannelRender", c_bool),
        ("MultiChannelCapture", c_bool),
        ("CaptureDownmixMethod", c_int),
    ]


class PreAmplifier(Structure):
    _fields_ = [("Enabled", c_bool), ("FixedGainFactor", c_float)]


class AnalogMicGainEmulation(Structure):
    _fields_ = [("Enabled", c_bool), ("InitialLevel", c_int)]


class CaptureLevelAdjustment(Structure):
    _fields_ = [
        ("Enabled", c_bool),
        ("PreGainFactor", c_float),
        ("PostGainFactor", c_float),
        ("MicGainEmulation", AnalogMicGainEmulation),
    ]


class HighPassFilter(Structure):
    _fields_ = [("Enabled", c_bool), ("ApplyInFullBand", c_bool)]


class EchoCanceller(Structure):
    _fields_ = [
        ("Enabled", c_bool),
        ("MobileMode", c_bool),
        ("ExportLinearAecOutput", c_bool),
        ("EnforceHighPassFiltering", c_bool),
    ]


class NoiseSuppression(Structure):
    _fields_ = [
        ("Enabled", c_bool),
        ("NoiseLevel", c_int),
        ("AnalyzeLinearAecOutputWhenAvailable", c_bool),
    ]


class TransientSuppression(Structure):
    _fields_ = [("Enabled", c_bool)]


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


class GainController1(Structure):
    _fields_ = [
        ("Enabled", c_bool),
        ("ControllerMode", c_int),
        ("TargetLevelDbfs", c_int),
        ("CompressionGainDb", c_int),
        ("EnableLimiter", c_bool),
        ("AnalogController", AnalogGainController),
    ]


class InputVolumeController(Structure):
    _fields_ = [("Enabled", c_bool)]


class AdaptiveDigital(Structure):
    _fields_ = [
        ("Enabled", c_bool),
        ("HeadroomDb", c_float),
        ("MaxGainDb", c_float),
        ("InitialGainDb", c_float),
        ("MaxGainChangeDbPerSecond", c_float),
        ("MaxOutputNoiseLevelDbfs", c_float),
    ]


class FixedDigital(Structure):
    _fields_ = [("GainDb", c_float)]


class GainController2(Structure):
    _fields_ = [
        ("Enabled", c_bool),
        ("VolumeController", InputVolumeController),
        ("AdaptiveController", AdaptiveDigital),
        ("FixedController", FixedDigital),
    ]


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
if apm_lib:
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


def create_optimized_apm_config():
    """
    创建优化的WebRTC APM配置，专为实时音频处理优化.
    """
    config = Config()

    # Pipeline配置 - 使用16kHz优化
    config.PipelineConfig.MaximumInternalProcessingRate = 16000
    config.PipelineConfig.MultiChannelRender = False
    config.PipelineConfig.MultiChannelCapture = False
    config.PipelineConfig.CaptureDownmixMethod = DownmixMethod.AverageChannels

    # 预放大器 - 关闭以减少失真
    config.PreAmp.Enabled = False
    config.PreAmp.FixedGainFactor = 1.0

    # 电平调整 - 简化配置
    config.LevelAdjustment.Enabled = False
    config.LevelAdjustment.PreGainFactor = 1.0
    config.LevelAdjustment.PostGainFactor = 1.0
    config.LevelAdjustment.MicGainEmulation.Enabled = False
    config.LevelAdjustment.MicGainEmulation.InitialLevel = 100

    # 高通滤波器 - 启用以移除低频噪声
    config.HighPass.Enabled = True
    config.HighPass.ApplyInFullBand = True

    # 回声消除 - 核心功能
    config.Echo.Enabled = True
    config.Echo.MobileMode = False
    config.Echo.ExportLinearAecOutput = False
    config.Echo.EnforceHighPassFiltering = True

    # 噪声抑制 - 中等强度
    config.NoiseSuppress.Enabled = True
    config.NoiseSuppress.NoiseLevel = NoiseSuppressionLevel.Moderate
    config.NoiseSuppress.AnalyzeLinearAecOutputWhenAvailable = True

    # 瞬态抑制 - 关闭以保护语音
    config.TransientSuppress.Enabled = False

    # 增益控制1 - 启用自适应数字增益
    config.GainControl1.Enabled = True
    config.GainControl1.ControllerMode = GainControllerMode.AdaptiveDigital
    config.GainControl1.TargetLevelDbfs = 3
    config.GainControl1.CompressionGainDb = 9
    config.GainControl1.EnableLimiter = True

    # 模拟增益控制器 - 关闭
    config.GainControl1.AnalogController.Enabled = False
    config.GainControl1.AnalogController.StartupMinVolume = 0
    config.GainControl1.AnalogController.ClippedLevelMin = 70
    config.GainControl1.AnalogController.EnableDigitalAdaptive = False
    config.GainControl1.AnalogController.ClippedLevelStep = 15
    config.GainControl1.AnalogController.ClippedRatioThreshold = 0.1
    config.GainControl1.AnalogController.ClippedWaitFrames = 300

    # 削波预测器 - 关闭
    predictor = config.GainControl1.AnalogController.Predictor
    predictor.Enabled = False
    predictor.PredictorMode = ClippingPredictorMode.ClippingEventPrediction
    predictor.WindowLength = 5
    predictor.ReferenceWindowLength = 5
    predictor.ReferenceWindowDelay = 5
    predictor.ClippingThreshold = -1.0
    predictor.CrestFactorMargin = 3.0
    predictor.UsePredictedStep = True

    # 增益控制2 - 关闭以避免冲突
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


class WebRTCProcessor:
    """
    WebRTC音频处理器，提供实时回声消除和音频增强功能.
    """

    def __init__(self, sample_rate=16000, channels=1, frame_size=160):
        """初始化WebRTC处理器.

        Args:
            sample_rate: 采样率，默认16000Hz
            channels: 声道数，默认1（单声道）
            frame_size: 帧大小，默认160样本（10ms @ 16kHz）
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.frame_size = frame_size

        # WebRTC APM实例
        self.apm = None
        self.stream_config = None
        self.config = None

        # 线程安全锁
        self._lock = threading.Lock()

        # 初始化状态
        self._initialized = False

        # 参考信号缓冲区（用于回声消除）
        self._reference_buffer = []
        self._reference_lock = threading.Lock()

        # 初始化WebRTC APM
        self._initialize()

    def _initialize(self):
        """
        初始化WebRTC APM.
        """
        if not apm_lib:
            logger.error("WebRTC APM库未加载，无法初始化处理器")
            return False

        try:
            with self._lock:
                # 创建APM实例
                self.apm = apm_lib.WebRTC_APM_Create()
                if not self.apm:
                    logger.error("创建WebRTC APM实例失败")
                    return False

                # 创建流配置
                self.stream_config = apm_lib.WebRTC_APM_CreateStreamConfig(
                    self.sample_rate, self.channels
                )
                if not self.stream_config:
                    logger.error("创建WebRTC流配置失败")
                    return False

                # 应用配置
                self.config = create_optimized_apm_config()
                result = apm_lib.WebRTC_APM_ApplyConfig(self.apm, byref(self.config))
                if result != 0:
                    logger.warning(f"应用WebRTC配置失败，错误码: {result}")

                # 设置延迟
                apm_lib.WebRTC_APM_SetStreamDelayMs(self.apm, 50)

                self._initialized = True
                logger.info("WebRTC处理器初始化成功")
                return True

        except Exception as e:
            logger.error(f"初始化WebRTC处理器失败: {e}")
            return False

    def process_capture_stream(self, input_data, reference_data=None):
        """处理捕获流（麦克风输入）

        Args:
            input_data: 输入音频数据（bytes）
            reference_data: 参考音频数据（bytes，可选）

        Returns:
            处理后的音频数据（bytes），失败返回原始数据
        """
        if not self._initialized or not self.apm:
            logger.warning("WebRTC处理器未初始化，返回原始数据")
            return input_data

        try:
            with self._lock:
                # 转换输入数据为numpy数组
                input_array = np.frombuffer(input_data, dtype=np.int16)

                # 检查数据长度
                if len(input_array) != self.frame_size:
                    logger.warning(
                        f"输入数据长度不匹配，期望{self.frame_size}，实际{len(input_array)}"
                    )
                    return input_data

                # 创建输入指针
                input_ptr = input_array.ctypes.data_as(POINTER(c_short))

                # 创建输出缓冲区
                output_array = np.zeros(self.frame_size, dtype=np.int16)
                output_ptr = output_array.ctypes.data_as(POINTER(c_short))

                # 处理参考信号（如果提供）
                if reference_data:
                    self._process_reference_stream(reference_data)

                # 处理捕获流
                result = apm_lib.WebRTC_APM_ProcessStream(
                    self.apm,
                    input_ptr,
                    self.stream_config,
                    self.stream_config,
                    output_ptr,
                )

                if result != 0:
                    logger.debug(f"WebRTC处理警告，错误码: {result}")
                    # 即使有警告，也返回处理后的数据

                return output_array.tobytes()

        except Exception as e:
            logger.error(f"处理捕获流失败: {e}")
            return input_data

    def _process_reference_stream(self, reference_data):
        """处理参考流（扬声器输出）

        Args:
            reference_data: 参考音频数据（bytes）
        """
        try:
            # 转换参考数据为numpy数组
            ref_array = np.frombuffer(reference_data, dtype=np.int16)

            # 检查数据长度
            if len(ref_array) != self.frame_size:
                # 如果长度不匹配，调整到正确长度
                if len(ref_array) > self.frame_size:
                    ref_array = ref_array[: self.frame_size]
                else:
                    # 补零
                    padded = np.zeros(self.frame_size, dtype=np.int16)
                    padded[: len(ref_array)] = ref_array
                    ref_array = padded

            # 创建参考信号指针
            ref_ptr = ref_array.ctypes.data_as(POINTER(c_short))

            # 创建参考输出缓冲区（虽然不使用但必须提供）
            ref_output_array = np.zeros(self.frame_size, dtype=np.int16)
            ref_output_ptr = ref_output_array.ctypes.data_as(POINTER(c_short))

            # 处理参考流
            result = apm_lib.WebRTC_APM_ProcessReverseStream(
                self.apm,
                ref_ptr,
                self.stream_config,
                self.stream_config,
                ref_output_ptr,
            )

            if result != 0:
                logger.debug(f"处理参考流警告，错误码: {result}")

        except Exception as e:
            logger.error(f"处理参考流失败: {e}")

    def add_reference_data(self, reference_data):
        """添加参考数据到缓冲区.

        Args:
            reference_data: 参考音频数据（bytes）
        """
        with self._reference_lock:
            self._reference_buffer.append(reference_data)
            # 保持缓冲区大小合理（约1秒的数据）
            max_buffer_size = self.sample_rate // self.frame_size
            if len(self._reference_buffer) > max_buffer_size:
                self._reference_buffer = self._reference_buffer[-max_buffer_size:]

    def get_reference_data(self):
        """获取并移除最旧的参考数据.

        Returns:
            参考音频数据（bytes），如果缓冲区为空返回None
        """
        with self._reference_lock:
            if self._reference_buffer:
                return self._reference_buffer.pop(0)
            return None

    def close(self):
        """
        关闭WebRTC处理器，释放资源.
        """
        if not self._initialized:
            return

        try:
            with self._lock:
                # 清理参考缓冲区
                with self._reference_lock:
                    self._reference_buffer.clear()

                # 销毁流配置
                if self.stream_config:
                    apm_lib.WebRTC_APM_DestroyStreamConfig(self.stream_config)
                    self.stream_config = None

                # 销毁APM实例
                if self.apm:
                    apm_lib.WebRTC_APM_Destroy(self.apm)
                    self.apm = None

                self._initialized = False
                logger.info("WebRTC处理器已关闭")

        except Exception as e:
            logger.error(f"关闭WebRTC处理器失败: {e}")

    def __del__(self):
        """
        析构函数，确保资源被释放.
        """
        self.close()
