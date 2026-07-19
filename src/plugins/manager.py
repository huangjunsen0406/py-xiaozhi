"""插件管理器.

管理插件生命周期，支持依赖声明和拓扑排序。
"""

from typing import TYPE_CHECKING, Any, List, Optional

from src.logging import get_logger

from .base import Plugin

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext

logger = get_logger()


class PluginManager:
    """插件管理器.

    职责:
    - 按依赖关系拓扑排序
    - 自动注入插件依赖
    - 统一 setup/start/stop 广播
    - 错误隔离，单个插件失败不影响其他插件
    - 失败标记 + 依赖失败时跳过下游
    """

    def __init__(self) -> None:
        self._plugins: List[Plugin] = []
        self._by_name: dict[str, Plugin] = {}
        self._sorted: bool = False

    def register(self, *plugins: Plugin) -> None:
        """注册插件.

        先按 priority 排序，后续 setup_all 时会按依赖拓扑排序。
        """
        sorted_plugins = sorted(plugins, key=lambda p: getattr(p, "priority", 50))
        for p in sorted_plugins:
            if p not in self._plugins:
                self._plugins.append(p)
                try:
                    name = getattr(p, "name", None)
                    if isinstance(name, str) and name:
                        self._by_name[name] = p
                except Exception as e:
                    logger.error(f"插件注册失败: {e}", exc_info=True)
        self._sorted = False

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """根据插件名获取插件实例."""
        return self._by_name.get(name)

    def is_failed(self, name: str) -> bool:
        """插件是否失败（未注册视为失败）."""
        plugin = self._by_name.get(name)
        return plugin is None or plugin.failed

    def failed_plugins(self) -> List[str]:
        """返回所有已失败插件名."""
        return [
            p.name
            for p in self._plugins
            if getattr(p, "name", None) and p.failed
        ]

    def _dependencies_ok(self, plugin: Plugin) -> bool:
        """检查插件声明的依赖是否都可用（已注册且未失败）."""
        requires = getattr(plugin, "requires", []) or []
        for dep_name in requires:
            dep = self._by_name.get(dep_name)
            if dep is None:
                logger.warning(
                    f"插件 {getattr(plugin, 'name', 'unknown')} 依赖 {dep_name} 未注册"
                )
                return False
            if dep.failed:
                logger.warning(
                    f"插件 {getattr(plugin, 'name', 'unknown')} 依赖 {dep_name} 已失败，跳过"
                )
                return False
        return True

    def _active_plugins(self) -> List[Plugin]:
        """未失败的插件列表."""
        return [p for p in self._plugins if not p.failed]

    def _topological_sort(self) -> List[Plugin]:
        """拓扑排序插件列表，确保依赖先于被依赖者初始化.

        Returns:
            排序后的插件列表

        Raises:
            ValueError: 存在循环依赖
        """
        # 构建依赖图
        in_degree: dict[str, int] = {}
        dependents: dict[str, List[str]] = {}  # 被谁依赖

        for p in self._plugins:
            name = getattr(p, "name", "")
            if name:
                in_degree[name] = 0
                dependents[name] = []

        for p in self._plugins:
            name = getattr(p, "name", "")
            requires = getattr(p, "requires", []) or []
            for dep in requires:
                if dep in self._by_name:
                    in_degree[name] = in_degree.get(name, 0) + 1
                    dependents[dep].append(name)
                else:
                    logger.warning(f"插件 {name} 声明的依赖 {dep} 未注册，忽略")

        # Kahn 算法
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result: List[Plugin] = []

        while queue:
            # 从入度为0的节点中选择 priority 最小的
            queue.sort(
                key=lambda n: getattr(self._by_name.get(n), "priority", 50)
            )
            current = queue.pop(0)
            plugin = self._by_name.get(current)
            if plugin:
                result.append(plugin)

            for dependent in dependents.get(current, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len([p for p in self._plugins if getattr(p, "name", "")]):
            raise ValueError("插件存在循环依赖")

        # 添加没有 name 的插件到末尾
        unnamed = [p for p in self._plugins if not getattr(p, "name", "")]
        result.extend(unnamed)

        return result

    def _inject_dependencies(self) -> None:
        """为每个插件注入其声明的依赖."""
        for p in self._plugins:
            requires = getattr(p, "requires", []) or []
            for dep_name in requires:
                dep_plugin = self._by_name.get(dep_name)
                if dep_plugin:
                    p._inject_dependency(dep_name, dep_plugin)
                    logger.debug(f"注入依赖: {p.name} <- {dep_name}")

    async def setup_all(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        """初始化所有插件.

        按拓扑排序后的顺序初始化，自动注入依赖。
        setup 失败或依赖失败的插件会被 mark_failed 并跳过后续生命周期。

        Args:
            ctx: 插件上下文
            cmd: 插件命令接口
        """
        # 拓扑排序
        if not self._sorted:
            try:
                self._plugins = self._topological_sort()
                self._sorted = True
                logger.info(
                    f"插件拓扑排序完成: {[p.name for p in self._plugins if hasattr(p, 'name')]}"
                )
            except ValueError as e:
                logger.error(f"插件排序失败: {e}", exc_info=True)
                # 降级为优先级排序
                self._plugins.sort(key=lambda p: getattr(p, "priority", 50))

        # 注入依赖
        self._inject_dependencies()

        # 初始化
        for p in list(self._plugins):
            name = getattr(p, "name", "unknown")
            if p.failed:
                continue
            if not self._dependencies_ok(p):
                p.mark_failed()
                logger.error(f"插件 {name} 因依赖失败被跳过 setup")
                continue
            try:
                await p.setup(ctx, cmd)
            except Exception as e:
                p.mark_failed()
                logger.error(f"插件 {name} setup 失败: {e}", exc_info=True)

    async def start_all(self) -> None:
        """启动所有未失败的插件."""
        for p in list(self._plugins):
            if p.failed:
                continue
            if not self._dependencies_ok(p):
                p.mark_failed()
                logger.error(
                    f"插件 {getattr(p, 'name', 'unknown')} 因依赖失败被跳过 start"
                )
                continue
            try:
                await p.start()
            except Exception as e:
                p.mark_failed()
                logger.error(
                    f"插件 {getattr(p, 'name', 'unknown')} start 失败: {e}",
                    exc_info=True,
                )

    async def notify_protocol_connected(self, protocol: Any) -> None:
        """通知协议已连接."""
        for p in self._active_plugins():
            try:
                if p.on_protocol_connected:
                    await p.on_protocol_connected(protocol)
            except Exception as e:
                logger.error(
                    f"插件 {getattr(p, 'name', 'unknown')} on_protocol_connected 失败: {e}",
                    exc_info=True,
                )

    async def notify_incoming_json(self, message: Any) -> None:
        """通知收到 JSON 消息."""
        for p in self._active_plugins():
            try:
                await p.on_incoming_json(message)
            except Exception as e:
                logger.error(
                    f"插件 {getattr(p, 'name', 'unknown')} on_incoming_json 失败: {e}",
                    exc_info=True,
                )

    async def notify_incoming_audio(self, data: bytes) -> None:
        """通知收到音频数据."""
        for p in self._active_plugins():
            try:
                await p.on_incoming_audio(data)
            except Exception as e:
                logger.error(
                    f"插件 {getattr(p, 'name', 'unknown')} on_incoming_audio 失败: {e}",
                    exc_info=True,
                )

    async def notify_device_state_changed(self, state: Any) -> None:
        """通知设备状态变更."""
        for p in self._active_plugins():
            try:
                await p.on_device_state_changed(state)
            except Exception as e:
                logger.error(
                    f"插件 {getattr(p, 'name', 'unknown')} on_device_state_changed 失败: {e}",
                    exc_info=True,
                )

    async def stop_all(self) -> None:
        """停止所有插件（逆序；失败插件仍尝试 stop 以便清理）."""
        for p in reversed(self._plugins):
            try:
                await p.stop()
            except Exception as e:
                logger.error(
                    f"插件 {getattr(p, 'name', 'unknown')} stop 失败: {e}",
                    exc_info=True,
                )
