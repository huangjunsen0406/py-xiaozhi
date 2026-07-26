"""设置窗口 ViewModel.

按功能拆成 settings/ 下多个 mixin，本文件组合并声明 QML Property。
对外 仍为 SettingsModel，QML context 名 settingsModel 不变。
"""

import json
import os
import threading
from typing import Any

from PySide6.QtCore import Property, Signal, Slot

from src.logging import get_logger
from src.ui.gui.models.base_model import BaseModel
from src.ui.gui.models.settings.audio_devices import SettingsAudioDevicesMixin
from src.ui.gui.models.settings.camera_devices import SettingsCameraDevicesMixin
from src.ui.gui.models.settings.camera_options import SettingsCameraOptionsMixin
from src.ui.gui.models.settings.mcp_tools import SettingsMcpToolsMixin
from src.ui.gui.models.settings.shortcuts import SettingsShortcutsMixin
from src.ui.gui.models.settings.system_options import SettingsSystemOptionsMixin
from src.ui.gui.models.settings.wake_word import SettingsWakeWordMixin
from src.utils.config_manager import get_config
from src.utils.resource_finder import get_user_data_dir

logger = get_logger()


class SettingsModel(
    SettingsSystemOptionsMixin,
    SettingsMcpToolsMixin,
    SettingsWakeWordMixin,
    SettingsCameraOptionsMixin,
    SettingsAudioDevicesMixin,
    SettingsShortcutsMixin,
    SettingsCameraDevicesMixin,
    BaseModel,
):
    """设置窗口数据模型（组合 mixin）."""

    settingsChanged = Signal()
    devicesChanged = Signal()
    statusMessage = Signal(str)
    testComplete = Signal(str, bool)
    wakeWordChanged = Signal()
    configSaved = Signal()
    # MCP 工具禁用列表相对打开/上次保存是否变化 → 保存后可能触发重连
    mcpToolsNeedReconnect = Signal()

    def __init__(self, parent=None, event_bus=None, task_manager=None):
        super().__init__(parent)
        self._config_manager = get_config()
        self._config_path = get_user_data_dir() / "config" / "config.json"
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
        self._audio_devices_refreshing = False

        self._testing_input = False
        self._testing_output = False

        self._wake_word: str = ""
        self._wake_word_lang: str = "zh"
        self._wake_word_preview: str = ""
        # 打开设置时快照，保存时对比是否变更 MCP 工具暴露
        self._mcp_disabled_snapshot: list[str] = []

        # 启动仅读配置；音频/摄像头/唤醒词预览延后到打开设置时再处理
        self._load_config()
        self._load_wake_word(update_preview=False)
        self._snapshot_mcp_disabled()

    def _run_worker(
        self,
        target,
        *args,
        name: str | None = None,
        test_kind: str | None = None,
        clear_flags=None,
    ) -> None:
        """后台线程统一入口：异常必达 statusMessage / testComplete."""

        def _entry():
            try:
                target(*args)
            except Exception as e:
                logger.error(
                    f"设置页后台任务失败 ({name or target}): {e}", exc_info=True
                )
                try:
                    self.statusMessage.emit(f"[错误] {e}")
                except Exception:
                    pass
                if test_kind is not None:
                    try:
                        self.testComplete.emit(test_kind, False)
                    except Exception:
                        pass
            finally:
                if clear_flags is not None:
                    try:
                        clear_flags()
                    except Exception:
                        pass

        thread = threading.Thread(
            target=_entry, name=name or "settings:worker", daemon=True
        )
        thread.start()

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
            logger.error(f"加载配置失败: {e}", exc_info=True)
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

    def _snapshot_mcp_disabled(self) -> None:
        from src.mcp.tool_catalog import normalize_disabled

        raw = self._get_value("MCP_TOOLS.DISABLED", []) or []
        self._mcp_disabled_snapshot = list(normalize_disabled(raw))

    @Slot()
    def save(self):
        """保存配置到文件，并让运行中的 ConfigManager 重新读盘."""
        try:
            from src.mcp.tool_catalog import normalize_disabled

            new_disabled = normalize_disabled(
                self._get_value("MCP_TOOLS.DISABLED", []) or []
            )
            mcp_changed = sorted(new_disabled) != sorted(self._mcp_disabled_snapshot)

            # 原子写：临时文件 + replace，与 ConfigManager 一致
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._config_path.with_suffix(".tmp")
            tmp_path.write_text(
                json.dumps(self._config, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp_path, self._config_path)
            try:
                self._config_manager.reload_config()
            except Exception as e:
                logger.warning(f"ConfigManager 重载失败: {e}", exc_info=True)
            logger.info("设置已保存")
            self._snapshot_mcp_disabled()
            if mcp_changed:
                self.statusMessage.emit("配置已保存（MCP 工具变更，将重连以更新）")
                self.mcpToolsNeedReconnect.emit()
            else:
                self.statusMessage.emit("配置已保存")
            self.configSaved.emit()
        except Exception as e:
            logger.error(f"保存配置失败: {e}", exc_info=True)
            self.set_error(f"保存配置失败: {e}")

    @Slot()
    def reload(self):
        """重新加载配置（打开设置窗口时调用；此时才枚举设备）."""
        self._load_config()
        self._load_audio_devices(force=True)
        self._load_cameras(force=True)
        self._load_wake_word()
        self._snapshot_mcp_disabled()
        self.settingsChanged.emit()
        logger.info("设置已重新加载")

    # ========== QML Properties（实现见各 mixin）==========
    clientId = Property(str, SettingsSystemOptionsMixin._get_clientId, SettingsSystemOptionsMixin._set_clientId, notify=settingsChanged)
    deviceId = Property(str, SettingsSystemOptionsMixin._get_deviceId, SettingsSystemOptionsMixin._set_deviceId, notify=settingsChanged)
    otaUrl = Property(str, SettingsSystemOptionsMixin._get_otaUrl, SettingsSystemOptionsMixin._set_otaUrl, notify=settingsChanged)
    websocketUrl = Property(
        str, SettingsSystemOptionsMixin._get_websocketUrl, SettingsSystemOptionsMixin._set_websocketUrl, notify=settingsChanged
    )
    websocketToken = Property(
        str, SettingsSystemOptionsMixin._get_websocketToken, SettingsSystemOptionsMixin._set_websocketToken, notify=settingsChanged
    )
    authorizationUrl = Property(
        str, SettingsSystemOptionsMixin._get_authorizationUrl, SettingsSystemOptionsMixin._set_authorizationUrl, notify=settingsChanged
    )
    activationVersion = Property(
        str, SettingsSystemOptionsMixin._get_activationVersion, SettingsSystemOptionsMixin._set_activationVersion, notify=settingsChanged
    )
    windowSizeMode = Property(
        str, SettingsSystemOptionsMixin._get_windowSizeMode, SettingsSystemOptionsMixin._set_windowSizeMode, notify=settingsChanged
    )
    musicSearchUrl = Property(
        str, SettingsSystemOptionsMixin._get_musicSearchUrl, SettingsSystemOptionsMixin._set_musicSearchUrl, notify=settingsChanged
    )
    musicUrlApi = Property(
        str, SettingsSystemOptionsMixin._get_musicUrlApi, SettingsSystemOptionsMixin._set_musicUrlApi, notify=settingsChanged
    )
    musicUrlApiKey = Property(
        str, SettingsSystemOptionsMixin._get_musicUrlApiKey, SettingsSystemOptionsMixin._set_musicUrlApiKey, notify=settingsChanged
    )
    musicDefaultPlatform = Property(
        str,
        SettingsSystemOptionsMixin._get_musicDefaultPlatform,
        SettingsSystemOptionsMixin._set_musicDefaultPlatform,
        notify=settingsChanged,
    )
    musicDefaultQuality = Property(
        str, SettingsSystemOptionsMixin._get_musicDefaultQuality, SettingsSystemOptionsMixin._set_musicDefaultQuality, notify=settingsChanged
    )
    mqttEndpoint = Property(
        str, SettingsSystemOptionsMixin._get_mqttEndpoint, SettingsSystemOptionsMixin._set_mqttEndpoint, notify=settingsChanged
    )
    mqttClientId = Property(
        str, SettingsSystemOptionsMixin._get_mqttClientId, SettingsSystemOptionsMixin._set_mqttClientId, notify=settingsChanged
    )
    mqttUsername = Property(
        str, SettingsSystemOptionsMixin._get_mqttUsername, SettingsSystemOptionsMixin._set_mqttUsername, notify=settingsChanged
    )
    mqttPassword = Property(
        str, SettingsSystemOptionsMixin._get_mqttPassword, SettingsSystemOptionsMixin._set_mqttPassword, notify=settingsChanged
    )
    mqttPublishTopic = Property(
        str, SettingsSystemOptionsMixin._get_mqttPublishTopic, SettingsSystemOptionsMixin._set_mqttPublishTopic, notify=settingsChanged
    )
    mqttSubscribeTopic = Property(
        str, SettingsSystemOptionsMixin._get_mqttSubscribeTopic, SettingsSystemOptionsMixin._set_mqttSubscribeTopic, notify=settingsChanged
    )
    aecEnabled = Property(
        bool, SettingsSystemOptionsMixin._get_aecEnabled, SettingsSystemOptionsMixin._set_aecEnabled, notify=settingsChanged
    )
    pathCacheDir = Property(
        str,
        SettingsSystemOptionsMixin._get_pathCacheDir,
        SettingsSystemOptionsMixin._set_pathCacheDir,
        notify=settingsChanged,
    )
    pathLogDir = Property(
        str,
        SettingsSystemOptionsMixin._get_pathLogDir,
        SettingsSystemOptionsMixin._set_pathLogDir,
        notify=settingsChanged,
    )
    pathMusicCacheDir = Property(
        str,
        SettingsSystemOptionsMixin._get_pathMusicCacheDir,
        SettingsSystemOptionsMixin._set_pathMusicCacheDir,
        notify=settingsChanged,
    )
    pathKeywordsDir = Property(
        str,
        SettingsSystemOptionsMixin._get_pathKeywordsDir,
        SettingsSystemOptionsMixin._set_pathKeywordsDir,
        notify=settingsChanged,
    )
    pathMcpPluginsDir = Property(
        str,
        SettingsSystemOptionsMixin._get_pathMcpPluginsDir,
        SettingsSystemOptionsMixin._set_pathMcpPluginsDir,
        notify=settingsChanged,
    )
    pathDefaultCacheDir = Property(
        str, SettingsSystemOptionsMixin._get_pathDefaultCacheDir, notify=settingsChanged
    )
    pathDefaultLogDir = Property(
        str, SettingsSystemOptionsMixin._get_pathDefaultLogDir, notify=settingsChanged
    )
    pathDefaultMusicCacheDir = Property(
        str,
        SettingsSystemOptionsMixin._get_pathDefaultMusicCacheDir,
        notify=settingsChanged,
    )
    pathDefaultKeywordsDir = Property(
        str,
        SettingsSystemOptionsMixin._get_pathDefaultKeywordsDir,
        notify=settingsChanged,
    )
    pathDefaultMcpPluginsDir = Property(
        str,
        SettingsSystemOptionsMixin._get_pathDefaultMcpPluginsDir,
        notify=settingsChanged,
    )
    pathHints = Property(
        str, SettingsSystemOptionsMixin._get_pathHints, notify=settingsChanged
    )

    @Slot(str, result=str)
    def browseDirectory(self, which: str) -> str:
        """打开系统目录选择框。which: cache|log|music|keywords|mcp.

        返回选中的路径；取消返回空串（QML 勿写回）。
        """
        which = (which or "").strip().lower()
        getters = {
            "cache": self._get_pathCacheDir,
            "log": self._get_pathLogDir,
            "music": self._get_pathMusicCacheDir,
            "keywords": self._get_pathKeywordsDir,
            "mcp": self._get_pathMcpPluginsDir,
        }
        setters = {
            "cache": self._set_pathCacheDir,
            "log": self._set_pathLogDir,
            "music": self._set_pathMusicCacheDir,
            "keywords": self._set_pathKeywordsDir,
            "mcp": self._set_pathMcpPluginsDir,
        }
        titles = {
            "cache": "选择缓存目录",
            "log": "选择日志目录",
            "music": "选择音乐缓存目录",
            "keywords": "选择唤醒词目录",
            "mcp": "选择 MCP 插件目录",
        }
        if which not in getters:
            return ""
        current = getters[which]()
        path = self._browse_directory(titles[which], current, which)
        if path:
            setters[which](path)
        return path

    @Slot(str)
    def clearPathDir(self, which: str) -> None:
        """清空某项自定义路径（恢复默认）."""
        which = (which or "").strip().lower()
        setters = {
            "cache": self._set_pathCacheDir,
            "log": self._set_pathLogDir,
            "music": self._set_pathMusicCacheDir,
            "keywords": self._set_pathKeywordsDir,
            "mcp": self._set_pathMcpPluginsDir,
        }
        if which in setters:
            setters[which]("")

    mcpToolsCatalogJson = Property(
        str, SettingsMcpToolsMixin._get_mcpToolsCatalogJson, notify=settingsChanged
    )
    mcpToolsDisabledJson = Property(
        str,
        SettingsMcpToolsMixin._get_mcpToolsDisabledJson,
        SettingsMcpToolsMixin._set_mcpToolsDisabledJson,
        notify=settingsChanged,
    )

    @Slot(str, bool)
    def setMcpToolEnabled(self, name: str, enabled: bool) -> None:
        self._set_mcpToolEnabled(name, enabled)

    @Slot(str, bool)
    def setMcpToolGroupEnabled(self, group: str, enabled: bool) -> None:
        self._set_mcpToolGroupEnabled(group, enabled)

    wakeWordEnabled = Property(
        bool, SettingsWakeWordMixin._get_wakeWordEnabled, SettingsWakeWordMixin._set_wakeWordEnabled, notify=settingsChanged
    )
    modelPath = Property(str, SettingsWakeWordMixin._get_modelPath, SettingsWakeWordMixin._set_modelPath, notify=settingsChanged)
    numThreads = Property(int, SettingsWakeWordMixin._get_numThreads, SettingsWakeWordMixin._set_numThreads, notify=settingsChanged)
    keywordsScore = Property(
        float, SettingsWakeWordMixin._get_keywordsScore, SettingsWakeWordMixin._set_keywordsScore, notify=settingsChanged
    )
    keywordsThreshold = Property(
        float, SettingsWakeWordMixin._get_keywordsThreshold, SettingsWakeWordMixin._set_keywordsThreshold, notify=settingsChanged
    )
    wakeWord = Property(str, SettingsWakeWordMixin._get_wakeWord, SettingsWakeWordMixin._set_wakeWord, notify=wakeWordChanged)
    wakeWordLang = Property(str, SettingsWakeWordMixin._get_wakeWordLang, notify=wakeWordChanged)
    wakeWordPreview = Property(str, SettingsWakeWordMixin._get_wakeWordPreview, notify=wakeWordChanged)
    cameraIndex = Property(
        int, SettingsCameraOptionsMixin._get_cameraIndex, SettingsCameraOptionsMixin._set_cameraIndex, notify=settingsChanged
    )
    frameWidth = Property(int, SettingsCameraOptionsMixin._get_frameWidth, SettingsCameraOptionsMixin._set_frameWidth, notify=settingsChanged)
    frameHeight = Property(
        int, SettingsCameraOptionsMixin._get_frameHeight, SettingsCameraOptionsMixin._set_frameHeight, notify=settingsChanged
    )
    fps = Property(int, SettingsCameraOptionsMixin._get_fps, SettingsCameraOptionsMixin._set_fps, notify=settingsChanged)
    vlApiUrl = Property(str, SettingsCameraOptionsMixin._get_vlApiUrl, SettingsCameraOptionsMixin._set_vlApiUrl, notify=settingsChanged)
    vlApiKey = Property(str, SettingsCameraOptionsMixin._get_vlApiKey, SettingsCameraOptionsMixin._set_vlApiKey, notify=settingsChanged)
    vlModels = Property(str, SettingsCameraOptionsMixin._get_vlModels, SettingsCameraOptionsMixin._set_vlModels, notify=settingsChanged)
    selectedInputIndex = Property(
        int, SettingsAudioDevicesMixin._get_selectedInputIndex, SettingsAudioDevicesMixin._set_selectedInputIndex, notify=settingsChanged
    )
    selectedOutputIndex = Property(
        int, SettingsAudioDevicesMixin._get_selectedOutputIndex, SettingsAudioDevicesMixin._set_selectedOutputIndex, notify=settingsChanged
    )
    inputDeviceInfo = Property(str, SettingsAudioDevicesMixin._get_inputDeviceInfo, notify=settingsChanged)
    outputDeviceInfo = Property(str, SettingsAudioDevicesMixin._get_outputDeviceInfo, notify=settingsChanged)
    opusOutputSampleRate = Property(
        int,
        SettingsAudioDevicesMixin._get_opusOutputSampleRate,
        SettingsAudioDevicesMixin._set_opusOutputSampleRate,
        notify=settingsChanged,
    )
    frameDuration = Property(
        int, SettingsAudioDevicesMixin._get_frameDuration, SettingsAudioDevicesMixin._set_frameDuration, notify=settingsChanged
    )
    shortcutsEnabled = Property(
        bool, SettingsShortcutsMixin._get_shortcutsEnabled, SettingsShortcutsMixin._set_shortcutsEnabled, notify=settingsChanged
    )
    shortcutManualModifier = Property(
        str,
        SettingsShortcutsMixin._get_shortcutManualModifier,
        SettingsShortcutsMixin._set_shortcutManualModifier,
        notify=settingsChanged,
    )
    shortcutManualKey = Property(
        str, SettingsShortcutsMixin._get_shortcutManualKey, SettingsShortcutsMixin._set_shortcutManualKey, notify=settingsChanged
    )
    shortcutAutoModifier = Property(
        str,
        SettingsShortcutsMixin._get_shortcutAutoModifier,
        SettingsShortcutsMixin._set_shortcutAutoModifier,
        notify=settingsChanged,
    )
    shortcutAutoKey = Property(
        str, SettingsShortcutsMixin._get_shortcutAutoKey, SettingsShortcutsMixin._set_shortcutAutoKey, notify=settingsChanged
    )
    shortcutAbortModifier = Property(
        str,
        SettingsShortcutsMixin._get_shortcutAbortModifier,
        SettingsShortcutsMixin._set_shortcutAbortModifier,
        notify=settingsChanged,
    )
    shortcutAbortKey = Property(
        str, SettingsShortcutsMixin._get_shortcutAbortKey, SettingsShortcutsMixin._set_shortcutAbortKey, notify=settingsChanged
    )
    shortcutModeModifier = Property(
        str,
        SettingsShortcutsMixin._get_shortcutModeModifier,
        SettingsShortcutsMixin._set_shortcutModeModifier,
        notify=settingsChanged,
    )
    shortcutModeKey = Property(
        str, SettingsShortcutsMixin._get_shortcutModeKey, SettingsShortcutsMixin._set_shortcutModeKey, notify=settingsChanged
    )
    shortcutWindowModifier = Property(
        str,
        SettingsShortcutsMixin._get_shortcutWindowModifier,
        SettingsShortcutsMixin._set_shortcutWindowModifier,
        notify=settingsChanged,
    )
    shortcutWindowKey = Property(
        str, SettingsShortcutsMixin._get_shortcutWindowKey, SettingsShortcutsMixin._set_shortcutWindowKey, notify=settingsChanged
    )
    selectedCameraIndex = Property(
        int, SettingsCameraDevicesMixin._get_selectedCameraIndex, SettingsCameraDevicesMixin._set_selectedCameraIndex, notify=settingsChanged
    )

