"""设置窗口 ViewModel.

完整支持所有配置项，参照旧 PyQt5 实现。
"""

import json
import threading
import time
from typing import Any

import numpy as np
import sounddevice as sd
from PySide6.QtCore import Property, Signal, Slot

from src.audio_processing.keyword_converters import convert_wake_word
from src.logging import get_logger
from src.utils.config_manager import ConfigManager
from src.utils.resource_finder import get_user_data_dir

from .base_model import BaseModel

logger = get_logger()


class SettingsModel(BaseModel):
    """设置窗口数据模型."""

    # 信号
    settingsChanged = Signal()
    devicesChanged = Signal()
    statusMessage = Signal(str)  # 状态消息
    testComplete = Signal(str, bool)  # 测试完成(类型, 成功)
    wakeWordChanged = Signal()  # 唤醒词变更
    configSaved = Signal()  # 配置已保存（用于触发热重载）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config_manager = ConfigManager.get_instance()
        self._config_path = get_user_data_dir() / "config" / "config.json"
        self._config: dict = {}

        # 音频设备
        self._input_devices: list[dict] = []
        self._output_devices: list[dict] = []

        # 摄像头设备
        self._cameras: list[dict] = []

        # 测试状态
        self._testing_input = False
        self._testing_output = False

        # 唤醒词
        self._wake_word: str = ""
        self._wake_word_lang: str = "zh"
        self._wake_word_preview: str = ""

        # 加载数据
        self._load_config()
        self._load_audio_devices()
        self._load_cameras()
        self._load_wake_word()

    # ========== 配置读写 ==========

    def _load_config(self):
        """从文件加载配置."""
        try:
            if self._config_path.exists():
                with open(self._config_path, encoding="utf-8") as f:
                    self._config = json.load(f)
                logger.debug("设置配置已加载")
            else:
                logger.warning(f"配置文件不存在: {self._config_path}")
                self._config = {}
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            self._config = {}

    def _get_value(self, path: str, default: Any = None) -> Any:
        """获取配置值，支持点号分隔的路径."""
        keys = path.split(".")
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def _set_value(self, path: str, value: Any):
        """设置配置值，支持点号分隔的路径."""
        keys = path.split(".")
        config = self._config
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        config[keys[-1]] = value
        self.settingsChanged.emit()

    @Slot()
    def save(self):
        """保存配置到文件."""
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            logger.info("设置已保存")
            self.statusMessage.emit("配置已保存")
            # 发送配置保存信号，触发热重载
            self.configSaved.emit()
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            self.set_error(f"保存配置失败: {e}")

    @Slot()
    def reload(self):
        """重新加载配置."""
        self._load_config()
        self._load_audio_devices()
        self._load_cameras()
        self.settingsChanged.emit()
        logger.info("设置已重新加载")

    # ========== 系统选项 ==========

    # CLIENT_ID
    def _get_clientId(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.CLIENT_ID", "")

    def _set_clientId(self, value: str):
        self._set_value("SYSTEM_OPTIONS.CLIENT_ID", value)

    clientId = Property(str, _get_clientId, _set_clientId, notify=settingsChanged)

    # DEVICE_ID
    def _get_deviceId(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.DEVICE_ID", "")

    def _set_deviceId(self, value: str):
        self._set_value("SYSTEM_OPTIONS.DEVICE_ID", value)

    deviceId = Property(str, _get_deviceId, _set_deviceId, notify=settingsChanged)

    # OTA_VERSION_URL
    def _get_otaUrl(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL", "")

    def _set_otaUrl(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL", value)

    otaUrl = Property(str, _get_otaUrl, _set_otaUrl, notify=settingsChanged)

    # WEBSOCKET_URL
    def _get_websocketUrl(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL", "")

    def _set_websocketUrl(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL", value)

    websocketUrl = Property(
        str, _get_websocketUrl, _set_websocketUrl, notify=settingsChanged
    )

    # WEBSOCKET_ACCESS_TOKEN
    def _get_websocketToken(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN", "")

    def _set_websocketToken(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN", value)

    websocketToken = Property(
        str, _get_websocketToken, _set_websocketToken, notify=settingsChanged
    )

    # AUTHORIZATION_URL
    def _get_authorizationUrl(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL", "")

    def _set_authorizationUrl(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL", value)

    authorizationUrl = Property(
        str, _get_authorizationUrl, _set_authorizationUrl, notify=settingsChanged
    )

    # ACTIVATION_VERSION
    def _get_activationVersion(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION", "v1")

    def _set_activationVersion(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION", value)

    activationVersion = Property(
        str, _get_activationVersion, _set_activationVersion, notify=settingsChanged
    )

    # WINDOW_SIZE_MODE
    def _get_windowSizeMode(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.WINDOW_SIZE_MODE", "default")

    def _set_windowSizeMode(self, value: str):
        self._set_value("SYSTEM_OPTIONS.WINDOW_SIZE_MODE", value)

    windowSizeMode = Property(
        str, _get_windowSizeMode, _set_windowSizeMode, notify=settingsChanged
    )

    # 音乐配置
    def _get_musicSearchUrl(self) -> str:
        return self._get_value("MUSIC.SEARCH_URL", "")

    def _set_musicSearchUrl(self, value: str):
        self._set_value("MUSIC.SEARCH_URL", value)

    musicSearchUrl = Property(
        str, _get_musicSearchUrl, _set_musicSearchUrl, notify=settingsChanged
    )

    def _get_musicUrlApi(self) -> str:
        return self._get_value("MUSIC.URL_API", "")

    def _set_musicUrlApi(self, value: str):
        self._set_value("MUSIC.URL_API", value)

    musicUrlApi = Property(
        str, _get_musicUrlApi, _set_musicUrlApi, notify=settingsChanged
    )

    def _get_musicUrlApiKey(self) -> str:
        return self._get_value("MUSIC.URL_API_KEY", "")

    def _set_musicUrlApiKey(self, value: str):
        self._set_value("MUSIC.URL_API_KEY", value)

    musicUrlApiKey = Property(
        str, _get_musicUrlApiKey, _set_musicUrlApiKey, notify=settingsChanged
    )

    def _get_musicDefaultPlatform(self) -> str:
        return self._get_value("MUSIC.DEFAULT_PLATFORM", "kw")

    def _set_musicDefaultPlatform(self, value: str):
        self._set_value("MUSIC.DEFAULT_PLATFORM", value)

    musicDefaultPlatform = Property(
        str,
        _get_musicDefaultPlatform,
        _set_musicDefaultPlatform,
        notify=settingsChanged,
    )

    def _get_musicDefaultQuality(self) -> str:
        return self._get_value("MUSIC.DEFAULT_QUALITY", "320k")

    def _set_musicDefaultQuality(self, value: str):
        self._set_value("MUSIC.DEFAULT_QUALITY", value)

    musicDefaultQuality = Property(
        str, _get_musicDefaultQuality, _set_musicDefaultQuality, notify=settingsChanged
    )

    # MQTT 配置
    def _get_mqttEndpoint(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.endpoint", "")

    def _set_mqttEndpoint(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.endpoint", value)

    mqttEndpoint = Property(
        str, _get_mqttEndpoint, _set_mqttEndpoint, notify=settingsChanged
    )

    def _get_mqttClientId(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.client_id", "")

    def _set_mqttClientId(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.client_id", value)

    mqttClientId = Property(
        str, _get_mqttClientId, _set_mqttClientId, notify=settingsChanged
    )

    def _get_mqttUsername(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.username", "")

    def _set_mqttUsername(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.username", value)

    mqttUsername = Property(
        str, _get_mqttUsername, _set_mqttUsername, notify=settingsChanged
    )

    def _get_mqttPassword(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.password", "")

    def _set_mqttPassword(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.password", value)

    mqttPassword = Property(
        str, _get_mqttPassword, _set_mqttPassword, notify=settingsChanged
    )

    def _get_mqttPublishTopic(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.publish_topic", "")

    def _set_mqttPublishTopic(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.publish_topic", value)

    mqttPublishTopic = Property(
        str, _get_mqttPublishTopic, _set_mqttPublishTopic, notify=settingsChanged
    )

    def _get_mqttSubscribeTopic(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.subscribe_topic", "")

    def _set_mqttSubscribeTopic(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.subscribe_topic", value)

    mqttSubscribeTopic = Property(
        str, _get_mqttSubscribeTopic, _set_mqttSubscribeTopic, notify=settingsChanged
    )

    # AEC 启用
    def _get_aecEnabled(self) -> bool:
        return self._get_value("AEC_OPTIONS.ENABLED", False)

    def _set_aecEnabled(self, value: bool):
        self._set_value("AEC_OPTIONS.ENABLED", value)

    aecEnabled = Property(
        bool, _get_aecEnabled, _set_aecEnabled, notify=settingsChanged
    )

    # ========== 唤醒词设置 ==========

    def _get_wakeWordEnabled(self) -> bool:
        return self._get_value("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False)

    def _set_wakeWordEnabled(self, value: bool):
        self._set_value("WAKE_WORD_OPTIONS.USE_WAKE_WORD", value)

    wakeWordEnabled = Property(
        bool, _get_wakeWordEnabled, _set_wakeWordEnabled, notify=settingsChanged
    )

    def _get_modelPath(self) -> str:
        return self._get_value("WAKE_WORD_OPTIONS.MODEL_PATH", "models")

    def _set_modelPath(self, value: str):
        self._set_value("WAKE_WORD_OPTIONS.MODEL_PATH", value)

    modelPath = Property(str, _get_modelPath, _set_modelPath, notify=settingsChanged)

    def _get_numThreads(self) -> int:
        return self._get_value("WAKE_WORD_OPTIONS.NUM_THREADS", 4)

    def _set_numThreads(self, value: int):
        self._set_value("WAKE_WORD_OPTIONS.NUM_THREADS", value)

    numThreads = Property(int, _get_numThreads, _set_numThreads, notify=settingsChanged)

    def _get_keywordsScore(self) -> float:
        return self._get_value("WAKE_WORD_OPTIONS.KEYWORDS_SCORE", 1.8)

    def _set_keywordsScore(self, value: float):
        self._set_value("WAKE_WORD_OPTIONS.KEYWORDS_SCORE", value)

    keywordsScore = Property(
        float, _get_keywordsScore, _set_keywordsScore, notify=settingsChanged
    )

    def _get_keywordsThreshold(self) -> float:
        return self._get_value("WAKE_WORD_OPTIONS.KEYWORDS_THRESHOLD", 0.2)

    def _set_keywordsThreshold(self, value: float):
        self._set_value("WAKE_WORD_OPTIONS.KEYWORDS_THRESHOLD", value)

    keywordsThreshold = Property(
        float, _get_keywordsThreshold, _set_keywordsThreshold, notify=settingsChanged
    )

    # 唤醒词文本
    def _load_wake_word(self):
        """从配置加载唤醒词."""
        self._wake_word = self._get_value("WAKE_WORD_OPTIONS.WAKE_WORD", "")
        self._wake_word_lang = self._get_value("WAKE_WORD_OPTIONS.WAKE_WORD_LANG", "zh")
        self._update_wake_word_preview()

    def _update_wake_word_preview(self):
        """更新唤醒词预览."""
        if not self._wake_word:
            self._wake_word_preview = ""
            return

        try:
            keyword_line, lang, _ = convert_wake_word(self._wake_word)
            self._wake_word_preview = keyword_line
            self._wake_word_lang = lang
        except Exception as e:
            logger.error(f"转换唤醒词失败: {e}")
            self._wake_word_preview = f"转换失败: {e}"

    def _get_wakeWord(self) -> str:
        return self._wake_word

    def _set_wakeWord(self, value: str):
        if self._wake_word != value:
            self._wake_word = value
            self._update_wake_word_preview()
            self.wakeWordChanged.emit()

    wakeWord = Property(str, _get_wakeWord, _set_wakeWord, notify=wakeWordChanged)

    def _get_wakeWordLang(self) -> str:
        return self._wake_word_lang

    wakeWordLang = Property(str, _get_wakeWordLang, notify=wakeWordChanged)

    def _get_wakeWordPreview(self) -> str:
        return self._wake_word_preview

    wakeWordPreview = Property(str, _get_wakeWordPreview, notify=wakeWordChanged)

    @Slot(result=bool)
    def saveWakeWord(self) -> bool:
        """保存唤醒词并生成 keywords.txt.

        Returns:
            是否保存成功
        """
        if not self._wake_word:
            self.statusMessage.emit("请输入唤醒词")
            return False

        try:
            # 转换唤醒词
            keyword_line, lang, model_path = convert_wake_word(self._wake_word)

            # 更新配置
            self._set_value("WAKE_WORD_OPTIONS.WAKE_WORD", self._wake_word)
            self._set_value("WAKE_WORD_OPTIONS.WAKE_WORD_LANG", lang)
            self._set_value("WAKE_WORD_OPTIONS.MODEL_PATH", model_path)

            # 写入 keywords.txt 到用户数据目录
            from src.utils.resource_finder import get_user_data_dir

            keywords_dir = get_user_data_dir() / "keywords"
            keywords_dir.mkdir(parents=True, exist_ok=True)
            keywords_path = keywords_dir / f"{lang}_keywords.txt"

            with open(keywords_path, "w", encoding="utf-8") as f:
                f.write(keyword_line + "\n")

            logger.info(f"唤醒词已保存: {self._wake_word} -> {keywords_path}")
            self.statusMessage.emit(f"唤醒词已保存 ({lang.upper()})")

            # 保存到文件
            self.save()
            return True

        except Exception as e:
            logger.error(f"保存唤醒词失败: {e}", exc_info=True)
            self.statusMessage.emit(f"保存失败: {e}")
            return False

    # ========== 摄像头设置 ==========

    def _get_cameraIndex(self) -> int:
        return self._get_value("CAMERA.camera_index", 0)

    def _set_cameraIndex(self, value: int):
        self._set_value("CAMERA.camera_index", value)

    cameraIndex = Property(
        int, _get_cameraIndex, _set_cameraIndex, notify=settingsChanged
    )

    def _get_frameWidth(self) -> int:
        return self._get_value("CAMERA.frame_width", 640)

    def _set_frameWidth(self, value: int):
        self._set_value("CAMERA.frame_width", value)

    frameWidth = Property(int, _get_frameWidth, _set_frameWidth, notify=settingsChanged)

    def _get_frameHeight(self) -> int:
        return self._get_value("CAMERA.frame_height", 480)

    def _set_frameHeight(self, value: int):
        self._set_value("CAMERA.frame_height", value)

    frameHeight = Property(
        int, _get_frameHeight, _set_frameHeight, notify=settingsChanged
    )

    def _get_fps(self) -> int:
        return self._get_value("CAMERA.fps", 30)

    def _set_fps(self, value: int):
        self._set_value("CAMERA.fps", value)

    fps = Property(int, _get_fps, _set_fps, notify=settingsChanged)

    def _get_vlApiUrl(self) -> str:
        return self._get_value("CAMERA.Local_VL_url", "")

    def _set_vlApiUrl(self, value: str):
        self._set_value("CAMERA.Local_VL_url", value)

    vlApiUrl = Property(str, _get_vlApiUrl, _set_vlApiUrl, notify=settingsChanged)

    def _get_vlApiKey(self) -> str:
        return self._get_value("CAMERA.VLapi_key", "")

    def _set_vlApiKey(self, value: str):
        self._set_value("CAMERA.VLapi_key", value)

    vlApiKey = Property(str, _get_vlApiKey, _set_vlApiKey, notify=settingsChanged)

    def _get_vlModels(self) -> str:
        return self._get_value("CAMERA.models", "glm-4v-plus")

    def _set_vlModels(self, value: str):
        self._set_value("CAMERA.models", value)

    vlModels = Property(str, _get_vlModels, _set_vlModels, notify=settingsChanged)

    # ========== 音频设备设置 ==========

    def _load_audio_devices(self):
        """加载可用的音频设备列表."""
        try:
            devices = list(sd.query_devices())
            self._input_devices = []
            self._output_devices = []

            default_input = sd.default.device[0] if sd.default.device else None
            default_output = sd.default.device[1] if sd.default.device else None

            for i, d in enumerate(devices):
                device_name = d.get("name", "Unknown")
                sample_rate = int(d.get("default_samplerate", 48000))

                # 输入设备
                if int(d.get("max_input_channels", 0)) > 0:
                    default_mark = " (默认)" if i == default_input else ""
                    self._input_devices.append(
                        {
                            "index": i,
                            "name": device_name + default_mark,
                            "raw_name": device_name,
                            "sample_rate": sample_rate,
                            "channels": int(d.get("max_input_channels", 0)),
                        }
                    )

                # 输出设备
                if int(d.get("max_output_channels", 0)) > 0:
                    default_mark = " (默认)" if i == default_output else ""
                    self._output_devices.append(
                        {
                            "index": i,
                            "name": device_name + default_mark,
                            "raw_name": device_name,
                            "sample_rate": sample_rate,
                            "channels": int(d.get("max_output_channels", 0)),
                        }
                    )

            logger.debug(
                f"加载了 {len(self._input_devices)} 个输入设备, {len(self._output_devices)} 个输出设备"
            )
            self.devicesChanged.emit()
        except Exception as e:
            logger.error(f"加载音频设备失败: {e}")
            self._input_devices = []
            self._output_devices = []

    @Slot(result=list)
    def getInputDevices(self) -> list:
        """获取输入设备列表."""
        return [d["name"] for d in self._input_devices]

    @Slot(result=list)
    def getOutputDevices(self) -> list:
        """获取输出设备列表."""
        return [d["name"] for d in self._output_devices]

    @Slot()
    def refreshDevices(self):
        """刷新设备列表."""
        self._load_audio_devices()
        self.statusMessage.emit("设备列表已刷新")

    def _get_selectedInputIndex(self) -> int:
        """获取当前选中的输入设备索引."""
        current_id = self._get_value("AUDIO_DEVICES.input_device_id", -1)
        current_name = self._get_value("AUDIO_DEVICES.input_device_name", "")

        # 优先按设备名称匹配
        if current_name:
            for i, d in enumerate(self._input_devices):
                if d["raw_name"] == current_name:
                    return i

        # 其次按设备ID匹配
        for i, d in enumerate(self._input_devices):
            if d["index"] == current_id:
                return i
        return 0

    def _set_selectedInputIndex(self, index: int):
        """设置选中的输入设备."""
        if 0 <= index < len(self._input_devices):
            device = self._input_devices[index]
            self._set_value("AUDIO_DEVICES.input_device_id", device["index"])
            self._set_value("AUDIO_DEVICES.input_device_name", device["raw_name"])
            self._set_value("AUDIO_DEVICES.input_sample_rate", device["sample_rate"])
            self._set_value("AUDIO_DEVICES.input_channels", min(device["channels"], 1))
            logger.info(f"选择输入设备: {device['name']}")

    selectedInputIndex = Property(
        int, _get_selectedInputIndex, _set_selectedInputIndex, notify=settingsChanged
    )

    def _get_selectedOutputIndex(self) -> int:
        """获取当前选中的输出设备索引."""
        current_id = self._get_value("AUDIO_DEVICES.output_device_id", -1)
        current_name = self._get_value("AUDIO_DEVICES.output_device_name", "")

        # 优先按设备名称匹配
        if current_name:
            for i, d in enumerate(self._output_devices):
                if d["raw_name"] == current_name:
                    return i

        # 其次按设备ID匹配
        for i, d in enumerate(self._output_devices):
            if d["index"] == current_id:
                return i
        return 0

    def _set_selectedOutputIndex(self, index: int):
        """设置选中的输出设备."""
        if 0 <= index < len(self._output_devices):
            device = self._output_devices[index]
            self._set_value("AUDIO_DEVICES.output_device_id", device["index"])
            self._set_value("AUDIO_DEVICES.output_device_name", device["raw_name"])
            self._set_value("AUDIO_DEVICES.output_sample_rate", device["sample_rate"])
            self._set_value("AUDIO_DEVICES.output_channels", min(device["channels"], 2))
            logger.info(f"选择输出设备: {device['name']}")

    selectedOutputIndex = Property(
        int, _get_selectedOutputIndex, _set_selectedOutputIndex, notify=settingsChanged
    )

    # 设备信息显示
    def _get_inputDeviceInfo(self) -> str:
        idx = self._get_selectedInputIndex()
        if 0 <= idx < len(self._input_devices):
            d = self._input_devices[idx]
            return f"采样率: {d['sample_rate']}Hz, 通道: {d['channels']}"
        return "未选择设备"

    inputDeviceInfo = Property(str, _get_inputDeviceInfo, notify=settingsChanged)

    def _get_outputDeviceInfo(self) -> str:
        idx = self._get_selectedOutputIndex()
        if 0 <= idx < len(self._output_devices):
            d = self._output_devices[idx]
            return f"采样率: {d['sample_rate']}Hz, 通道: {d['channels']}"
        return "未选择设备"

    outputDeviceInfo = Property(str, _get_outputDeviceInfo, notify=settingsChanged)

    # Opus 输出采样率
    def _get_opusOutputSampleRate(self) -> int:
        return self._get_value("AUDIO_DEVICES.opus_output_sample_rate", 24000)

    def _set_opusOutputSampleRate(self, value: int):
        self._set_value("AUDIO_DEVICES.opus_output_sample_rate", value)

    opusOutputSampleRate = Property(
        int,
        _get_opusOutputSampleRate,
        _set_opusOutputSampleRate,
        notify=settingsChanged,
    )

    # 音频帧长度
    def _get_frameDuration(self) -> int:
        return self._get_value("AUDIO_DEVICES.frame_duration", 20)

    def _set_frameDuration(self, value: int):
        if value in [20, 40, 60]:
            self._set_value("AUDIO_DEVICES.frame_duration", value)

    frameDuration = Property(
        int, _get_frameDuration, _set_frameDuration, notify=settingsChanged
    )

    # 音频测试
    @Slot()
    def testInputDevice(self):
        """测试输入设备（录音）."""
        if self._testing_input:
            return

        idx = self._get_selectedInputIndex()
        if idx < 0 or idx >= len(self._input_devices):
            self.statusMessage.emit("请先选择输入设备")
            return

        device = self._input_devices[idx]
        self._testing_input = True
        self.statusMessage.emit("开始录音测试...")

        thread = threading.Thread(target=self._do_input_test, args=(device,))
        thread.daemon = True
        thread.start()

    def _do_input_test(self, device: dict):
        """执行录音测试."""
        try:
            device_id = device["index"]
            sample_rate = device["sample_rate"]
            duration = 3

            self.statusMessage.emit(f"请对着麦克风说话 ({duration}秒)...")
            time.sleep(1)

            recording = sd.rec(
                int(duration * sample_rate),
                samplerate=sample_rate,
                channels=1,
                device=device_id,
                dtype=np.float32,
            )
            sd.wait()

            # 分析录音
            max_amplitude = np.max(np.abs(recording))

            if max_amplitude < 0.001:
                self.statusMessage.emit("[失败] 未检测到音频信号")
                self.testComplete.emit("input", False)
            elif max_amplitude > 0.8:
                self.statusMessage.emit("[警告] 音频信号过载")
                self.testComplete.emit("input", True)
            else:
                self.statusMessage.emit(
                    f"[成功] 录音测试通过 (音量: {max_amplitude:.1%})"
                )
                self.testComplete.emit("input", True)

        except Exception as e:
            logger.error(f"录音测试失败: {e}")
            self.statusMessage.emit(f"[错误] {str(e)}")
            self.testComplete.emit("input", False)
        finally:
            self._testing_input = False

    @Slot()
    def testOutputDevice(self):
        """测试输出设备（播放）."""
        if self._testing_output:
            return

        idx = self._get_selectedOutputIndex()
        if idx < 0 or idx >= len(self._output_devices):
            self.statusMessage.emit("请先选择输出设备")
            return

        device = self._output_devices[idx]
        self._testing_output = True
        self.statusMessage.emit("开始播放测试...")

        thread = threading.Thread(target=self._do_output_test, args=(device,))
        thread.daemon = True
        thread.start()

    def _do_output_test(self, device: dict):
        """执行播放测试."""
        try:
            device_id = device["index"]
            sample_rate = device["sample_rate"]
            duration = 2.0
            frequency = 440

            self.statusMessage.emit("播放 440Hz 测试音...")
            time.sleep(0.5)

            # 生成测试音
            t = np.linspace(0, duration, int(sample_rate * duration))
            audio = 0.3 * np.sin(2 * np.pi * frequency * t)

            # 淡入淡出
            fade_samples = int(0.1 * sample_rate)
            audio[:fade_samples] *= np.linspace(0, 1, fade_samples)
            audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)

            sd.play(audio, samplerate=sample_rate, device=device_id)
            sd.wait()

            self.statusMessage.emit("[成功] 播放测试完成")
            self.testComplete.emit("output", True)

        except Exception as e:
            logger.error(f"播放测试失败: {e}")
            self.statusMessage.emit(f"[错误] {str(e)}")
            self.testComplete.emit("output", False)
        finally:
            self._testing_output = False

    # ========== 快捷键设置 ==========

    def _get_shortcutsEnabled(self) -> bool:
        return self._get_value("SHORTCUTS.ENABLED", True)

    def _set_shortcutsEnabled(self, value: bool):
        self._set_value("SHORTCUTS.ENABLED", value)

    shortcutsEnabled = Property(
        bool, _get_shortcutsEnabled, _set_shortcutsEnabled, notify=settingsChanged
    )

    # 快捷键：手动模式
    def _get_shortcutManualModifier(self) -> str:
        return self._get_value("SHORTCUTS.MANUAL_PRESS.modifier", "ctrl")

    def _set_shortcutManualModifier(self, value: str):
        self._set_value("SHORTCUTS.MANUAL_PRESS.modifier", value)

    shortcutManualModifier = Property(
        str,
        _get_shortcutManualModifier,
        _set_shortcutManualModifier,
        notify=settingsChanged,
    )

    def _get_shortcutManualKey(self) -> str:
        return self._get_value("SHORTCUTS.MANUAL_PRESS.key", "j")

    def _set_shortcutManualKey(self, value: str):
        self._set_value("SHORTCUTS.MANUAL_PRESS.key", value)

    shortcutManualKey = Property(
        str, _get_shortcutManualKey, _set_shortcutManualKey, notify=settingsChanged
    )

    # 快捷键：自动模式
    def _get_shortcutAutoModifier(self) -> str:
        return self._get_value("SHORTCUTS.AUTO_TOGGLE.modifier", "ctrl")

    def _set_shortcutAutoModifier(self, value: str):
        self._set_value("SHORTCUTS.AUTO_TOGGLE.modifier", value)

    shortcutAutoModifier = Property(
        str,
        _get_shortcutAutoModifier,
        _set_shortcutAutoModifier,
        notify=settingsChanged,
    )

    def _get_shortcutAutoKey(self) -> str:
        return self._get_value("SHORTCUTS.AUTO_TOGGLE.key", "k")

    def _set_shortcutAutoKey(self, value: str):
        self._set_value("SHORTCUTS.AUTO_TOGGLE.key", value)

    shortcutAutoKey = Property(
        str, _get_shortcutAutoKey, _set_shortcutAutoKey, notify=settingsChanged
    )

    # 快捷键：中断
    def _get_shortcutAbortModifier(self) -> str:
        return self._get_value("SHORTCUTS.ABORT.modifier", "ctrl")

    def _set_shortcutAbortModifier(self, value: str):
        self._set_value("SHORTCUTS.ABORT.modifier", value)

    shortcutAbortModifier = Property(
        str,
        _get_shortcutAbortModifier,
        _set_shortcutAbortModifier,
        notify=settingsChanged,
    )

    def _get_shortcutAbortKey(self) -> str:
        return self._get_value("SHORTCUTS.ABORT.key", "q")

    def _set_shortcutAbortKey(self, value: str):
        self._set_value("SHORTCUTS.ABORT.key", value)

    shortcutAbortKey = Property(
        str, _get_shortcutAbortKey, _set_shortcutAbortKey, notify=settingsChanged
    )

    # 快捷键：模式切换
    def _get_shortcutModeModifier(self) -> str:
        return self._get_value("SHORTCUTS.MODE_TOGGLE.modifier", "ctrl")

    def _set_shortcutModeModifier(self, value: str):
        self._set_value("SHORTCUTS.MODE_TOGGLE.modifier", value)

    shortcutModeModifier = Property(
        str,
        _get_shortcutModeModifier,
        _set_shortcutModeModifier,
        notify=settingsChanged,
    )

    def _get_shortcutModeKey(self) -> str:
        return self._get_value("SHORTCUTS.MODE_TOGGLE.key", "m")

    def _set_shortcutModeKey(self, value: str):
        self._set_value("SHORTCUTS.MODE_TOGGLE.key", value)

    shortcutModeKey = Property(
        str, _get_shortcutModeKey, _set_shortcutModeKey, notify=settingsChanged
    )

    # 快捷键：窗口显示/隐藏
    def _get_shortcutWindowModifier(self) -> str:
        return self._get_value("SHORTCUTS.WINDOW_TOGGLE.modifier", "ctrl")

    def _set_shortcutWindowModifier(self, value: str):
        self._set_value("SHORTCUTS.WINDOW_TOGGLE.modifier", value)

    shortcutWindowModifier = Property(
        str,
        _get_shortcutWindowModifier,
        _set_shortcutWindowModifier,
        notify=settingsChanged,
    )

    def _get_shortcutWindowKey(self) -> str:
        return self._get_value("SHORTCUTS.WINDOW_TOGGLE.key", "w")

    def _set_shortcutWindowKey(self, value: str):
        self._set_value("SHORTCUTS.WINDOW_TOGGLE.key", value)

    shortcutWindowKey = Property(
        str, _get_shortcutWindowKey, _set_shortcutWindowKey, notify=settingsChanged
    )

    # ========== 摄像头设备列表 ==========

    def _load_cameras(self):
        """在后台线程加载摄像头列表，避免阻塞 Qt 主线程."""
        thread = threading.Thread(target=self._do_load_cameras)
        thread.daemon = True
        thread.start()

    def _do_load_cameras(self):
        """执行摄像头扫描（在后台线程）."""
        cameras = []
        try:
            import cv2

            for i in range(10):
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    cameras.append({"index": i, "name": f"摄像头 {i}"})
                    cap.release()
        except ImportError:
            logger.warning("cv2 未安装，无法扫描摄像头")
        except Exception as e:
            logger.error(f"扫描摄像头失败: {e}", exc_info=True)

        self._cameras = cameras
        self.devicesChanged.emit()
        self.statusMessage.emit("摄像头列表已刷新")

    @Slot(result=list)
    def getCameras(self) -> list:
        """获取摄像头列表."""
        return [c["name"] for c in self._cameras]

    @Slot()
    def refreshCameras(self):
        """刷新摄像头列表（非阻塞）."""
        self._load_cameras()

    def _get_selectedCameraIndex(self) -> int:
        """获取当前选中的摄像头索引."""
        current_idx = self._get_value("CAMERA.camera_index", 0)
        for i, c in enumerate(self._cameras):
            if c["index"] == current_idx:
                return i
        return 0

    def _set_selectedCameraIndex(self, index: int):
        """设置选中的摄像头."""
        if 0 <= index < len(self._cameras):
            camera = self._cameras[index]
            self._set_value("CAMERA.camera_index", camera["index"])
            logger.info(f"选择摄像头: {camera['name']}")

    selectedCameraIndex = Property(
        int, _get_selectedCameraIndex, _set_selectedCameraIndex, notify=settingsChanged
    )

    @Slot()
    def testCamera(self):
        """测试摄像头，捕获一帧并显示."""
        if not self._cameras:
            self.statusMessage.emit("没有可用的摄像头")
            return

        idx = self._get_selectedCameraIndex()
        if idx < 0 or idx >= len(self._cameras):
            self.statusMessage.emit("请先选择摄像头")
            return

        camera = self._cameras[idx]
        self.statusMessage.emit(f"正在测试摄像头 {camera['name']}...")

        thread = threading.Thread(target=self._do_camera_test, args=(camera,))
        thread.daemon = True
        thread.start()

    def _do_camera_test(self, camera: dict):
        """执行摄像头测试."""
        try:
            import cv2

            camera_id = camera["index"]
            cap = cv2.VideoCapture(camera_id)

            if not cap.isOpened():
                self.statusMessage.emit("[失败] 无法打开摄像头")
                return

            # 设置分辨率
            width = self._get_value("CAMERA.frame_width", 640)
            height = self._get_value("CAMERA.frame_height", 480)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            # 读取几帧（让摄像头预热）
            for _ in range(5):
                cap.read()

            # 捕获一帧
            ret, frame = cap.read()
            cap.release()

            if not ret or frame is None:
                self.statusMessage.emit("[失败] 无法捕获图像")
                return

            # 获取实际分辨率
            actual_height, actual_width = frame.shape[:2]
            self.statusMessage.emit(
                f"[成功] 摄像头正常 (分辨率: {actual_width}x{actual_height})"
            )

        except ImportError:
            self.statusMessage.emit("[错误] cv2 未安装")
        except Exception as e:
            logger.error(f"摄像头测试失败: {e}")
            self.statusMessage.emit(f"[错误] {str(e)}")
