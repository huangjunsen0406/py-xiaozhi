"""激活基类.

提取 GUI/CLI 激活的共享核心流程，子类仅覆盖展示方法。
"""


class BaseActivation:
    """激活基类（非 ABC，避免与 PySide6 QObject 元类冲突）.

    Args:
        activation_service: ActivationService 单例
        init_result: 由 handle_activation() 传入的 initialize() 结果，
                     避免子类重复调用 initialize()
    """

    def __init__(self, activation_service=None, init_result=None):
        # 参数设为可选：PySide6 多重继承时 QObject.__init__ 的 super() 链
        # 会无参调用本方法，实际值由子类显式传入覆盖
        self._service = activation_service
        self._init_result = init_result

    def needs_activation(self) -> bool:
        """是否需要激活 UI 流程."""
        if self._init_result is None:
            return False
        return self._init_result.get("need_activation_ui", False)

    async def _core_activate(self) -> bool:
        """核心激活流程 — 所有模式共享.

        获取激活数据 → 展示验证码 → 调用 activate() → 展示结果.
        """
        data = self._service.get_activation_data()
        if not data:
            self._show_error("未获取到激活数据")
            return False

        self._show_code(data)
        success = await self._service.activate(data)
        self._show_result(success)
        return success

    # ---- 子类覆盖 ----

    async def run(self) -> bool:
        """运行激活流程."""
        raise NotImplementedError

    def _show_code(self, data: dict) -> None:
        """展示激活验证码."""
        raise NotImplementedError

    def _show_result(self, success: bool) -> None:
        """展示激活结果."""
        raise NotImplementedError

    def _show_error(self, msg: str) -> None:
        """展示错误信息（可选覆盖）."""
        pass
