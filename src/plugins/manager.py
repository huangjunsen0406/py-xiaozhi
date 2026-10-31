"""按固定装配顺序协调内置插件生命周期。"""

from typing import TYPE_CHECKING

from src.logging import get_logger

from .base import Plugin

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext

logger = get_logger()


class PluginManager:
    """按注册顺序 setup/start，逆序 stop，并隔离和传播依赖失败。"""

    def __init__(self) -> None:
        self._plugins: list[Plugin] = []
        self._by_name: dict[str, Plugin] = {}

    def register(self, *plugins: Plugin) -> None:
        """按传入顺序注册插件；名称冲突时整批不生效。"""
        by_name = dict(self._by_name)
        for p in plugins:
            name = getattr(p, "name", None)
            if isinstance(name, str) and name:
                existing = by_name.get(name)
                if existing is not None and existing is not p:
                    raise ValueError(f"插件名称重复: {name}")
                by_name[name] = p

        for p in plugins:
            if p not in self._plugins:
                self._plugins.append(p)
        self._by_name = by_name

    @property
    def plugins(self) -> tuple[Plugin, ...]:
        return tuple(self._plugins)

    def get_plugin(self, name: str) -> Plugin | None:
        """根据插件名获取插件实例。"""
        return self._by_name.get(name)

    def is_failed(self, name: str) -> bool:
        """插件是否失败（未注册视为失败）。"""
        plugin = self._by_name.get(name)
        return plugin is None or plugin.failed

    def failed_plugins(self) -> list[str]:
        """返回所有已失败插件名。"""
        return [p.name for p in self._plugins if getattr(p, "name", None) and p.failed]

    def _validate_dependencies(self) -> None:
        """依赖必须已注册且位于使用者之前；不调整装配顺序。"""
        seen: set[str] = set()
        for plugin in self._plugins:
            for dependency in plugin.requires:
                if dependency not in self._by_name:
                    raise ValueError(f"内置组件 {plugin.name} 依赖 {dependency} 未注册")
                if dependency not in seen:
                    raise ValueError(
                        f"内置组件依赖顺序无效: {plugin.name} 依赖 {dependency}"
                    )
            seen.add(plugin.name)

    def _dependencies_ok(self, plugin: Plugin) -> bool:
        """检查依赖在此前的生命周期调用中是否失败。"""
        for dep_name in plugin.requires:
            if self.is_failed(dep_name):
                logger.warning(f"插件 {plugin.name} 依赖 {dep_name} 不可用，跳过")
                return False
        return True

    async def setup_all(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        """先校验整批装配，再依次 setup；失败沿 requires 传播。"""
        try:
            self._validate_dependencies()
        except ValueError:
            # 装配无效时禁止后续 start，但 stop 仍会尝试清理每个组件。
            for plugin in self._plugins:
                plugin.mark_failed()
            raise

        for p in self._plugins:
            if p.failed:
                continue
            if not self._dependencies_ok(p):
                p.mark_failed()
                logger.error(f"插件 {p.name} 因依赖失败被跳过 setup")
                continue
            try:
                await p.setup(ctx, cmd)
            except Exception as e:
                p.mark_failed()
                logger.error(f"插件 {p.name} setup 失败: {e}", exc_info=True)

    async def start_all(self) -> None:
        """按注册顺序启动未失败插件，失败沿 requires 传播。"""
        for p in self._plugins:
            if p.failed:
                continue
            if not self._dependencies_ok(p):
                p.mark_failed()
                logger.error(f"插件 {p.name} 因依赖失败被跳过 start")
                continue
            try:
                await p.start()
            except Exception as e:
                p.mark_failed()
                logger.error(f"插件 {p.name} start 失败: {e}", exc_info=True)

    async def stop_all(self) -> None:
        """逆序停止所有插件，包括失败组件；清理异常不阻断后续清理。"""
        for p in reversed(self._plugins):
            try:
                await p.stop()
            except Exception as e:
                logger.error(f"插件 {p.name} stop 失败: {e}", exc_info=True)
