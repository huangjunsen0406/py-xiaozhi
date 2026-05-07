"""CLI模式设备激活流程."""

from datetime import datetime

from src.constants.system import SystemConstants
from src.logging import get_logger
from src.ui.shared.activation import BaseActivation

logger = get_logger()


class CLIActivation(BaseActivation):
    """CLI模式设备激活处理器.

    继承 BaseActivation，仅覆盖终端输出的展示方法。
    """

    def __init__(self, activation_service, init_result: dict):
        super().__init__(activation_service, init_result)

    async def run(self) -> bool:
        self._print_header()

        if not self.needs_activation():
            self._log("设备已激活，无需进一步操作")
            self._print_success()
            return True

        self._print_device_info()
        try:
            return await self._core_activate()
        except KeyboardInterrupt:
            self._log("\n用户中断激活流程")
            return False

    # ---- BaseActivation 展示方法 ----

    def _show_code(self, data: dict) -> None:
        self._print_activation_info(data)

    def _show_result(self, success: bool) -> None:
        if success:
            self._print_success()
        else:
            self._print_failure()

    def _show_error(self, msg: str) -> None:
        self._log(msg)

    # ---- 终端展示辅助方法 ----

    def _print_header(self):
        print("\n" + "=" * 60)
        print(f"{SystemConstants.APP_DISPLAY_NAME} - 设备激活")
        print("=" * 60)

    def _print_device_info(self):
        """打印设备信息."""
        serial = self._service.get_serial_number() or "--"
        mac = self._service.get_mac_address() or "--"
        status = self._service.get_activation_status()

        print("\n设备信息:")
        print(f"  序列号: {serial}")
        print(f"  MAC地址: {mac}")

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
        print("\n" + "=" * 60)
        print("设备激活成功!")
        print("=" * 60)
        print("设备已成功添加到您的账户")
        print(f"正在启动{SystemConstants.APP_DISPLAY_NAME}...")
        print("=" * 60 + "\n")

    def _print_failure(self):
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
        logger.info(message)
