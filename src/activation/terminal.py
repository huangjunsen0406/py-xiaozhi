"""终端模式设备激活流程。"""

from datetime import datetime

from src.constants.system import SystemConstants
from src.i18n import t
from src.logging import get_logger
from src.ui.shared.activation import BaseActivation

logger = get_logger()


class TerminalActivation(BaseActivation):
    """终端模式设备激活处理器。

    继承 BaseActivation，仅覆盖终端输出的展示方法；不依赖 Textual 或 Qt。
    """

    def __init__(self, activation_service, init_result: dict):
        super().__init__(activation_service, init_result)

    async def run(self) -> bool:
        self._print_header()

        if not self.needs_activation():
            self._log(t("activation.terminal.already_activated"))
            self._print_success()
            return True

        self._print_device_info()
        try:
            return await self._core_activate()
        except KeyboardInterrupt:
            self._log("\n" + t("activation.terminal.interrupted"))
            return False

    def _show_code(self, data: dict) -> None:
        self._print_activation_info(data)

    def _show_result(self, success: bool) -> None:
        if success:
            self._print_success()
        else:
            self._print_failure()

    def _show_error(self, msg: str) -> None:
        self._log(msg)

    def _print_header(self):
        print("\n" + "=" * 60)
        print(t("activation.terminal.header", app=SystemConstants.APP_DISPLAY_NAME))
        print("=" * 60)

    def _print_device_info(self):
        """打印设备信息。"""
        serial = self._service.get_serial_number() or "--"
        mac = self._service.get_mac_address() or "--"
        status = self._service.get_activation_status()

        print("\n" + t("activation.terminal.device_info"))
        print(t("activation.terminal.serial", serial=serial))
        print(t("activation.terminal.mac", mac=mac))

        local = status.get("local_activated", False)
        server = status.get("server_activated", False)
        consistent = status.get("status_consistent", True)

        if not consistent:
            status_key = (
                "activation.status.need_reactivate"
                if local and not server
                else "activation.status.auto_fixed"
            )
        else:
            status_key = (
                "activation.status.activated"
                if local
                else "activation.status.not_activated"
            )

        print(t("activation.terminal.status", status=t(status_key)))

    def _print_activation_info(self, data: dict):
        """打印激活信息。"""
        code = data.get("code", "------")
        message = data.get("message") or t("activation.terminal.default_message")

        print("\n" + "-" * 60)
        print(t("activation.terminal.info_title"))
        print("-" * 60)
        print(t("activation.terminal.code", code=" ".join(code)))
        print(t("activation.terminal.message", message=message))
        print("-" * 60)
        print("\n" + t("activation.terminal.steps_title"))
        print(t("activation.terminal.step1"))
        print(t("activation.terminal.step2"))
        print(t("activation.terminal.step3"))
        print(t("activation.terminal.step4", code=code))
        print(t("activation.terminal.step5"))

    def _print_success(self):
        print("\n" + "=" * 60)
        print(t("activation.terminal.success_title"))
        print("=" * 60)
        print(t("activation.terminal.success_desc"))
        print(t("activation.terminal.starting", app=SystemConstants.APP_DISPLAY_NAME))
        print("=" * 60 + "\n")

    def _print_failure(self):
        print("\n" + "=" * 60)
        print(t("activation.terminal.fail_title"))
        print("=" * 60)
        print(t("activation.terminal.fail_reasons"))
        print(t("activation.terminal.reason1"))
        print(t("activation.terminal.reason2"))
        print(t("activation.terminal.reason3"))
        print("\n" + t("activation.terminal.fail_solutions"))
        print(t("activation.terminal.solution1"))
        print(t("activation.terminal.solution2"))
        print(t("activation.terminal.solution3"))
        print("=" * 60 + "\n")

    def _log(self, message: str):
        """打印带时间戳的日志。"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        logger.info(message)
