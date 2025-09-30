import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QWidget,
)

from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger


class AudioWidget(QWidget):
    """
    音频设备设置组件.
    """

    # 信号定义
    settings_changed = pyqtSignal()
    status_message = pyqtSignal(str)
    reset_input_ui = pyqtSignal()
    reset_output_ui = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger(__name__)
        self.config_manager = ConfigManager.get_instance()

        # UI控件引用
        self.ui_controls = {}

        # 设备数据
        self.input_devices = []
        self.output_devices = []

        # 测试状态
        self.testing_input = False
        self.testing_output = False

        # 初始化UI
        self._setup_ui()
        self._connect_events()
        self._scan_devices()
        self._load_config_values()

        # 连接线程安全UI更新信号
        try:
            self.status_message.connect(self._on_status_message)
            self.reset_input_ui.connect(self._reset_input_test_ui)
            self.reset_output_ui.connect(self._reset_output_test_ui)
        except Exception:
            pass

    def _setup_ui(self):
        """
        设置UI界面.
        """
        try:
            from PyQt5 import uic

            ui_path = Path(__file__).parent / "audio_widget.ui"
            uic.loadUi(str(ui_path), self)

            # 获取UI控件引用
            self._get_ui_controls()

        except Exception as e:
            self.logger.error(f"设置音频UI失败: {e}", exc_info=True)
            raise

    def _get_ui_controls(self):
        """
        获取UI控件引用.
        """
        self.ui_controls.update(
            {
                "input_device_combo": self.findChild(QComboBox, "input_device_combo"),
                "output_device_combo": self.findChild(QComboBox, "output_device_combo"),
                "input_info_label": self.findChild(QLabel, "input_info_label"),
                "output_info_label": self.findChild(QLabel, "output_info_label"),
                "test_input_btn": self.findChild(QPushButton, "test_input_btn"),
                "test_output_btn": self.findChild(QPushButton, "test_output_btn"),
                "scan_devices_btn": self.findChild(QPushButton, "scan_devices_btn"),
                "status_text": self.findChild(QTextEdit, "status_text"),
            }
        )

    def _connect_events(self):
        """
        连接事件处理.
        """
        # 设备选择变更
        if self.ui_controls["input_device_combo"]:
            self.ui_controls["input_device_combo"].currentTextChanged.connect(
                self._on_input_device_changed
            )

        if self.ui_controls["output_device_combo"]:
            self.ui_controls["output_device_combo"].currentTextChanged.connect(
                self._on_output_device_changed
            )

        # 按钮点击
        if self.ui_controls["test_input_btn"]:
            self.ui_controls["test_input_btn"].clicked.connect(self._test_input_device)

        if self.ui_controls["test_output_btn"]:
            self.ui_controls["test_output_btn"].clicked.connect(
                self._test_output_device
            )

        if self.ui_controls["scan_devices_btn"]:
            self.ui_controls["scan_devices_btn"].clicked.connect(self._scan_devices)

    def _on_input_device_changed(self):
        """
        输入设备变更事件.
        """
        self.settings_changed.emit()
        self._update_device_info()

    def _on_output_device_changed(self):
        """
        输出设备变更事件.
        """
        self.settings_changed.emit()
        self._update_device_info()

    def _update_device_info(self):
        """
        更新设备信息显示.
        """
        try:
            # 更新输入设备信息
            input_device_id = self.ui_controls["input_device_combo"].currentData()
            if input_device_id is not None:
                input_device = next(
                    (d for d in self.input_devices if d["id"] == input_device_id), None
                )
                if input_device:
                    info_text = f"采样率: {int(input_device['sample_rate'])}Hz, 通道: {input_device['channels']}"
                    self.ui_controls["input_info_label"].setText(info_text)
                else:
                    self.ui_controls["input_info_label"].setText("设备信息获取失败")
            else:
                self.ui_controls["input_info_label"].setText("未选择设备")

            # 更新输出设备信息
            output_device_id = self.ui_controls["output_device_combo"].currentData()
            if output_device_id is not None:
                output_device = next(
                    (d for d in self.output_devices if d["id"] == output_device_id),
                    None,
                )
                if output_device:
                    info_text = f"采样率: {int(output_device['sample_rate'])}Hz, 通道: {output_device['channels']}"
                    self.ui_controls["output_info_label"].setText(info_text)
                else:
                    self.ui_controls["output_info_label"].setText("设备信息获取失败")
            else:
                self.ui_controls["output_info_label"].setText("未选择设备")

        except Exception as e:
            self.logger.error(f"更新设备信息失败: {e}", exc_info=True)

    def _scan_devices(self):
        """
        扫描音频设备.
        """
        try:
            self._append_status("正在扫描音频设备...")

            # 清空现有设备列表
            self.input_devices.clear()
            self.output_devices.clear()

            # 获取系统默认设备
            default_input = sd.default.device[0] if sd.default.device else None
            default_output = sd.default.device[1] if sd.default.device else None

            # 扫描所有设备
            devices = sd.query_devices()
            for i, dev_info in enumerate(devices):
                device_name = dev_info["name"]

                # 添加输入设备
                if dev_info["max_input_channels"] > 0:
                    default_mark = " (默认)" if i == default_input else ""
                    self.input_devices.append(
                        {
                            "id": i,
                            "name": device_name + default_mark,
                            "raw_name": device_name,
                            "channels": dev_info["max_input_channels"],
                            "sample_rate": dev_info["default_samplerate"],
                        }
                    )

                # 添加输出设备
                if dev_info["max_output_channels"] > 0:
                    default_mark = " (默认)" if i == default_output else ""
                    self.output_devices.append(
                        {
                            "id": i,
                            "name": device_name + default_mark,
                            "raw_name": device_name,
                            "channels": dev_info["max_output_channels"],
                            "sample_rate": dev_info["default_samplerate"],
                        }
                    )

            # 更新下拉框
            self._update_device_combos()

            # 自动选择默认设备
            self._select_default_devices()

            self._append_status(
                f"扫描完成: 找到 {len(self.input_devices)} 个输入设备, {len(self.output_devices)} 个输出设备"
            )

        except Exception as e:
            self.logger.error(f"扫描音频设备失败: {e}", exc_info=True)
            self._append_status(f"扫描设备失败: {str(e)}")

    def _update_device_combos(self):
        """
        更新设备下拉框.
        """
        try:
            # 保存当前选择
            current_input = self.ui_controls["input_device_combo"].currentData()
            current_output = self.ui_controls["output_device_combo"].currentData()

            # 清空并重新填充输入设备
            self.ui_controls["input_device_combo"].clear()
            for device in self.input_devices:
                self.ui_controls["input_device_combo"].addItem(
                    device["name"], device["id"]
                )

            # 清空并重新填充输出设备
            self.ui_controls["output_device_combo"].clear()
            for device in self.output_devices:
                self.ui_controls["output_device_combo"].addItem(
                    device["name"], device["id"]
                )

            # 尝试恢复之前的选择
            if current_input is not None:
                index = self.ui_controls["input_device_combo"].findData(current_input)
                if index >= 0:
                    self.ui_controls["input_device_combo"].setCurrentIndex(index)

            if current_output is not None:
                index = self.ui_controls["output_device_combo"].findData(current_output)
                if index >= 0:
                    self.ui_controls["output_device_combo"].setCurrentIndex(index)

        except Exception as e:
            self.logger.error(f"更新设备下拉框失败: {e}", exc_info=True)

    def _select_default_devices(self):
        """
        自动选择默认设备（与audio_codec.py的逻辑保持一致）。
        """
        try:
            # 优先选择配置中的设备，如果没有则选择系统默认设备
            config_input_id = self.config_manager.get_config(
                "AUDIO_DEVICES.input_device_id"
            )
            config_output_id = self.config_manager.get_config(
                "AUDIO_DEVICES.output_device_id"
            )

            # 选择输入设备
            if config_input_id is not None:
                # 使用配置中的设备
                index = self.ui_controls["input_device_combo"].findData(config_input_id)
                if index >= 0:
                    self.ui_controls["input_device_combo"].setCurrentIndex(index)
            else:
                # 自动选择默认输入设备（带"默认"标记的）
                for i in range(self.ui_controls["input_device_combo"].count()):
                    if "默认" in self.ui_controls["input_device_combo"].itemText(i):
                        self.ui_controls["input_device_combo"].setCurrentIndex(i)
                        break

            # 选择输出设备
            if config_output_id is not None:
                # 使用配置中的设备
                index = self.ui_controls["output_device_combo"].findData(
                    config_output_id
                )
                if index >= 0:
                    self.ui_controls["output_device_combo"].setCurrentIndex(index)
            else:
                # 自动选择默认输出设备（带"默认"标记的）
                for i in range(self.ui_controls["output_device_combo"].count()):
                    if "默认" in self.ui_controls["output_device_combo"].itemText(i):
                        self.ui_controls["output_device_combo"].setCurrentIndex(i)
                        break

            # 更新设备信息显示
            self._update_device_info()

        except Exception as e:
            self.logger.error(f"选择默认设备失败: {e}", exc_info=True)

    def _test_input_device(self):
        """
        测试输入设备.
        """
        if self.testing_input:
            return

        try:
            device_id = self.ui_controls["input_device_combo"].currentData()
            if device_id is None:
                QMessageBox.warning(self, "提示", "请先选择输入设备")
                return

            self.testing_input = True
            self.ui_controls["test_input_btn"].setEnabled(False)
            self.ui_controls["test_input_btn"].setText("录音中...")

            # 在线程中执行测试
            test_thread = threading.Thread(
                target=self._do_input_test, args=(device_id,)
            )
            test_thread.daemon = True
            test_thread.start()

        except Exception as e:
            self.logger.error(f"测试输入设备失败: {e}", exc_info=True)
            self._append_status(f"输入设备测试失败: {str(e)}")
            self._reset_input_test_ui()

    def _do_input_test(self, device_id):
        """
        执行输入设备测试.
        """
        try:
            # 获取设备信息和采样率
            input_device = next(
                (d for d in self.input_devices if d["id"] == device_id), None
            )
            if not input_device:
                self._append_status_threadsafe("错误: 无法获取设备信息")
                return

            sample_rate = int(input_device["sample_rate"])
            duration = 3  # 录音时长3秒

            self._append_status_threadsafe(
                f"开始录音测试 (设备: {device_id}, 采样率: {sample_rate}Hz)"
            )
            self._append_status_threadsafe("请对着麦克风说话，比如数数字: 1、2、3...")

            # 倒计时提示
            for i in range(3, 0, -1):
                self._append_status_threadsafe(f"{i}秒后开始录音...")
                time.sleep(1)

            self._append_status_threadsafe("正在录音，请说话... (3秒)")

            # 录音
            recording = sd.rec(
                int(duration * sample_rate),
                samplerate=sample_rate,
                channels=1,
                device=device_id,
                dtype=np.float32,
            )
            sd.wait()

            self._append_status_threadsafe("录音完成，正在分析...")

            # 分析录音质量
            max_amplitude = np.max(np.abs(recording))
            rms = np.sqrt(np.mean(recording**2))

            # 检测是否有语音活动
            frame_length = int(0.1 * sample_rate)  # 100ms帧
            frames = []
            for i in range(0, len(recording) - frame_length, frame_length):
                frame_rms = np.sqrt(np.mean(recording[i : i + frame_length] ** 2))
                frames.append(frame_rms)

            active_frames = sum(1 for f in frames if f > 0.01)  # 活跃帧数
            activity_ratio = active_frames / len(frames) if frames else 0

            # 测试结果分析
            if max_amplitude < 0.001:
                self._append_status_threadsafe("[失败] 未检测到音频信号")
                self._append_status_threadsafe(
                    "请检查: 1) 麦克风连接 2) 系统音量 3) 麦克风权限"
                )
            elif max_amplitude > 0.8:
                self._append_status_threadsafe("[警告] 音频信号过载")
                self._append_status_threadsafe("建议降低麦克风增益或音量设置")
            elif activity_ratio < 0.1:
                self._append_status_threadsafe("[警告] 检测到音频但语音活动较少")
                self._append_status_threadsafe(
                    "请确保对着麦克风说话，或检查麦克风灵敏度"
                )
            else:
                self._append_status_threadsafe("[成功] 录音测试通过")
                self._append_status_threadsafe(
                    f"音质数据: 最大音量={max_amplitude:.1%}, 平均音量={rms:.1%}, 活跃度={activity_ratio:.1%}"
                )
                self._append_status_threadsafe("麦克风工作正常")

        except Exception as e:
            self.logger.error(f"录音测试失败: {e}", exc_info=True)
            self._append_status_threadsafe(f"[错误] 录音测试失败: {str(e)}")
            if "Permission denied" in str(e) or "access" in str(e).lower():
                self._append_status_threadsafe(
                    "可能是权限问题，请检查系统麦克风权限设置"
                )
        finally:
            # 重置UI状态（切回主线程）
            self._reset_input_ui_threadsafe()

    def _test_output_device(self):
        """
        测试输出设备.
        """
        if self.testing_output:
            return

        try:
            device_id = self.ui_controls["output_device_combo"].currentData()
            if device_id is None:
                QMessageBox.warning(self, "提示", "请先选择输出设备")
                return

            self.testing_output = True
            self.ui_controls["test_output_btn"].setEnabled(False)
            self.ui_controls["test_output_btn"].setText("播放中...")

            # 在线程中执行测试
            test_thread = threading.Thread(
                target=self._do_output_test, args=(device_id,)
            )
            test_thread.daemon = True
            test_thread.start()

        except Exception as e:
            self.logger.error(f"测试输出设备失败: {e}", exc_info=True)
            self._append_status(f"输出设备测试失败: {str(e)}")
            self._reset_output_test_ui()

    def _do_output_test(self, device_id):
        """
        执行输出设备测试.
        """
        try:
            # 获取设备信息和采样率
            output_device = next(
                (d for d in self.output_devices if d["id"] == device_id), None
            )
            if not output_device:
                self._append_status_threadsafe("错误: 无法获取设备信息")
                return

            sample_rate = int(output_device["sample_rate"])
            duration = 2.0  # 播放时长
            frequency = 440  # 440Hz A音

            self._append_status_threadsafe(
                f"开始播放测试 (设备: {device_id}, 采样率: {sample_rate}Hz)"
            )
            self._append_status_threadsafe("请准备好耳机/扬声器，即将播放测试音...")

            # 倒计时提示
            for i in range(3, 0, -1):
                self._append_status_threadsafe(f"{i}秒后开始播放...")
                time.sleep(1)

            self._append_status_threadsafe(
                f"正在播放 {frequency}Hz 测试音 ({duration}秒)..."
            )

            # 生成测试音频 (正弦波)
            t = np.linspace(0, duration, int(sample_rate * duration))
            # 添加淡入淡出效果，避免爆音
            fade_samples = int(0.1 * sample_rate)  # 0.1秒淡入淡出
            audio = 0.3 * np.sin(2 * np.pi * frequency * t)

            # 应用淡入淡出
            audio[:fade_samples] *= np.linspace(0, 1, fade_samples)
            audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)

            # 播放音频
            sd.play(audio, samplerate=sample_rate, device=device_id)
            sd.wait()

            self._append_status_threadsafe("播放完成")
            self._append_status_threadsafe(
                "测试说明: 如果听到清晰的测试音，说明扬声器/耳机工作正常"
            )
            self._append_status_threadsafe(
                "如果没听到声音，请检查音量设置或选择其他输出设备"
            )

        except Exception as e:
            self.logger.error(f"播放测试失败: {e}", exc_info=True)
            self._append_status_threadsafe(f"[错误] 播放测试失败: {str(e)}")
        finally:
            # 重置UI状态（切回主线程）
            self._reset_output_ui_threadsafe()

    def _reset_input_test_ui(self):
        """
        重置输入测试UI状态.
        """
        self.testing_input = False
        self.ui_controls["test_input_btn"].setEnabled(True)
        self.ui_controls["test_input_btn"].setText("测试录音")

    def _reset_input_ui_threadsafe(self):
        try:
            self.reset_input_ui.emit()
        except Exception as e:
            self.logger.error(f"线程安全重置输入测试UI失败: {e}")

    def _reset_output_test_ui(self):
        """
        重置输出测试UI状态.
        """
        self.testing_output = False
        self.ui_controls["test_output_btn"].setEnabled(True)
        self.ui_controls["test_output_btn"].setText("测试播放")

    def _reset_output_ui_threadsafe(self):
        try:
            self.reset_output_ui.emit()
        except Exception as e:
            self.logger.error(f"线程安全重置输出测试UI失败: {e}")

    def _append_status(self, message):
        """
        添加状态信息.
        """
        try:
            if self.ui_controls["status_text"]:
                current_time = time.strftime("%H:%M:%S")
                formatted_message = f"[{current_time}] {message}"
                self.ui_controls["status_text"].append(formatted_message)
                # 滚动到底部
                self.ui_controls["status_text"].verticalScrollBar().setValue(
                    self.ui_controls["status_text"].verticalScrollBar().maximum()
                )
        except Exception as e:
            self.logger.error(f"添加状态信息失败: {e}", exc_info=True)

    def _append_status_threadsafe(self, message):
        """
        后台线程安全地将状态文本追加到 QTextEdit（通过信号切回主线程）。
        """
        try:
            if not self.ui_controls.get("status_text"):
                return
            current_time = time.strftime("%H:%M:%S")
            formatted_message = f"[{current_time}] {message}"
            self.status_message.emit(formatted_message)
        except Exception as e:
            self.logger.error(f"线程安全追加状态失败: {e}", exc_info=True)

    def _on_status_message(self, formatted_message: str):
        try:
            if not self.ui_controls.get("status_text"):
                return
            self.ui_controls["status_text"].append(formatted_message)
            # 滚动到底部
            self.ui_controls["status_text"].verticalScrollBar().setValue(
                self.ui_controls["status_text"].verticalScrollBar().maximum()
            )
        except Exception as e:
            self.logger.error(f"状态文本追加失败: {e}")

    def _load_config_values(self):
        """
        从配置文件加载值到UI控件.
        """
        try:
            # 获取音频设备配置
            audio_config = self.config_manager.get_config("AUDIO_DEVICES", {})

            # 设置输入设备
            input_device_id = audio_config.get("input_device_id")
            if input_device_id is not None:
                index = self.ui_controls["input_device_combo"].findData(input_device_id)
                if index >= 0:
                    self.ui_controls["input_device_combo"].setCurrentIndex(index)

            # 设置输出设备
            output_device_id = audio_config.get("output_device_id")
            if output_device_id is not None:
                index = self.ui_controls["output_device_combo"].findData(
                    output_device_id
                )
                if index >= 0:
                    self.ui_controls["output_device_combo"].setCurrentIndex(index)

            # 设备信息在设备选择变更时自动更新，无需手动设置

        except Exception as e:
            self.logger.error(f"加载音频设备配置值失败: {e}", exc_info=True)

    def get_config_data(self) -> dict:
        """
        获取当前配置数据.
        """
        config_data = {}

        try:
            audio_config = {}

            # 输入设备配置
            input_device_id = self.ui_controls["input_device_combo"].currentData()
            if input_device_id is not None:
                audio_config["input_device_id"] = input_device_id
                audio_config["input_device_name"] = self.ui_controls[
                    "input_device_combo"
                ].currentText()

            # 输出设备配置
            output_device_id = self.ui_controls["output_device_combo"].currentData()
            if output_device_id is not None:
                audio_config["output_device_id"] = output_device_id
                audio_config["output_device_name"] = self.ui_controls[
                    "output_device_combo"
                ].currentText()

            # 设备的采样率信息由设备自动确定，不需要用户配置
            # 保存设备的默认采样率用于后续使用
            input_device = next(
                (d for d in self.input_devices if d["id"] == input_device_id), None
            )
            if input_device:
                audio_config["input_sample_rate"] = int(input_device["sample_rate"])

            output_device = next(
                (d for d in self.output_devices if d["id"] == output_device_id), None
            )
            if output_device:
                audio_config["output_sample_rate"] = int(output_device["sample_rate"])

            if audio_config:
                config_data["AUDIO_DEVICES"] = audio_config

        except Exception as e:
            self.logger.error(f"获取音频设备配置数据失败: {e}", exc_info=True)

        return config_data

    def reset_to_defaults(self):
        """
        重置为默认值.
        """
        try:
            # 重新扫描设备
            self._scan_devices()

            # 设备扫描后采样率信息会自动显示，无需手动设置

            # 清空状态显示
            if self.ui_controls["status_text"]:
                self.ui_controls["status_text"].clear()

            self._append_status("已重置为默认设置")
            self.logger.info("音频设备配置已重置为默认值")

        except Exception as e:
            self.logger.error(f"重置音频设备配置失败: {e}", exc_info=True)
