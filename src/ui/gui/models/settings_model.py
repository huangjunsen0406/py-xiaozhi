"""设置窗口 ViewModel.

配置直映属性通过元数据工厂声明，有状态域（音频/摄像头设备、唤醒词、MCP 工具、目录浏览）
由 settings/ 下对应 mixin 提供。对外仍为 SettingsModel，QML context 名 settingsModel 不变。
"""

import threading
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Property, Qt, Signal, Slot

from src.i18n import (
    LANGUAGE_CHOICES,
    apply_language_from_config,
    set_language,
    t,
)
from src.logging import get_logger
from src.ui.gui.models.base_model import BaseModel
from src.ui.gui.models.settings.audio_devices import SettingsAudioDevicesMixin
from src.ui.gui.models.settings.camera_devices import SettingsCameraDevicesMixin
from src.ui.gui.models.settings.mcp_tools import SettingsMcpToolsMixin
from src.ui.gui.models.settings.system_options import SettingsSystemOptionsMixin
from src.ui.gui.models.settings.wake_word import SettingsWakeWordMixin
from src.ui.shared.settings_helpers import get_draft_value, set_draft_value
from src.utils.config_manager import ConfigManager

logger = get_logger()


def _config_property(
    prop_type: type,
    path: str,
    default: Any,
    *,
    notify: Signal,
    strip: bool = False,
    coerce_int: bool = False,
    allowed: tuple[Any, ...] | None = None,
) -> Property:
    """声明直接映射草稿配置路径的 Qt Property，消除机械 getter/setter 样板."""

    def _get(self):
        value = self._get_value(path, default)
        if strip:
            return value or ""
        if coerce_int:
            try:
                return int(value)
            except (TypeError, ValueError):
                return default
        return value

    def _set(self, value) -> None:
        if strip:
            value = value.strip() if value else ""
        elif coerce_int:
            value = int(value)
        if allowed is not None and value not in allowed:
            return
        self._set_value(path, value)

    return Property(prop_type, _get, _set, notify=notify)


