from pathlib import Path

import cv2
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger


class CameraWidget(QWidget):
    """
    摄像头设置组件.
    """

    # 信号定义
    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger(__name__)
        self.config_manager = ConfigManager.get_instance()

        # UI控件引用
        self.ui_controls = {}

        # 预览相关
        self.camera = None
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self._update_preview_frame)
        self.is_previewing = False

        # 初始化UI
        self._setup_ui()
        self._connect_events()
        self._load_config_values()

    def _setup_ui(self):
        """
        设置UI界面.
        """
        try:
            from PyQt5 import uic

            ui_path = Path(__file__).parent / "camera_widget.ui"
            uic.loadUi(str(ui_path), self)

            # 获取UI控件引用
            self._get_ui_controls()

        except Exception as e:
            self.logger.error(f"设置摄像头UI失败: {e}", exc_info=True)
            raise

    def _get_ui_controls(self):
        """
        获取UI控件引用.
        """
        self.ui_controls.update(
            {
                "camera_index_spin": self.findChild(QSpinBox, "camera_index_spin"),
                "frame_width_spin": self.findChild(QSpinBox, "frame_width_spin"),
                "frame_height_spin": self.findChild(QSpinBox, "frame_height_spin"),
                "fps_spin": self.findChild(QSpinBox, "fps_spin"),
                "local_vl_url_edit": self.findChild(QLineEdit, "local_vl_url_edit"),
                "vl_api_key_edit": self.findChild(QLineEdit, "vl_api_key_edit"),
                "models_edit": self.findChild(QLineEdit, "models_edit"),
                "scan_camera_btn": self.findChild(QPushButton, "scan_camera_btn"),
                # 预览相关控件
                "preview_label": self.findChild(QLabel, "preview_label"),
                "start_preview_btn": self.findChild(QPushButton, "start_preview_btn"),
                "stop_preview_btn": self.findChild(QPushButton, "stop_preview_btn"),
            }
        )

    def _connect_events(self):
        """
        连接事件处理.
        """
        # 为所有输入控件连接变更信号
        for control in self.ui_controls.values():
            if isinstance(control, QLineEdit):
                control.textChanged.connect(self.settings_changed.emit)
            elif isinstance(control, QSpinBox):
                if control == self.ui_controls.get("camera_index_spin"):
                    # 摄像头索引变化时，自动更新预览
                    control.valueChanged.connect(self._on_camera_index_changed)
                else:
                    control.valueChanged.connect(self.settings_changed.emit)
            elif isinstance(control, QPushButton):
                continue

        # 摄像头扫描按钮
        if self.ui_controls["scan_camera_btn"]:
            self.ui_controls["scan_camera_btn"].clicked.connect(self._on_scan_camera)

        # 预览控制按钮
        if self.ui_controls["start_preview_btn"]:
            self.ui_controls["start_preview_btn"].clicked.connect(self._start_preview)

        if self.ui_controls["stop_preview_btn"]:
            self.ui_controls["stop_preview_btn"].clicked.connect(self._stop_preview)

    def _load_config_values(self):
        """
        从配置文件加载值到UI控件.
        """
        try:
            # 摄像头配置
            camera_config = self.config_manager.get_config("CAMERA", {})
            self._set_spin_value(
                "camera_index_spin", camera_config.get("camera_index", 0)
            )
            self._set_spin_value(
                "frame_width_spin", camera_config.get("frame_width", 640)
            )
            self._set_spin_value(
                "frame_height_spin", camera_config.get("frame_height", 480)
            )
            self._set_spin_value("fps_spin", camera_config.get("fps", 30))
            self._set_text_value(
                "local_vl_url_edit", camera_config.get("Local_VL_url", "")
            )
            self._set_text_value("vl_api_key_edit", camera_config.get("VLapi_key", ""))
            self._set_text_value("models_edit", camera_config.get("models", ""))

        except Exception as e:
            self.logger.error(f"加载摄像头配置值失败: {e}", exc_info=True)

    def _set_text_value(self, control_name: str, value: str):
        """
        设置文本控件的值.
        """
        control = self.ui_controls.get(control_name)
        if control and hasattr(control, "setText"):
            control.setText(str(value) if value is not None else "")

    def _set_spin_value(self, control_name: str, value: int):
        """
        设置数字控件的值.
        """
        control = self.ui_controls.get(control_name)
        if control and hasattr(control, "setValue"):
            control.setValue(int(value) if value is not None else 0)

    def _get_text_value(self, control_name: str) -> str:
        """
        获取文本控件的值.
        """
        control = self.ui_controls.get(control_name)
        if control and hasattr(control, "text"):
            return control.text().strip()
        return ""

    def _get_spin_value(self, control_name: str) -> int:
        """
        获取数字控件的值.
        """
        control = self.ui_controls.get(control_name)
        if control and hasattr(control, "value"):
            return control.value()
        return 0

    def _on_scan_camera(self):
        """
        扫描摄像头按钮点击事件.
        """
        try:
            # 停止当前预览（避免占用摄像头）
            was_previewing = self.is_previewing
            if self.is_previewing:
                self._stop_preview()

            # 扫描可用摄像头
            available_cameras = self._scan_available_cameras()

            if not available_cameras:
                QMessageBox.information(
                    self,
                    "扫描结果",
                    "未检测到可用的摄像头设备。\n"
                    "请确保摄像头已连接并且没有被其他程序占用。",
                )
                return

            # 如果只有一个摄像头，直接使用
            if len(available_cameras) == 1:
                camera = available_cameras[0]
                self._apply_camera_settings(camera)
                QMessageBox.information(
                    self,
                    "设置完成",
                    f"检测到1个摄像头，已自动设置:\n"
                    f"索引: {camera[0]}, 分辨率: {camera[1]}x{camera[2]}",
                )
            else:
                # 多个摄像头时显示选择对话框
                selected_camera = self._show_camera_selection_dialog(available_cameras)
                if selected_camera:
                    self._apply_camera_settings(selected_camera)
                    QMessageBox.information(
                        self,
                        "设置完成",
                        f"已设置摄像头:\n"
                        f"索引: {selected_camera[0]}, 分辨率: {selected_camera[1]}x{selected_camera[2]}",
                    )

            # 恢复预览状态
            if was_previewing:
                QTimer.singleShot(500, self._start_preview)

        except Exception as e:
            self.logger.error(f"扫描摄像头失败: {e}", exc_info=True)
            QMessageBox.warning(self, "错误", f"扫描摄像头时发生错误: {str(e)}")

    def _scan_available_cameras(self, max_devices: int = 5):
        """
        扫描可用的摄像头设备.
        """
        available_cameras = []

        try:
            for i in range(max_devices):
                try:
                    # 尝试打开摄像头
                    cap = cv2.VideoCapture(i)

                    if cap.isOpened():
                        # 尝试读取一帧以验证摄像头工作
                        ret, _ = cap.read()
                        if ret:
                            # 获取默认分辨率
                            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            available_cameras.append((i, width, height))

                            self.logger.info(f"检测到摄像头 {i}: {width}x{height}")

                    cap.release()

                except Exception as e:
                    self.logger.debug(f"检测摄像头 {i} 时出错: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"扫描摄像头过程出错: {e}", exc_info=True)

        return available_cameras

    def _show_camera_selection_dialog(self, available_cameras):
        """
        显示摄像头选择对话框.
        """
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("选择摄像头")
            dialog.setFixedSize(400, 300)

            layout = QVBoxLayout(dialog)

            # 标题标签
            title_label = QLabel(
                f"检测到 {len(available_cameras)} 个可用摄像头，请选择一个:"
            )
            title_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
            layout.addWidget(title_label)

            # 摄像头列表
            camera_list = QListWidget()
            for idx, width, height in available_cameras:
                item_text = f"索引 {idx}: 分辨率 {width}x{height}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, (idx, width, height))  # 存储摄像头数据
                camera_list.addItem(item)

            # 默认选择第一个
            if camera_list.count() > 0:
                camera_list.setCurrentRow(0)

            layout.addWidget(camera_list)

            # 按钮
            button_box = QDialogButtonBox(
                QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal
            )
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)

            # 显示对话框
            if dialog.exec_() == QDialog.Accepted:
                current_item = camera_list.currentItem()
                if current_item:
                    return current_item.data(Qt.UserRole)

            return None

        except Exception as e:
            self.logger.error(f"显示摄像头选择对话框失败: {e}", exc_info=True)
            return None

    def _apply_camera_settings(self, camera_data):
        """
        应用摄像头设置.
        """
        try:
            idx, width, height = camera_data
            self._set_spin_value("camera_index_spin", idx)
            self._set_spin_value("frame_width_spin", width)
            self._set_spin_value("frame_height_spin", height)

            self.logger.info(f"应用摄像头设置: 索引{idx}, {width}x{height}")

        except Exception as e:
            self.logger.error(f"应用摄像头设置失败: {e}", exc_info=True)

    def get_config_data(self) -> dict:
        """
        获取当前配置数据.
        """
        config_data = {}

        try:
            # 摄像头配置
            camera_config = {}
            camera_config["camera_index"] = self._get_spin_value("camera_index_spin")
            camera_config["frame_width"] = self._get_spin_value("frame_width_spin")
            camera_config["frame_height"] = self._get_spin_value("frame_height_spin")
            camera_config["fps"] = self._get_spin_value("fps_spin")

            local_vl_url = self._get_text_value("local_vl_url_edit")
            if local_vl_url:
                camera_config["Local_VL_url"] = local_vl_url

            vl_api_key = self._get_text_value("vl_api_key_edit")
            if vl_api_key:
                camera_config["VLapi_key"] = vl_api_key

            models = self._get_text_value("models_edit")
            if models:
                camera_config["models"] = models

            # 获取现有的摄像头配置并更新
            existing_camera = self.config_manager.get_config("CAMERA", {})
            existing_camera.update(camera_config)
            config_data["CAMERA"] = existing_camera

        except Exception as e:
            self.logger.error(f"获取摄像头配置数据失败: {e}", exc_info=True)

        return config_data

    def reset_to_defaults(self):
        """
        重置为默认值.
        """
        try:
            # 获取默认配置
            default_config = ConfigManager.DEFAULT_CONFIG

            # 摄像头配置
            camera_config = default_config["CAMERA"]
            self._set_spin_value("camera_index_spin", camera_config["camera_index"])
            self._set_spin_value("frame_width_spin", camera_config["frame_width"])
            self._set_spin_value("frame_height_spin", camera_config["frame_height"])
            self._set_spin_value("fps_spin", camera_config["fps"])
            self._set_text_value("local_vl_url_edit", camera_config["Local_VL_url"])
            self._set_text_value("vl_api_key_edit", camera_config["VLapi_key"])
            self._set_text_value("models_edit", camera_config["models"])

            self.logger.info("摄像头配置已重置为默认值")

        except Exception as e:
            self.logger.error(f"重置摄像头配置失败: {e}", exc_info=True)

    def _on_camera_index_changed(self):
        """
        摄像头索引变化事件处理.
        """
        try:
            # 发出设置变更信号
            self.settings_changed.emit()

            # 如果当前正在预览，重启预览
            if self.is_previewing:
                self._restart_preview()

        except Exception as e:
            self.logger.error(f"处理摄像头索引变化失败: {e}", exc_info=True)

    def _start_preview(self):
        """
        开始预览摄像头.
        """
        try:
            if self.is_previewing:
                self._stop_preview()

            # 获取摄像头参数
            camera_index = self._get_spin_value("camera_index_spin")
            width = self._get_spin_value("frame_width_spin")
            height = self._get_spin_value("frame_height_spin")
            fps = self._get_spin_value("fps_spin")

            # 初始化摄像头
            self.camera = cv2.VideoCapture(camera_index)

            if not self.camera.isOpened():
                self._show_preview_error(f"无法打开摄像头索引 {camera_index}")
                return

            # 设置摄像头参数
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.camera.set(cv2.CAP_PROP_FPS, fps)

            # 验证摄像头是否能正常读取
            ret, _ = self.camera.read()
            if not ret:
                self._show_preview_error("摄像头无法读取画面")
                self.camera.release()
                self.camera = None
                return

            # 开始预览
            self.is_previewing = True
            self.preview_timer.start(max(1, int(1000 / fps)))

            # 更新按钮状态
            self._update_preview_buttons(True)

            self.logger.info(f"开始预览摄像头 {camera_index}")

        except Exception as e:
            self.logger.error(f"启动摄像头预览失败: {e}", exc_info=True)
            self._show_preview_error(f"启动预览时发生错误: {str(e)}")
            self._cleanup_camera()

    def _stop_preview(self):
        """
        停止预览摄像头.
        """
        try:
            if not self.is_previewing:
                return

            # 停止定时器
            self.preview_timer.stop()
            self.is_previewing = False

            # 释放摄像头
            self._cleanup_camera()

            # 清空预览显示
            if self.ui_controls["preview_label"]:
                self.ui_controls["preview_label"].setText(
                    "摄像头预览区域\n点击开始预览查看摄像头画面"
                )
                self.ui_controls["preview_label"].setPixmap(QPixmap())

            # 更新按钮状态
            self._update_preview_buttons(False)

            self.logger.info("停止摄像头预览")

        except Exception as e:
            self.logger.error(f"停止摄像头预览失败: {e}", exc_info=True)

    def _restart_preview(self):
        """
        重启预览（摄像头参数变更时调用）.
        """
        if self.is_previewing:
            self._stop_preview()
            # 稍微延迟后重启，确保摄像头资源释放
            QTimer.singleShot(100, self._start_preview)

    def _update_preview_frame(self):
        """
        更新预览帧.
        """
        try:
            if not self.camera or not self.camera.isOpened():
                return

            ret, frame = self.camera.read()
            if not ret:
                self._show_preview_error("无法读取摄像头画面")
                return

            # 转换颜色空间 BGR -> RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # 获取帧尺寸
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w

            # 转换为QImage
            qt_image = QImage(
                rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888
            )

            # 缩放到预览标签大小
            if self.ui_controls["preview_label"]:
                label_size = self.ui_controls["preview_label"].size()
                scaled_image = qt_image.scaled(
                    label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )

                # 转换为QPixmap并显示
                pixmap = QPixmap.fromImage(scaled_image)
                self.ui_controls["preview_label"].setPixmap(pixmap)

        except Exception as e:
            self.logger.error(f"更新预览帧失败: {e}", exc_info=True)
            self._show_preview_error(f"显示画面出错: {str(e)}")

    def _update_preview_buttons(self, is_previewing: bool):
        """
        更新预览按钮状态.
        """
        try:
            if self.ui_controls["start_preview_btn"]:
                self.ui_controls["start_preview_btn"].setEnabled(not is_previewing)

            if self.ui_controls["stop_preview_btn"]:
                self.ui_controls["stop_preview_btn"].setEnabled(is_previewing)

        except Exception as e:
            self.logger.error(f"更新预览按钮状态失败: {e}", exc_info=True)

    def _show_preview_error(self, message: str):
        """
        在预览区域显示错误信息.
        """
        try:
            if self.ui_controls["preview_label"]:
                self.ui_controls["preview_label"].setText(f"预览错误:\n{message}")
                self.ui_controls["preview_label"].setPixmap(QPixmap())
        except Exception as e:
            self.logger.error(f"显示预览错误失败: {e}", exc_info=True)

    def _cleanup_camera(self):
        """
        清理摄像头资源.
        """
        try:
            if self.camera:
                self.camera.release()
                self.camera = None
        except Exception as e:
            self.logger.error(f"清理摄像头资源失败: {e}", exc_info=True)

    def closeEvent(self, event):
        """
        组件关闭时清理资源.
        """
        try:
            self._stop_preview()
        except Exception as e:
            self.logger.error(f"关闭摄像头组件失败: {e}", exc_info=True)
        super().closeEvent(event)
