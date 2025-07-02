# -*- coding: utf-8 -*-
"""
全局资源管理器 统一管理所有需要清理的资源，解决事件循环相关的问题.
"""

import asyncio
import time
import weakref
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class ResourceType(Enum):
    """
    资源类型枚举.
    """

    AUDIO_CODEC = "audio_codec"
    PROTOCOL = "protocol"
    WAKE_WORD_DETECTOR = "wake_word_detector"
    DISPLAY = "display"
    IOT_DEVICE = "iot_device"
    TASK = "task"
    SHORTCUT_MANAGER = "shortcut_manager"
    STREAM = "stream"
    OTHER = "other"


class ResourceState(Enum):
    """
    资源状态枚举.
    """

    ACTIVE = "active"
    CLEANING = "cleaning"
    CLEANED = "cleaned"
    FAILED = "failed"


@dataclass
class ManagedResource:
    """
    管理的资源.
    """

    resource: Any
    cleanup_func: Callable
    resource_type: ResourceType
    priority: int = 0  # 优先级，数字越大越先清理
    name: str = ""
    is_async: bool = True
    timeout: float = 1.0  # 清理超时时间
    state: ResourceState = field(default=ResourceState.ACTIVE)
    created_at: float = field(default_factory=time.time)
    dependencies: Set[str] = field(default_factory=set)  # 依赖的其他资源ID
    group: str = ""  # 资源分组