class SettingsModel(
    SettingsSystemOptionsMixin,
    SettingsMcpToolsMixin,
    SettingsWakeWordMixin,
    SettingsAudioDevicesMixin,
    SettingsCameraDevicesMixin,
    BaseModel,
):
    """设置窗口数据模型."""

    settingsChanged = Signal()
    devicesChanged = Signal()
    statusMessage = Signal(str)
    statusReset = Signal()
    testComplete = Signal(str, bool)
    wakeWordChanged = Signal()
    configSaved = Signal()
    _uiCallbackRequested = Signal(object)

    def __init__(
        self,
        parent=None,
        event_bus=None,
        task_manager=None,
        config_manager: ConfigManager | None = None,
        runtime_tool_names: Callable[[], tuple[str, ...]] | None = None,
    ):
        super().__init__(parent)
        self._closed = False
        self._uiCallbackRequested.connect(
            self._run_ui_callback, Qt.ConnectionType.QueuedConnection
        )
        self._config_manager = (
            config_manager if config_manager is not None else ConfigManager.from_dict()
        )
        self._runtime_tool_names = (
            runtime_tool_names if runtime_tool_names is not None else lambda: ()
        )
        self._config: dict = {}
        # 可选：用于「刷新音频设备」时协调 AudioPlugin 停流重枚举
        self._event_bus = event_bus
        self._task_manager = task_manager

        self._input_devices: list[dict] = []
        self._output_devices: list[dict] = []

        self._cameras: list[dict] = []
        self._cameras_loading = False
        self._cameras_loaded_once = False
        self._audio_devices_loaded = False
        self._audio_devices_loading = False
        self._audio_devices_refreshing = False
        self._audio_generation = 0

        self._testing_input = False
        self._testing_output = False

        self._wake_word: str = ""
        self._wake_word_lang: str = "zh"
        self._wake_word_preview: str = ""
        self._language_previewed: bool = False

        # 启动仅读配置；音频/摄像头/唤醒词预览延后到打开设置时再处理
        self._load_config()
        self._load_wake_word(update_preview=False)

    @Slot(object)
    def _run_ui_callback(self, callback) -> None:
        if not self._closed:
            try:
                callback()
            except Exception as exc:
                logger.error("设置页 UI 回调失败: %s", exc, exc_info=True)

    def _schedule_ui(self, callback) -> None:
        """A receiver-bound queued signal always runs on this QObject's thread."""
        if self._closed:
            return
        try:
            self._uiCallbackRequested.emit(callback)
        except RuntimeError:
            # Qt may already have deleted the receiver while a worker finishes.
            pass

    def close(self) -> None:
        self._closed = True
        self._audio_generation += 1
        self._audio_devices_loading = False
        self._audio_devices_refreshing = False
        self._cameras_loading = False
        self._runtime_tool_names = lambda: ()

    def _run_worker(
        self,
        target,
        *args,
        name: str | None = None,
        test_kind: str | None = None,
        clear_flags=None,
    ) -> None:
        """后台线程统一入口：异常必达 statusMessage / testComplete."""

        if self._closed:
            return

        def _entry():
            try:
                target(*args)
            except Exception as e:
                logger.error(
                    f"设置页后台任务失败 ({name or target}): {e}", exc_info=True
                )
                try:
                    self.statusMessage.emit(t("common.error_with_msg", error=e))
                except RuntimeError:
                    pass
                if test_kind is not None:
                    try:
                        self.testComplete.emit(test_kind, False)
                    except RuntimeError:
                        pass
            finally:
                if clear_flags is not None:
                    self._schedule_ui(clear_flags)

        thread = threading.Thread(
            target=_entry, name=name or "settings:worker", daemon=True
        )
        thread.start()

    # ========== 配置读写 ==========

    def _load_config(self):
        """从注入的运行时配置复制独立草稿，避免覆盖其他配置写入者的更新."""
        self._config = self._config_manager.get_config("", {})

    def _get_value(self, path: str, default: Any = None) -> Any:
        """获取配置值，支持点号分隔的路径."""
        return get_draft_value(self._config, path, default)

    def _set_value(self, path: str, value: Any):
        """设置配置值，支持点号分隔的路径."""
        set_draft_value(self._config, path, value)
        self.settingsChanged.emit()

    @Slot(result=bool)
    def save(self) -> bool:
        """提交草稿并更新运行时；失败时保留草稿供用户重试."""
        self.set_error("")
        self.statusReset.emit()
        try:
            error = self._config_manager.commit_draft(self._config)
            if error is not None:
                self.set_error(error)
                return False
            self._language_previewed = False
            logger.info("设置已保存并加载到运行时配置")
            self.statusMessage.emit(t("settings.saved"))
            self.configSaved.emit()
            return True
        except Exception as e:
            logger.error(f"保存配置失败: {e}", exc_info=True)
            self.set_error(t("settings.save_failed", error=e))
            return False

    @Slot()
    def discard(self):
        """丢弃草稿并恢复当前运行时快照，不枚举设备或加载模型."""
        if self._language_previewed:
            self._language_previewed = False
            apply_language_from_config(self._config_manager)
        self._load_config()
        self._load_wake_word(update_preview=False)
        self.set_error("")
        self.statusReset.emit()
        self.settingsChanged.emit()
        self.wakeWordChanged.emit()

    @Slot()
    def reload(self):
        """打开设置时恢复草稿，再按原策略刷新设备与唤醒词预览."""
        self.discard()
        self._load_audio_devices(force=True)
        self._load_cameras(force=True)
        self._load_wake_word()
        self.wakeWordChanged.emit()
        logger.info("设置已重新加载")

    # ========== QML Properties（元数据直映）==========
    clientId = _config_property(str, "SYSTEM_OPTIONS.CLIENT_ID", "", notify=settingsChanged)
    deviceId = _config_property(str, "SYSTEM_OPTIONS.DEVICE_ID", "", notify=settingsChanged)

    def _get_language(self) -> str:
        val = str(self._get_value("SYSTEM_OPTIONS.LANGUAGE", "auto") or "auto")
        return val if val in LANGUAGE_CHOICES else "auto"

    def _set_language(self, value: str) -> None:
        val = str(value or "auto").strip()
        if val not in LANGUAGE_CHOICES:
            return
        self._set_value("SYSTEM_OPTIONS.LANGUAGE", val)
        self._language_previewed = True
        set_language(val)

    language = Property(str, _get_language, _set_language, notify=settingsChanged)
    otaUrl = _config_property(str, "SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL", "", notify=settingsChanged)
    websocketUrl = _config_property(str, "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL", "", notify=settingsChanged)
    websocketToken = _config_property(str, "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN", "", notify=settingsChanged)
    authorizationUrl = _config_property(str, "SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL", "", notify=settingsChanged)
    activationVersion = _config_property(str, "SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION", "v1", notify=settingsChanged)
    windowSizeMode = _config_property(str, "SYSTEM_OPTIONS.WINDOW_SIZE_MODE", "default", notify=settingsChanged)
    mqttEndpoint = _config_property(str, "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.endpoint", "", notify=settingsChanged)
    mqttClientId = _config_property(str, "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.client_id", "", notify=settingsChanged)
    mqttUsername = _config_property(str, "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.username", "", notify=settingsChanged)
    mqttPassword = _config_property(str, "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.password", "", notify=settingsChanged)
    mqttPublishTopic = _config_property(str, "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.publish_topic", "", notify=settingsChanged)
    mqttSubscribeTopic = _config_property(str, "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.subscribe_topic", "", notify=settingsChanged)
    aecEnabled = _config_property(bool, "AEC_OPTIONS.ENABLED", False, notify=settingsChanged)
    aecReferenceMode = _config_property(str, "AEC_OPTIONS.REFERENCE_MODE", "self", notify=settingsChanged)
    aecMediaParallel = _config_property(bool, "AEC_OPTIONS.MEDIA_PARALLEL", True, notify=settingsChanged)
    aecFrameDelay = _config_property(int, "AEC_OPTIONS.FRAME_DELAY", 3, notify=settingsChanged, coerce_int=True)
    aecEnablePreprocess = _config_property(bool, "AEC_OPTIONS.ENABLE_PREPROCESS", True, notify=settingsChanged)

    userDataDir = Property(
        str, SettingsSystemOptionsMixin._get_userDataDir, notify=settingsChanged
    )

    @Slot(result=bool)
    def openUserDataDir(self) -> bool:
        return self._open_user_data_dir()

    mcpToolsCatalogJson = Property(
        str, SettingsMcpToolsMixin._get_mcpToolsCatalogJson, notify=settingsChanged
    )
    mcpToolsDisabledJson = Property(
        str,
        SettingsMcpToolsMixin._get_mcpToolsDisabledJson,
        SettingsMcpToolsMixin._set_mcpToolsDisabledJson,
        notify=settingsChanged,
    )
    mcpAllowMediaPlayer = Property(
        bool,
        SettingsMcpToolsMixin._get_mcpAllowMediaPlayer,
        SettingsMcpToolsMixin._set_mcpAllowMediaPlayer,
        notify=settingsChanged,
    )
    mcpPluginsDir = Property(
        str, SettingsMcpToolsMixin._get_mcpPluginsDir, notify=settingsChanged
    )
    mcpInstalledPluginsJson = Property(
        str, SettingsMcpToolsMixin._get_mcpInstalledPluginsJson, notify=settingsChanged
    )

    @Slot(str, bool)
    def setMcpToolEnabled(self, name: str, enabled: bool) -> None:
        self._set_mcpToolEnabled(name, enabled)

    @Slot(str, bool)
    def setMcpToolGroupEnabled(self, group: str, enabled: bool) -> None:
        self._set_mcpToolGroupEnabled(group, enabled)

    @Slot(result=bool)
    def importMcpPluginZip(self) -> bool:
        return self._import_mcp_plugin_zip()

    @Slot(result=bool)
    def importMcpPluginDir(self) -> bool:
        return self._import_mcp_plugin_dir()

    @Slot(str, result=bool)
    def uninstallMcpPlugin(self, plugin_id: str) -> bool:
        return self._uninstall_mcp_plugin(plugin_id)

    @Slot(result=bool)
    def openMcpPluginsDir(self) -> bool:
        return self._open_mcp_plugins_dir()

    @Slot()
    def refreshMcpPlugins(self) -> None:
        self._trigger_runtime_plugin_reload()

    wakeWordEnabled = _config_property(bool, "WAKE_WORD_OPTIONS.USE_WAKE_WORD", False, notify=settingsChanged)
    modelPath = _config_property(str, "WAKE_WORD_OPTIONS.MODEL_PATH", "models", notify=settingsChanged)
    numThreads = _config_property(int, "WAKE_WORD_OPTIONS.NUM_THREADS", 4, notify=settingsChanged)
    keywordsScore = _config_property(float, "WAKE_WORD_OPTIONS.KEYWORDS_SCORE", 1.8, notify=settingsChanged)
    keywordsThreshold = _config_property(float, "WAKE_WORD_OPTIONS.KEYWORDS_THRESHOLD", 0.2, notify=settingsChanged)
    wakeWord = Property(str, SettingsWakeWordMixin._get_wakeWord, SettingsWakeWordMixin._set_wakeWord, notify=wakeWordChanged)
    wakeWordLang = Property(str, SettingsWakeWordMixin._get_wakeWordLang, notify=wakeWordChanged)
    wakeWordPreview = Property(str, SettingsWakeWordMixin._get_wakeWordPreview, notify=wakeWordChanged)

    cameraIndex = _config_property(int, "CAMERA.camera_index", 0, notify=settingsChanged)
    frameWidth = _config_property(int, "CAMERA.frame_width", 640, notify=settingsChanged)
    frameHeight = _config_property(int, "CAMERA.frame_height", 480, notify=settingsChanged)
    vlApiUrl = _config_property(str, "CAMERA.Local_VL_url", "", notify=settingsChanged)
    vlApiKey = _config_property(str, "CAMERA.VLapi_key", "", notify=settingsChanged)
    vlModels = _config_property(str, "CAMERA.models", "glm-4v-plus", notify=settingsChanged)

    selectedInputIndex = Property(
        int, SettingsAudioDevicesMixin._get_selectedInputIndex, SettingsAudioDevicesMixin._set_selectedInputIndex, notify=settingsChanged
    )
    selectedOutputIndex = Property(
        int, SettingsAudioDevicesMixin._get_selectedOutputIndex, SettingsAudioDevicesMixin._set_selectedOutputIndex, notify=settingsChanged
    )
    inputDeviceInfo = Property(str, SettingsAudioDevicesMixin._get_inputDeviceInfo, notify=settingsChanged)
    outputDeviceInfo = Property(str, SettingsAudioDevicesMixin._get_outputDeviceInfo, notify=settingsChanged)
    opusOutputSampleRate = _config_property(int, "AUDIO_DEVICES.opus_output_sample_rate", 24000, notify=settingsChanged)
    frameDuration = _config_property(int, "AUDIO_DEVICES.frame_duration", 20, notify=settingsChanged, allowed=(20, 40, 60))

    shortcutsEnabled = _config_property(bool, "SHORTCUTS.ENABLED", True, notify=settingsChanged)
    shortcutManualModifier = _config_property(str, "SHORTCUTS.MANUAL_PRESS.modifier", "ctrl", notify=settingsChanged)
    shortcutManualKey = _config_property(str, "SHORTCUTS.MANUAL_PRESS.key", "j", notify=settingsChanged)
    shortcutAutoModifier = _config_property(str, "SHORTCUTS.AUTO_TOGGLE.modifier", "ctrl", notify=settingsChanged)
    shortcutAutoKey = _config_property(str, "SHORTCUTS.AUTO_TOGGLE.key", "k", notify=settingsChanged)
    shortcutAbortModifier = _config_property(str, "SHORTCUTS.ABORT.modifier", "ctrl", notify=settingsChanged)
    shortcutAbortKey = _config_property(str, "SHORTCUTS.ABORT.key", "q", notify=settingsChanged)
    shortcutModeModifier = _config_property(str, "SHORTCUTS.MODE_TOGGLE.modifier", "ctrl", notify=settingsChanged)
    shortcutModeKey = _config_property(str, "SHORTCUTS.MODE_TOGGLE.key", "m", notify=settingsChanged)
    shortcutWindowModifier = _config_property(str, "SHORTCUTS.WINDOW_TOGGLE.modifier", "ctrl", notify=settingsChanged)
    shortcutWindowKey = _config_property(str, "SHORTCUTS.WINDOW_TOGGLE.key", "w", notify=settingsChanged)
    selectedCameraIndex = Property(
        int, SettingsCameraDevicesMixin._get_selectedCameraIndex, SettingsCameraDevicesMixin._set_selectedCameraIndex, notify=settingsChanged
    )

