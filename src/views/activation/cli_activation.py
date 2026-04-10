# -*- coding: utf-8 -*-
"""
CLI模式设备激活流程 提供与GUI激活窗口相同的功能，但使用纯终端输出.
"""

from datetime import datetime
from typing import Optional

from PyQt5.QtCore import QCoreApplication

from src.core.system_initializer import SystemInitializer
from src.utils.device_activator import DeviceActivator
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class CLIActivation:
    """
    CLI模式设备激活处理器.
    """

    def __init__(self, system_initializer: Optional[SystemInitializer] = None):
        # 组件实例
        self.system_initializer = system_initializer
        self.device_activator: Optional[DeviceActivator] = None

        # 状态管理
        self.current_stage = None
        self.activation_data = None
        self.is_activated = False

        self.logger = logger

    async def run_activation_process(self) -> bool:
        """运行完整的CLI激活流程.

        Returns:
            bool: 激活是否成功
        """
        try:
            self._print_header()

            # 如果已经提供了SystemInitializer实例，直接使用
            if self.system_initializer:
                self._log_and_print("使用已初始化的系统")
                self._update_device_info()
                return await self._start_activation_process()
            else:
                # 否则创建新的实例并运行初始化
                self._log_and_print("开始系统初始化流程")
                self.system_initializer = SystemInitializer()

                # 运行初始化流程
                init_result = await self.system_initializer.run_initialization()

                if init_result.get("success", False):
                    self._update_device_info()

                    # 显示状态消息
                    status_message = init_result.get("status_message", "")
                    if status_message:
                        self._log_and_print(status_message)

                    # 检查是否需要激活
                    if init_result.get("need_activation_ui", True):
                        return await self._start_activation_process()
                    else:
                        # 无需激活，直接完成
                        self.is_activated = True
                        self._log_and_print("设备已激活，无需进一步操作")
                        return True
                else:
                    error_msg = init_result.get("error", "初始化失败")
                    self._log_and_print(f"错误: {error_msg}")
                    return False

        except KeyboardInterrupt:
            self._log_and_print("\n用户中断激活流程")
            return False
        except Exception as e:
            self.logger.error(f"CLI激活过程异常: {e}", exc_info=True)
            self._log_and_print(f"激活异常: {e}")
            return False

    def _print_header(self):
        """
        打印CLI激活流程头部信息.
        """
        print("\n" + "=" * 60)
        print(
            QCoreApplication.translate("CLIActivation", "小智AI客户端 - 设备激活流程")
        )
        print("=" * 60)
        print(QCoreApplication.translate("CLIActivation", "正在初始化设备，请稍候..."))
        print()

    def _update_device_info(self):
        """
        更新设备信息显示.
        """
        if (
            not self.system_initializer
            or not self.system_initializer.device_fingerprint
        ):
            return

        device_fp = self.system_initializer.device_fingerprint

        # 获取设备信息
        serial_number = device_fp.get_serial_number()
        mac_address = device_fp.get_mac_address_from_efuse()

        # 获取激活状态
        activation_status = self.system_initializer.get_activation_status()
        local_activated = activation_status.get("local_activated", False)
        server_activated = activation_status.get("server_activated", False)
        status_consistent = activation_status.get("status_consistent", True)

        # 更新激活状态
        self.is_activated = local_activated

        # 显示设备信息
        print(QCoreApplication.translate("CLIActivation", "📱 设备信息:"))
        print(
            QCoreApplication.translate("CLIActivation", "   序列号: ")
            + (serial_number if serial_number else "--")
        )
        print(
            QCoreApplication.translate("CLIActivation", "   MAC地址: ")
            + (mac_address if mac_address else "--")
        )

        # 显示激活状态
        if not status_consistent:
            if local_activated and not server_activated:
                status_text = QCoreApplication.translate(
                    "CLIActivation", "状态不一致(需重新激活)"
                )
            else:
                status_text = QCoreApplication.translate(
                    "CLIActivation", "状态不一致(已自动修复)"
                )
        else:
            status_text = (
                QCoreApplication.translate("CLIActivation", "已激活")
                if local_activated
                else QCoreApplication.translate("CLIActivation", "未激活")
            )

        print(
            QCoreApplication.translate("CLIActivation", "   激活状态: ") + status_text
        )

    async def _start_activation_process(self) -> bool:
        """
        开始激活流程.
        """
        try:
            # 获取激活数据
            activation_data = self.system_initializer.get_activation_data()

            if not activation_data:
                self._log_and_print("\n未获取到激活数据")
                print(
                    QCoreApplication.translate(
                        "CLIActivation", "错误: 未获取到激活数据，请检查网络连接"
                    )
                )
                return False

            self.activation_data = activation_data

            # 显示激活信息
            self._show_activation_info(activation_data)

            # 初始化设备激活器
            config_manager = self.system_initializer.get_config_manager()
            self.device_activator = DeviceActivator(config_manager)

            # 开始激活流程
            self._log_and_print("\n开始设备激活流程...")
            print(
                QCoreApplication.translate(
                    "CLIActivation", "正在连接激活服务器，请保持网络连接..."
                )
            )

            activation_success = await self.device_activator.process_activation(
                activation_data
            )

            if activation_success:
                self._log_and_print("\n设备激活成功！")
                self._print_activation_success()
                return True
            else:
                self._log_and_print("\n设备激活失败")
                self._print_activation_failure()
                return False

        except Exception as e:
            self.logger.error(f"激活流程异常: {e}", exc_info=True)
            self._log_and_print(f"\n激活异常: {e}")
            return False

    def _show_activation_info(self, activation_data: dict):
        """
        显示激活信息.
        """
        code = activation_data.get("code", "------")
        message = activation_data.get("message", "请访问xiaozhi.me输入验证码")

        print("\n" + "=" * 60)
        print(QCoreApplication.translate("CLIActivation", "设备激活信息"))
        print("=" * 60)
        print(QCoreApplication.translate("CLIActivation", "激活验证码: ") + code)
        print(QCoreApplication.translate("CLIActivation", "激活说明: ") + message)
        print("=" * 60)

        # 格式化显示验证码（每个字符间加空格）
        formatted_code = " ".join(code)
        print(
            QCoreApplication.translate("CLIActivation", "\n验证码（请在网站输入）: ")
            + formatted_code
        )
        print(QCoreApplication.translate("CLIActivation", "\n请按以下步骤完成激活:"))
        print(
            QCoreApplication.translate("CLIActivation", "1. 打开浏览器访问 xiaozhi.me")
        )
        print(QCoreApplication.translate("CLIActivation", "2. 登录您的账户"))
        print(QCoreApplication.translate("CLIActivation", "3. 选择添加设备"))
        print(
            QCoreApplication.translate("CLIActivation", "4. 输入验证码: ")
            + formatted_code
        )
        print(QCoreApplication.translate("CLIActivation", "5. 确认添加设备"))
        print(
            QCoreApplication.translate(
                "CLIActivation", "\n等待激活确认中，请在网站完成操作..."
            )
        )

        self._log_and_print(f"激活验证码: {code}")
        self._log_and_print(f"激活说明: {message}")

    def _print_activation_success(self):
        """
        打印激活成功信息.
        """
        print("\n" + "=" * 60)
        print(QCoreApplication.translate("CLIActivation", "设备激活成功！"))
        print("=" * 60)
        print(QCoreApplication.translate("CLIActivation", "设备已成功添加到您的账户"))
        print(QCoreApplication.translate("CLIActivation", "配置已自动更新"))
        print(QCoreApplication.translate("CLIActivation", "准备启动小智AI客户端..."))
        print("=" * 60)

    def _print_activation_failure(self):
        """
        打印激活失败信息.
        """
        print("\n" + "=" * 60)
        print(QCoreApplication.translate("CLIActivation", "设备激活失败"))
        print("=" * 60)
        print(QCoreApplication.translate("CLIActivation", "可能的原因:"))
        print(QCoreApplication.translate("CLIActivation", "• 网络连接不稳定"))
        print(QCoreApplication.translate("CLIActivation", "• 验证码输入错误或已过期"))
        print(QCoreApplication.translate("CLIActivation", "• 服务器暂时不可用"))
        print(QCoreApplication.translate("CLIActivation", "\n解决方案:"))
        print(QCoreApplication.translate("CLIActivation", "• 检查网络连接"))
        print(QCoreApplication.translate("CLIActivation", "• 重新运行程序获取新验证码"))
        print(QCoreApplication.translate("CLIActivation", "• 确保在网站正确输入验证码"))
        print("=" * 60)

    def _log_and_print(self, message: str):
        """
        同时记录日志和打印到终端.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        print(log_message)
        self.logger.info(message)

    def get_activation_result(self) -> dict:
        """
        获取激活结果.
        """
        device_fingerprint = None
        config_manager = None

        if self.system_initializer:
            device_fingerprint = self.system_initializer.device_fingerprint
            config_manager = self.system_initializer.config_manager

        return {
            "is_activated": self.is_activated,
            "device_fingerprint": device_fingerprint,
            "config_manager": config_manager,
        }
