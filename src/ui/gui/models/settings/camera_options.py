"""摄像头参数与 VL 配置属性."""


class SettingsCameraOptionsMixin:
    # ========== 摄像头设置 ==========

    def _get_cameraIndex(self) -> int:
        return self._get_value("CAMERA.camera_index", 0)

    def _set_cameraIndex(self, value: int):
        self._set_value("CAMERA.camera_index", value)

    def _get_frameWidth(self) -> int:
        return self._get_value("CAMERA.frame_width", 640)

    def _set_frameWidth(self, value: int):
        self._set_value("CAMERA.frame_width", value)

    def _get_frameHeight(self) -> int:
        return self._get_value("CAMERA.frame_height", 480)

    def _set_frameHeight(self, value: int):
        self._set_value("CAMERA.frame_height", value)

    def _get_fps(self) -> int:
        return self._get_value("CAMERA.fps", 30)

    def _set_fps(self, value: int):
        self._set_value("CAMERA.fps", value)

    def _get_vlApiUrl(self) -> str:
        return self._get_value("CAMERA.Local_VL_url", "")

    def _set_vlApiUrl(self, value: str):
        self._set_value("CAMERA.Local_VL_url", value)

    def _get_vlApiKey(self) -> str:
        return self._get_value("CAMERA.VLapi_key", "")

    def _set_vlApiKey(self, value: str):
        self._set_value("CAMERA.VLapi_key", value)

    def _get_vlModels(self) -> str:
        return self._get_value("CAMERA.models", "glm-4v-plus")

    def _set_vlModels(self, value: str):
        self._set_value("CAMERA.models", value)

