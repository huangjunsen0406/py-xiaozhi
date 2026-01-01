# -*- coding: utf-8 -*-
"""CLI模式设备激活流程."""

from datetime import datetime
from typing import Optional

from src.activation import ActivationService
from src.constants.system import SystemConstants
from src.logging import get_logger

logger = get_logger()


class CLIActivation:
    """CLI模式设备激活处理器."""

    def __init__(self, activation_service: Optional[ActivationService] = None):
        self.activation_service = activation_service
        self.is_activated = False
        self.logger = logger

    async def run_activation_process(self) -> bool:
        """运行完整的CLI激活流程.

        Returns:
            bool: 激活是否成功
        """
        try:
            self._print_header()

            # 获取或创建激活服务实例
            if not self.activation_service:
                self._log("正在初始化激活服务...")
                self.activation_service = await ActivationService.get_instance()

            # 运行初始化
            self._log("正在检查激活状态...")
            init_result = await self.activation_service.initialize()

            if not init_result.get("success", False):
                self._log(f"初始化失败: {init_result.get('error', '未知错误')}")
                return False

            # 显示设备信息
            self._print_device_info()

            # 检查是否需要激活
            if not init_result.get("need_activation_ui", False):
                self.is_activated = True
                self._log("设备已激活，无需进一步操作")
                self._print_success()
                return True

            # 执行激活流程
            return await self._run_activation()

        except KeyboardInterrupt:
            self._log("\n用户中断激活流程")
            return False
        except Exception as e:
            self.logger.error(f"CLI激活过程异常: {e}", exc_info=True)
            self._log(f"激活异常: {e}")
            return False

    async def _run_activation(self) -> bool:
        """执行激活流程."""
        activation_data = self.activation_service.get_activation_data()

        if not activation_data:
            self._log("未获取到激活数据，请检查网络连接")
            return False

        # 显示激活信息
        self._print_activation_info(activation_data)

        # 执行激活
        self._log("\n正在等待激活确认...")
        success = await self.activation_service.activate(activation_data)

        if success:
            self.is_activated = True
            self._print_success()
        else:
            self._print_failure()

        return success

    def _print_header(self):
        """打印头部信息."""
        print("\n" + "=" * 60)
        print(f"{SystemConstants.APP_DISPLAY_NAME} - 设备激活")
        print("=" * 60)

    def _print_device_info(self):
        """打印设备信息."""
        serial = self.activation_service.get_serial_number() or "--"
        mac = self.activation_service.get_mac_address() or "--"
        status = self.activation_service.get_activation_status()

        print("\n设备信息:")
        print(f"  序列号: {serial}")
        print(f"  MAC地址: {mac}")

        # 状态描述
        local = status.get("local_activated", False)
        server = status.get("server_activated", False)
        consistent = status.get("status_consistent", True)

        if not consistent:
            status_text = "需重新激活" if local and not server else "已自动修复"
        else:
            status_text = "已激活" if local else "未激活"

        print(f"  状态: {status_text}")

    def _print_activation_info(self, data: dict):
        """打印激活信息."""
        code = data.get("code", "------")
        message = data.get("message", "请访问 xiaozhi.me 输入验证码")

        print("\n" + "-" * 60)
        print("激活信息")
        print("-" * 60)
        print(f"验证码: {' '.join(code)}")
        print(f"说明: {message}")
        print("-" * 60)
        print("\n激活步骤:")
        print("  1. 打开浏览器访问 xiaozhi.me")
        print("  2. 登录您的账户")
        print("  3. 选择添加设备")
        print(f"  4. 输入验证码: {code}")
        print("  5. 确认添加设备")

    def _print_success(self):
        """打印激活成功信息."""
        print("\n" + "=" * 60)
        print("设备激活成功!")
        print("=" * 60)
        print("设备已成功添加到您的账户")
        print(f"正在启动{SystemConstants.APP_DISPLAY_NAME}...")
        print("=" * 60 + "\n")

    def _print_failure(self):
        """打印激活失败信息."""
        print("\n" + "=" * 60)
        print("设备激活失败")
        print("=" * 60)
        print("可能的原因:")
        print("  - 网络连接不稳定")
        print("  - 验证码输入错误或已过期")
        print("  - 服务器暂时不可用")
        print("\n解决方案:")
        print("  - 检查网络连接")
        print("  - 重新运行程序获取新验证码")
        print("  - 确保正确输入验证码")
        print("=" * 60 + "\n")

    def _log(self, message: str):
        """打印带时间戳的日志."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        self.logger.info(message)

    def get_activation_result(self) -> dict:
        """获取激活结果."""
        return {
            "is_activated": self.is_activated,
            "activation_service": self.activation_service,
            "config_manager": (
                self.activation_service.get_config_manager()
                if self.activation_service
                else None
            ),
        }