class ResourceManager:
    """
    全局资源管理器.
    """

    def __init__(self):
        """
        初始化资源管理器.
        """
        logger.debug("初始化ResourceManager实例")

        self._resources: Dict[str, ManagedResource] = {}
        self._resource_groups: Dict[str, Set[str]] = {}  # 分组管理
        self._cleanup_order: List[ResourceType] = [
            ResourceType.DISPLAY,  # 首先关闭显示界面
            ResourceType.TASK,  # 然后取消任务
            ResourceType.SHORTCUT_MANAGER,  # 关闭快捷键服务
            ResourceType.WAKE_WORD_DETECTOR,  # 停止唤醒词检测
            ResourceType.PROTOCOL,  # 关闭协议连接
            ResourceType.AUDIO_CODEC,  # 关闭音频设备
            ResourceType.IOT_DEVICE,  # 清理IoT设备
            ResourceType.STREAM,  # 关闭流
            ResourceType.OTHER,  # 其他资源
        ]
        self._is_shutting_down = False
        self._shutdown_event = asyncio.Event()
        self._lock = asyncio.Lock()  # 保护资源字典的并发访问
        self._cleanup_semaphore = asyncio.Semaphore(10)  # 限制并发清理数量

        # 性能统计
        self._stats = {
            "total_registered": 0,
            "total_cleaned": 0,
            "total_failed": 0,
            "avg_cleanup_time": 0.0,
        }

        logger.info("资源管理器初始化完成")

    def _is_event_loop_running(self) -> bool:
        """
        安全检查事件循环是否运行.
        """
        try:
            loop = asyncio.get_running_loop()
            return loop.is_running()
        except RuntimeError:
            return False

    async def register_resource(
        self,
        resource_id: str,
        resource: Any,
        cleanup_func: Callable,
        resource_type: ResourceType = ResourceType.OTHER,
        priority: int = 0,
        name: str = "",
        is_async: bool = True,
        timeout: float = 1.0,
        dependencies: Optional[Set[str]] = None,
        group: str = "",
    ) -> str:
        """注册资源.

        Args:
            resource_id: 资源ID，如果为空则自动生成
            resource: 资源对象
            cleanup_func: 清理函数
            resource_type: 资源类型
            priority: 优先级（同类型资源中，数字越大越先清理）
            name: 资源名称（用于日志）
            is_async: 清理函数是否为异步
            timeout: 清理超时时间
            dependencies: 依赖的其他资源ID集合
            group: 资源分组

        Returns:
            str: 资源ID
        """
        async with self._lock:
            if self._is_shutting_down:
                msg = f"正在关闭中，跳过注册资源: {resource_id or name}"
                logger.warning(msg)
                return resource_id

            if not resource_id:
                resource_id = f"{resource_type.value}_{id(resource)}"

            # 使用弱引用避免循环引用
            weak_resource = (
                weakref.ref(resource) if hasattr(resource, "__weakref__") else resource
            )

            managed_resource = ManagedResource(
                resource=weak_resource,
                cleanup_func=cleanup_func,
                resource_type=resource_type,
                priority=priority,
                name=name or resource_id,
                is_async=is_async,
                timeout=timeout,
                dependencies=dependencies or set(),
                group=group,
            )

            self._resources[resource_id] = managed_resource
            self._stats["total_registered"] += 1

            # 添加到分组
            if group:
                if group not in self._resource_groups:
                    self._resource_groups[group] = set()
                self._resource_groups[group].add(resource_id)

            resource_info = f"{managed_resource.name} ({resource_type.value})"
            logger.debug(f"注册资源: {resource_info}")
            return resource_id

    async def unregister_resource(self, resource_id: str) -> bool:
        """注销资源.

        Args:
            resource_id: 资源ID

        Returns:
            bool: 是否成功注销
        """
        async with self._lock:
            if resource_id in self._resources:
                resource = self._resources.pop(resource_id)

                # 从分组中移除
                if resource.group and resource.group in self._resource_groups:
                    self._resource_groups[resource.group].discard(resource_id)
                    if not self._resource_groups[resource.group]:
                        del self._resource_groups[resource.group]

                logger.debug(f"注销资源: {resource.name}")
                return True
            return False

    def get_resource(self, resource_id: str) -> Optional[Any]:
        """获取资源对象.

        Args:
            resource_id: 资源ID

        Returns:
            资源对象或None
        """
        if resource_id in self._resources:
            managed_resource = self._resources[resource_id]
            if isinstance(managed_resource.resource, weakref.ref):
                return managed_resource.resource()
            return managed_resource.resource
        return None

    def list_resources(
        self,
        resource_type: Optional[ResourceType] = None,
        group: Optional[str] = None,
        state: Optional[ResourceState] = None,
    ) -> List[str]:
        """列出资源.

        Args:
            resource_type: 资源类型过滤器
            group: 分组过滤器
            state: 状态过滤器

        Returns:
            资源ID列表
        """
        result = []
        for resource_id, resource in self._resources.items():
            # 类型过滤
            if resource_type is not None and resource.resource_type != resource_type:
                continue
            # 分组过滤
            if group is not None and resource.group != group:
                continue
            # 状态过滤
            if state is not None and resource.state != state:
                continue
            result.append(resource_id)
        return result

    async def health_check_resource(self, resource_id: str) -> bool:
        """检查资源健康状态.

        Args:
            resource_id: 资源ID

        Returns:
            bool: 资源是否健康
        """
        if resource_id not in self._resources:
            return False

        managed_resource = self._resources[resource_id]

        # 检查弱引用是否有效
        if isinstance(managed_resource.resource, weakref.ref):
            actual_resource = managed_resource.resource()
            if actual_resource is None:
                logger.debug(f"资源已被垃圾回收: {managed_resource.name}")
                await self.unregister_resource(resource_id)
                return False

        return managed_resource.state == ResourceState.ACTIVE

    async def cleanup_resource(self, resource_id: str) -> bool:
        """清理单个资源.

        Args:
            resource_id: 资源ID

        Returns:
            bool: 是否成功清理
        """
        if resource_id not in self._resources:
            logger.warning(f"资源不存在: {resource_id}")
            return False

        managed_resource = self._resources[resource_id]

        # 避免重复清理
        if managed_resource.state != ResourceState.ACTIVE:
            logger.debug(f"资源已清理或正在清理中: {managed_resource.name}")
            return managed_resource.state == ResourceState.CLEANED

        # 标记为清理中
        managed_resource.state = ResourceState.CLEANING

        # 使用信号量限制并发清理
        async with self._cleanup_semaphore:
            return await self._do_cleanup_resource(resource_id, managed_resource)

    async def _do_cleanup_resource(
        self, resource_id: str, managed_resource: ManagedResource
    ) -> bool:
        """
        执行资源清理的实际逻辑.
        """
        start_time = time.time()

        # 获取实际资源对象
        actual_resource = managed_resource.resource
        if isinstance(actual_resource, weakref.ref):
            actual_resource = actual_resource()
            if actual_resource is None:
                logger.debug(f"资源已被垃圾回收: {managed_resource.name}")
                managed_resource.state = ResourceState.CLEANED
                await self.unregister_resource(resource_id)
                return True

        try:
            logger.info(f"正在清理资源: {managed_resource.name}")

            if managed_resource.is_async:
                # 异步清理
                if not self._is_event_loop_running():
                    # 没有事件循环，尝试同步清理
                    return await self._sync_fallback_cleanup(
                        resource_id, managed_resource, actual_resource
                    )

                try:
                    await asyncio.wait_for(
                        managed_resource.cleanup_func(),
                        timeout=managed_resource.timeout,
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"资源清理超时: {managed_resource.name}")
                    managed_resource.state = ResourceState.FAILED
                    return False
                except RuntimeError as e:
                    if "no running event loop" in str(e):
                        return await self._sync_fallback_cleanup(
                            resource_id, managed_resource, actual_resource
                        )
                    else:
                        raise
            else:
                # 同步清理
                managed_resource.cleanup_func()

            # 清理成功
            managed_resource.state = ResourceState.CLEANED
            elapsed = time.time() - start_time
            self._update_stats(True, elapsed)

            time_info = f"(耗时: {elapsed:.3f}s)"
            logger.debug(f"资源清理完成: {managed_resource.name} {time_info}")
            await self.unregister_resource(resource_id)
            return True

        except Exception as e:
            managed_resource.state = ResourceState.FAILED
            self._update_stats(False, time.time() - start_time)
            error_msg = f"清理资源失败: {managed_resource.name}, {e}"
            logger.error(error_msg, exc_info=True)
            # 即使清理失败也移除资源，避免重复尝试
            await self.unregister_resource(resource_id)
            return False

    async def _sync_fallback_cleanup(
        self,
        resource_id: str,
        managed_resource: ManagedResource,
        actual_resource: Any,
    ) -> bool:
        """
        同步方式清理资源的后备方案.
        """
        logger.info(f"事件循环已停止，尝试同步清理: {managed_resource.name}")

        try:
            # 尝试常见的同步清理方法
            if hasattr(actual_resource, "close"):
                actual_resource.close()
            elif hasattr(actual_resource, "stop"):
                actual_resource.stop()
            elif not managed_resource.is_async:
                managed_resource.cleanup_func()
            else:
                logger.warning(f"无法同步清理异步资源: {managed_resource.name}")
                managed_resource.state = ResourceState.FAILED
                return False

            managed_resource.state = ResourceState.CLEANED
            await self.unregister_resource(resource_id)
            return True

        except Exception as e:
            logger.error(f"同步清理失败: {managed_resource.name}, {e}")
            managed_resource.state = ResourceState.FAILED
            return False

    def _update_stats(self, success: bool, elapsed_time: float):
        """
        更新统计信息.
        """
        if success:
            self._stats["total_cleaned"] += 1
            # 计算平均清理时间
            current_avg = self._stats["avg_cleanup_time"]
            total_cleaned = self._stats["total_cleaned"]
            new_avg = current_avg * (total_cleaned - 1) + elapsed_time
            self._stats["avg_cleanup_time"] = new_avg / total_cleaned
        else:
            self._stats["total_failed"] += 1

    async def cleanup_resources_by_type(
        self, resource_type: ResourceType, parallel: bool = True
    ) -> int:
        """按类型清理资源.

        Args:
            resource_type: 资源类型
            parallel: 是否并行清理

        Returns:
            int: 成功清理的资源数量
        """
        resource_ids = self.list_resources(resource_type)
        if not resource_ids:
            return 0

        if parallel and len(resource_ids) > 1:
            return await self._cleanup_resources_parallel(resource_ids)
        else:
            return await self._cleanup_resources_sequential(resource_ids)

    async def _cleanup_resources_parallel(self, resource_ids: List[str]) -> int:
        """
        并行清理资源.
        """
        # 按依赖关系和优先级排序
        sorted_resources = await self._sort_resources_by_dependencies(resource_ids)

        success_count = 0
        cleanup_tasks = []

        # 创建清理任务
        for resource_id in sorted_resources:
            if not self._is_event_loop_running():
                logger.warning("事件循环已停止，切换到顺序清理")
                return await self._cleanup_resources_sequential(resource_ids)

            try:
                task_name = f"cleanup_{resource_id}"
                cleanup_task = self.cleanup_resource(resource_id)
                task = asyncio.create_task(cleanup_task, name=task_name)
                cleanup_tasks.append((resource_id, task))
            except RuntimeError as e:
                if "no running event loop" in str(e):
                    msg = f"无法创建清理任务，事件循环已停止: {resource_id}"
                    logger.warning(msg)
                    continue
                else:
                    raise

        # 等待所有清理任务完成
        if cleanup_tasks:
            try:
                tasks = [task for _, task in cleanup_tasks]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                success_count = sum(1 for result in results if result is True)
            except RuntimeError as e:
                if "no running event loop" in str(e):
                    logger.warning("事件循环已停止，统计已完成的任务")
                    success_count = sum(
                        1
                        for _, task in cleanup_tasks
                        if (
                            task.done()
                            and not task.cancelled()
                            and task.result() is True
                        )
                    )
                else:
                    raise

        return success_count

    async def _cleanup_resources_sequential(self, resource_ids: List[str]) -> int:
        """
        顺序清理资源.
        """
        # 按依赖关系和优先级排序
        sorted_resources = await self._sort_resources_by_dependencies(resource_ids)

        success_count = 0
        for resource_id in sorted_resources:
            try:
                if await self.cleanup_resource(resource_id):
                    success_count += 1
            except Exception as e:
                logger.error(f"清理资源 {resource_id} 时出错: {e}")

        return success_count

    async def _sort_resources_by_dependencies(
        self, resource_ids: List[str]
    ) -> List[str]:
        """
        根据依赖关系和优先级排序资源.
        """
        # 获取资源信息
        resources_info = []
        for resource_id in resource_ids:
            if resource_id in self._resources:
                managed_resource = self._resources[resource_id]
                resources_info.append((resource_id, managed_resource))

        # 按优先级排序（优先级高的先清理）
        resources_info.sort(key=lambda x: x[1].priority, reverse=True)

        # TODO: 实现更复杂的依赖关系解析
        # 目前只按优先级排序，后续可以添加拓扑排序来处理复杂依赖

        return [resource_id for resource_id, _ in resources_info]

    async def cleanup_group(self, group: str, parallel: bool = True) -> int:
        """清理指定分组的所有资源.

        Args:
            group: 分组名称
            parallel: 是否并行清理

        Returns:
            int: 成功清理的资源数量
        """
        if group not in self._resource_groups:
            logger.warning(f"分组不存在: {group}")
            return 0

        resource_ids = list(self._resource_groups[group])
        if parallel and len(resource_ids) > 1:
            return await self._cleanup_resources_parallel(resource_ids)
        else:
            return await self._cleanup_resources_sequential(resource_ids)

    @asynccontextmanager
    async def resource_context(
        self, resource_id: str, resource: Any, cleanup_func: Callable, **kwargs
    ):
        """
        资源上下文管理器.
        """
        try:
            # 注册资源
            await self.register_resource(resource_id, resource, cleanup_func, **kwargs)
            yield resource
        finally:
            # 自动清理
            await self.cleanup_resource(resource_id)

    async def shutdown_all(self, timeout: float = 5.0, parallel: bool = True) -> bool:
        """关闭所有资源.

        Args:
            timeout: 总超时时间
            parallel: 是否并行清理同类型资源

        Returns:
            bool: 是否所有资源都成功清理
        """
        if self._is_shutting_down:
            logger.warning("已经在关闭流程中")
            return False

        async with self._lock:
            self._is_shutting_down = True
            self._shutdown_event.set()

        logger.info("开始清理所有资源...")
        start_time = time.time()
        total_cleaned = 0

        try:
            # 检查是否有事件循环
            if not self._is_event_loop_running():
                logger.warning("没有运行的事件循环，使用同步清理")
                return self._shutdown_all_sync()

            # 按预定义顺序清理资源
            for resource_type in self._cleanup_order:
                try:
                    # 检查超时
                    if time.time() - start_time > timeout:
                        logger.warning("清理超时，剩余时间不足，停止清理")
                        break

                    cleaned = await self.cleanup_resources_by_type(
                        resource_type, parallel=parallel
                    )
                    total_cleaned += cleaned

                    # 小延迟，让其他协程有机会运行
                    if self._is_event_loop_running():
                        await asyncio.sleep(0.01)

                except RuntimeError as e:
                    if "no running event loop" in str(e):
                        logger.info("事件循环已停止，切换到同步清理模式")
                        return self._shutdown_all_sync()
                    else:
                        raise

            # 清理剩余的资源
            remaining_resources = list(self._resources.keys())
            if remaining_resources:
                logger.info(f"清理剩余的 {len(remaining_resources)} 个资源")
                if parallel and len(remaining_resources) > 1:
                    cleanup_parallel = self._cleanup_resources_parallel
                    cleaned = await cleanup_parallel(remaining_resources)
                else:
                    cleaned = await self._cleanup_resources_sequential(
                        remaining_resources
                    )
                total_cleaned += cleaned

            elapsed_time = time.time() - start_time
            remaining_count = len(self._resources)

            # 输出统计信息
            self._log_cleanup_stats(total_cleaned, remaining_count, elapsed_time)

            return remaining_count == 0

        except Exception as e:
            logger.error(f"清理资源时发生异常: {e}", exc_info=True)
            # 如果是事件循环问题，尝试同步清理
            if "no running event loop" in str(e):
                logger.info("检测到事件循环问题，尝试同步清理")
                return self._shutdown_all_sync()
            return False
        finally:
            # 强制清空剩余资源
            remaining = len(self._resources)
            if remaining > 0:
                logger.warning(f"强制清空剩余的 {remaining} 个资源")
                self._resources.clear()
                self._resource_groups.clear()

    def _log_cleanup_stats(
        self, total_cleaned: int, remaining_count: int, elapsed_time: float
    ):
        """
        记录清理统计信息.
        """
        avg_time = self._stats["avg_cleanup_time"]
        stats_msg = (
            f"资源清理统计 - 成功: {total_cleaned}, 剩余: {remaining_count}, "
            f"耗时: {elapsed_time:.2f}s, 平均清理时间: {avg_time:.3f}s"
        )
        logger.info(stats_msg)

        if remaining_count == 0:
            logger.info("所有资源清理完成")
        else:
            logger.warning(f"仍有 {remaining_count} 个资源未能清理")

    def _shutdown_all_sync(self) -> bool:
        """
        同步方式关闭所有资源（当没有事件循环时使用）
        """
        logger.info("使用同步方式清理资源...")
        total_cleaned = 0

        # 按预定义顺序清理资源
        for resource_type in self._cleanup_order:
            resource_ids = self.list_resources(resource_type)

            for resource_id in resource_ids[:]:  # 创建副本
                try:
                    managed_resource = self._resources.get(resource_id)
                    if not managed_resource:
                        continue

                    # 获取实际资源对象
                    actual_resource = managed_resource.resource
                    if isinstance(actual_resource, weakref.ref):
                        actual_resource = actual_resource()
                        if actual_resource is None:
                            self._resources.pop(resource_id, None)
                            continue

                    logger.info(f"同步清理资源: {managed_resource.name}")

                    # 尝试同步清理方法
                    if not managed_resource.is_async:
                        managed_resource.cleanup_func()
                    elif hasattr(actual_resource, "close"):
                        actual_resource.close()
                    elif hasattr(actual_resource, "stop"):
                        actual_resource.stop()
                    else:
                        msg = f"无法同步清理资源: {managed_resource.name}"
                        logger.warning(msg)
                        continue

                    self._resources.pop(resource_id, None)
                    total_cleaned += 1

                except Exception as e:
                    logger.error(f"同步清理资源失败: {resource_id}, {e}")
                    self._resources.pop(resource_id, None)

        remaining = len(self._resources)
        logger.info(f"同步清理完成，成功: {total_cleaned}, 剩余: {remaining}")

        # 强制清空剩余资源
        if remaining > 0:
            self._resources.clear()
            self._resource_groups.clear()

        return remaining == 0

    def is_shutting_down(self) -> bool:
        """
        检查是否正在关闭.
        """
        return self._is_shutting_down

    def get_stats(self) -> Dict[str, Union[int, float]]:
        """
        获取统计信息.
        """
        return self._stats.copy()

    async def reset(self):
        """
        重置资源管理器（主要用于测试）
        """
        async with self._lock:
            self._resources.clear()
            self._resource_groups.clear()
            self._is_shutting_down = False
            self._shutdown_event.clear()
            self._stats = {
                "total_registered": 0,
                "total_cleaned": 0,
                "total_failed": 0,
                "avg_cleanup_time": 0.0,
            }
            logger.info("资源管理器已重置")


# 全局资源管理器实例
_global_resource_manager = None


def get_resource_manager() -> ResourceManager:
    """
    获取全局资源管理器实例.
    """
    global _global_resource_manager
    if _global_resource_manager is None:
        _global_resource_manager = ResourceManager()
    return _global_resource_manager


# 便捷函数
async def register_resource(
    resource_id: str,
    resource: Any,
    cleanup_func: Callable,
    resource_type: ResourceType = ResourceType.OTHER,
    **kwargs,
) -> str:
    """
    注册资源的便捷函数.
    """
    return await get_resource_manager().register_resource(
        resource_id, resource, cleanup_func, resource_type, **kwargs
    )


async def unregister_resource(resource_id: str) -> bool:
    """
    注销资源的便捷函数.
    """
    return await get_resource_manager().unregister_resource(resource_id)


async def shutdown_all_resources(timeout: float = 5.0) -> bool:
    """
    关闭所有资源的便捷函数.
    """
    return await get_resource_manager().shutdown_all(timeout)
