import asyncio
from typing import Any, Callable, Dict, List, Union

from src.iot.thing import Method, Parameter, Thing


class AsyncMethod(Method):
    """支持异步操作的方法类"""
    
    def __init__(self, name: str, description: str, parameters: List[Parameter], 
                 callback: Union[Callable, Callable[..., Any]], is_async: bool = False):
        super().__init__(name, description, parameters, callback)
        self.is_async = is_async
    
    async def invoke_async(self, params: Dict[str, Any]) -> Any:
        """异步调用方法"""
        # 设置参数值
        for name, value in params.items():
            if name in self.parameters:
                self.parameters[name].set_value(value)
        
        # 检查必需参数
        for name, param in self.parameters.items():
            if param.required and param.get_value() is None:
                raise ValueError(f"缺少必需参数: {name}")
        
        # 调用回调函数
        if self.is_async:
            return await self.callback(self.parameters)
        else:
            # 对于同步回调，在线程池中执行以避免阻塞
            return await asyncio.to_thread(self.callback, self.parameters)


class AsyncThing(Thing):
    """支持异步操作的Thing基类
    
    适用于需要执行耗时操作的IoT设备，如：
    - 机械臂控制（TCP通信）
    - 网络摄像头操作
    - 文件下载/上传
    - 数据库操作
    """
    
    def __init__(self, name: str, description: str):
        super().__init__(name, description)
        # 任务管理
        self._background_tasks: Dict[str, asyncio.Task] = {}
        self._task_results: Dict[str, Any] = {}
        
    def add_async_method(self, name: str, description: str, 
                         parameters: List[Parameter], callback: Callable) -> None:
        """添加异步方法"""
        self.methods[name] = AsyncMethod(
            name, description, parameters, callback, is_async=True
        )
    
    def add_sync_method(self, name: str, description: str, 
                        parameters: List[Parameter], callback: Callable) -> None:
        """添加同步方法（会在线程池中执行）"""
        self.methods[name] = AsyncMethod(
            name, description, parameters, callback, is_async=False
        )
    
    async def invoke_async(self, command: Dict) -> Any:
        """异步调用设备方法"""
        method_name = command.get("method")
        if method_name not in self.methods:
            raise ValueError(f"方法不存在: {method_name}")
        
        method = self.methods[method_name]
        parameters = command.get("parameters", {})
        
        if isinstance(method, AsyncMethod):
            return await method.invoke_async(parameters)
        else:
            # 兼容原有同步方法
            return await asyncio.to_thread(method.invoke, parameters)
    
    def start_background_task(self, task_name: str, coro) -> str:
        """启动后台任务"""
        if task_name in self._background_tasks:
            # 取消现有任务
            self._background_tasks[task_name].cancel()
        
        task = asyncio.create_task(coro)
        self._background_tasks[task_name] = task
        
        # 设置完成回调
        def done_callback(t):
            try:
                if not t.cancelled():
                    self._task_results[task_name] = t.result()
            except Exception as e:
                self._task_results[task_name] = {"error": str(e)}
            finally:
                self._background_tasks.pop(task_name, None)
        
        task.add_done_callback(done_callback)
        return task_name
    
    def get_task_status(self, task_name: str) -> Dict[str, Any]:
        """获取任务状态"""
        if task_name in self._background_tasks:
            task = self._background_tasks[task_name]
            return {
                "status": "running",
                "done": task.done(),
                "cancelled": task.cancelled()
            }
        elif task_name in self._task_results:
            return {
                "status": "completed",
                "result": self._task_results[task_name]
            }
        else:
            return {"status": "not_found"}
    
    def cancel_task(self, task_name: str) -> bool:
        """取消任务"""
        if task_name in self._background_tasks:
            self._background_tasks[task_name].cancel()
            return True
        return False
    
    async def cleanup(self):
        """清理资源"""
        # 取消所有后台任务
        for task in self._background_tasks.values():
            task.cancel()
        
        # 等待任务取消完成
        if self._background_tasks:
            await asyncio.gather(
                *self._background_tasks.values(), return_exceptions=True
            )
        
        self._background_tasks.clear()
        self._task_results.clear() 