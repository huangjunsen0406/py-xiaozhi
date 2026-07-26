"""系统选项：设备 ID、网络、MQTT、音乐、AEC."""


class SettingsSystemOptionsMixin:
    # ========== 系统选项 ==========

    # CLIENT_ID
    def _get_clientId(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.CLIENT_ID", "")

    def _set_clientId(self, value: str):
        self._set_value("SYSTEM_OPTIONS.CLIENT_ID", value)

    # DEVICE_ID
    def _get_deviceId(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.DEVICE_ID", "")

    def _set_deviceId(self, value: str):
        self._set_value("SYSTEM_OPTIONS.DEVICE_ID", value)

    # OTA_VERSION_URL
    def _get_otaUrl(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL", "")

    def _set_otaUrl(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL", value)

    # WEBSOCKET_URL
    def _get_websocketUrl(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL", "")

    def _set_websocketUrl(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL", value)

    # WEBSOCKET_ACCESS_TOKEN
    def _get_websocketToken(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN", "")

    def _set_websocketToken(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN", value)

    # AUTHORIZATION_URL
    def _get_authorizationUrl(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL", "")

    def _set_authorizationUrl(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL", value)

    # ACTIVATION_VERSION
    def _get_activationVersion(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION", "v1")

    def _set_activationVersion(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION", value)

    # WINDOW_SIZE_MODE
    def _get_windowSizeMode(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.WINDOW_SIZE_MODE", "default")

    def _set_windowSizeMode(self, value: str):
        self._set_value("SYSTEM_OPTIONS.WINDOW_SIZE_MODE", value)

    # 音乐配置
    def _get_musicSearchUrl(self) -> str:
        return self._get_value("MUSIC.SEARCH_URL", "")

    def _set_musicSearchUrl(self, value: str):
        self._set_value("MUSIC.SEARCH_URL", value)

    def _get_musicUrlApi(self) -> str:
        return self._get_value("MUSIC.URL_API", "")

    def _set_musicUrlApi(self, value: str):
        self._set_value("MUSIC.URL_API", value)

    def _get_musicUrlApiKey(self) -> str:
        return self._get_value("MUSIC.URL_API_KEY", "")

    def _set_musicUrlApiKey(self, value: str):
        self._set_value("MUSIC.URL_API_KEY", value)

    def _get_musicDefaultPlatform(self) -> str:
        return self._get_value("MUSIC.DEFAULT_PLATFORM", "kw")

    def _set_musicDefaultPlatform(self, value: str):
        self._set_value("MUSIC.DEFAULT_PLATFORM", value)

    def _get_musicDefaultQuality(self) -> str:
        return self._get_value("MUSIC.DEFAULT_QUALITY", "320k")

    def _set_musicDefaultQuality(self, value: str):
        self._set_value("MUSIC.DEFAULT_QUALITY", value)

    # MQTT 配置
    def _get_mqttEndpoint(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.endpoint", "")

    def _set_mqttEndpoint(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.endpoint", value)

    def _get_mqttClientId(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.client_id", "")

    def _set_mqttClientId(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.client_id", value)

    def _get_mqttUsername(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.username", "")

    def _set_mqttUsername(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.username", value)

    def _get_mqttPassword(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.password", "")

    def _set_mqttPassword(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.password", value)

    def _get_mqttPublishTopic(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.publish_topic", "")

    def _set_mqttPublishTopic(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.publish_topic", value)

    def _get_mqttSubscribeTopic(self) -> str:
        return self._get_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.subscribe_topic", "")

    def _set_mqttSubscribeTopic(self, value: str):
        self._set_value("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.subscribe_topic", value)

    # AEC 启用
    def _get_aecEnabled(self) -> bool:
        return self._get_value("AEC_OPTIONS.ENABLED", False)

    def _set_aecEnabled(self, value: bool):
        self._set_value("AEC_OPTIONS.ENABLED", value)

    # AEC 在位时 TTS 与音乐并行播放（闪避混音）
    def _get_aecMusicParallel(self) -> bool:
        return self._get_value("AEC_OPTIONS.MUSIC_PARALLEL", True)

    def _set_aecMusicParallel(self, value: bool):
        self._set_value("AEC_OPTIONS.MUSIC_PARALLEL", value)

    # 延迟补偿帧数（40ms + N × 协议帧长）
    def _get_aecFrameDelay(self) -> int:
        try:
            return int(self._get_value("AEC_OPTIONS.FRAME_DELAY", 3))
        except (TypeError, ValueError):
            return 3

    def _set_aecFrameDelay(self, value: int):
        self._set_value("AEC_OPTIONS.FRAME_DELAY", int(value))

    # 噪声抑制/高通预处理
    def _get_aecEnablePreprocess(self) -> bool:
        return self._get_value("AEC_OPTIONS.ENABLE_PREPROCESS", True)

    def _set_aecEnablePreprocess(self, value: bool):
        self._set_value("AEC_OPTIONS.ENABLE_PREPROCESS", value)

    # ========== 可写目录 PATHS（config 目录不由此改）==========

    def _get_pathCacheDir(self) -> str:
        return self._get_value("PATHS.CACHE_DIR", "") or ""

    def _set_pathCacheDir(self, value: str):
        self._set_value("PATHS.CACHE_DIR", value.strip() if value else "")

    def _get_pathLogDir(self) -> str:
        return self._get_value("PATHS.LOG_DIR", "") or ""

    def _set_pathLogDir(self, value: str):
        self._set_value("PATHS.LOG_DIR", value.strip() if value else "")

    def _get_pathMusicCacheDir(self) -> str:
        return self._get_value("PATHS.MUSIC_CACHE_DIR", "") or ""

    def _set_pathMusicCacheDir(self, value: str):
        self._set_value("PATHS.MUSIC_CACHE_DIR", value.strip() if value else "")

    def _get_pathKeywordsDir(self) -> str:
        return self._get_value("PATHS.KEYWORDS_DIR", "") or ""

    def _set_pathKeywordsDir(self, value: str):
        self._set_value("PATHS.KEYWORDS_DIR", value.strip() if value else "")

    def _get_pathMcpPluginsDir(self) -> str:
        return self._get_value("MCP_PLUGINS.DIR", "") or ""

    def _set_pathMcpPluginsDir(self, value: str):
        self._set_value("MCP_PLUGINS.DIR", value.strip() if value else "")

    def _default_data_paths(self) -> dict[str, str]:
        """配置留空时各目录的系统默认绝对路径（不含 PATHS 覆盖）."""
        from pathlib import Path

        from src.utils.resource_finder import get_user_data_dir

        data = get_user_data_dir()
        cache_custom = (self._get_pathCacheDir() or "").strip()
        cache_default = Path(cache_custom) if cache_custom else (data / "cache")
        return {
            "cache": str(data / "cache"),
            "log": str(data / "logs"),
            # 音乐默认挂在「当前缓存」下：自定义了缓存则跟随
            "music": str(cache_default / "music"),
            "keywords": str(data / "keywords"),
            "mcp": str(data / "mcp_plugins"),
        }

    def _get_pathDefaultCacheDir(self) -> str:
        try:
            return self._default_data_paths()["cache"]
        except Exception:
            return ""

    def _get_pathDefaultLogDir(self) -> str:
        try:
            return self._default_data_paths()["log"]
        except Exception:
            return ""

    def _get_pathDefaultMusicCacheDir(self) -> str:
        try:
            return self._default_data_paths()["music"]
        except Exception:
            return ""

    def _get_pathDefaultKeywordsDir(self) -> str:
        try:
            return self._default_data_paths()["keywords"]
        except Exception:
            return ""

    def _get_pathDefaultMcpPluginsDir(self) -> str:
        try:
            return self._default_data_paths()["mcp"]
        except Exception:
            return ""

    def _get_pathHints(self) -> str:
        """只读：数据根与操作提示（默认路径已显示在各输入框占位符）."""
        try:
            from src.utils.resource_finder import get_user_data_dir

            data = get_user_data_dir()
            return (
                f"数据根(配置固定在此): {data}\n"
                f"留空=默认；点「选择」用系统对话框；保存后下次启动迁移"
            )
        except Exception:
            return "留空使用默认路径；保存后下次启动迁移"

    def _browse_directory(self, title: str, current: str, which: str = "") -> str:
        """打开系统文件夹选择对话框；取消返回空串（调用方勿覆盖）."""
        from pathlib import Path

        from PySide6.QtWidgets import QApplication, QFileDialog

        start = current.strip() if current else ""
        if not start and which:
            try:
                start = self._default_data_paths().get(which, "")
            except Exception:
                start = ""
        if not start:
            try:
                from src.utils.resource_finder import get_user_data_dir

                start = str(get_user_data_dir())
            except Exception:
                start = str(Path.home())
        parent = QApplication.activeWindow()
        path = QFileDialog.getExistingDirectory(
            parent,
            title,
            start,
            QFileDialog.Option.ShowDirsOnly
            | QFileDialog.Option.DontResolveSymlinks,
        )
        return path or ""

