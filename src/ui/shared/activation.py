"""激活 UI 基类.

共享「取码 → 展示 → service.activate → 结果」流程；子类只做展示。
"""


class BaseActivation:
    """激活 UI 基类（非 ABC，避免与 PySide6 QObject 元类冲突）.

    Args:
        activation_service: ActivationService 实例（由 create() 得到，非单例）
        init_result: handle_activation 传入的 initialize() 结果，避免重复 initialize
    """

    def __init__(self, activation_service=None, init_result=None):
        # 参数可选：PySide6 多重继承时 QObject.__init__ 的 super 链可能无参调用
        self._service = activation_service
        self._init_result = init_result

    def needs_activation(self) -> bool:
        """是否需要激活 UI 流程."""
        if self._init_result is None:
            return False
        return bool(self._init_result.get("need_activation_ui", False))

    async def _core_activate(self) -> bool:
        """核心激活：取码 → UI 展示 → service.activate（含剪贴板/播报副作用）."""
        if self._service is None:
            self._show_error("激活服务未初始化")
            return False

        data = self._service.get_activation_data()
        if not data:
            self._show_error("未获取到激活数据")
            return False

        self._show_code(data)
        success = await self._service.activate(data)
        self._show_result(success)
        return success

    async def run(self) -> bool:
        """运行激活流程."""
        raise NotImplementedError

    def _show_code(self, data: dict) -> None:
        """展示激活验证码（CLI 打印 / GUI 写 Model）."""
        raise NotImplementedError

    def _show_result(self, success: bool) -> None:
        """展示激活结果."""
        raise NotImplementedError

    def _show_error(self, msg: str) -> None:
        """展示错误（可选覆盖）."""
        pass
