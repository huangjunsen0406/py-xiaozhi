# IoT 设备开发指南

## 概述

py-xiaozhi 项目采用基于 Thing Pattern 的 IoT 设备架构，提供统一的设备抽象和管理接口。所有设备都继承自 Thing 基类，通过 ThingManager 进行集中管理。该架构支持异步操作、类型安全的参数处理和状态管理。

**重要说明**: 当前项目正在从 IoT 设备模式向 MCP (Model Context Protocol) 工具模式迁移，部分设备功能已迁移到 MCP 工具系统。

## 核心架构

### 目录结构

```
src/iot/
├── thing.py                 # 核心基类和工具类
│   ├── Thing               # 设备抽象基类
│   ├── Property            # 设备属性类
│   ├── Method              # 设备方法类
│   ├── Parameter           # 方法参数类
│   └── ValueType           # 参数类型枚举
├── thing_manager.py        # 设备管理器
│   └── ThingManager        # 单例设备管理器
└── things/                 # 设备实现
    ├── lamp.py            # 灯光设备
    ├── speaker.py         # 音响设备
    ├── music_player.py    # 音乐播放器
    ├── countdown_timer.py # 倒计时器
    └── CameraVL/          # 摄像头设备
        ├── Camera.py
        └── VL.py
```

### 核心组件

#### 1. Thing 基类

Thing 是所有 IoT 设备的抽象基类，提供统一的接口规范：

```python
from src.iot.thing import Thing, Parameter, ValueType

class Thing:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.properties = {}
        self.methods = {}
    
    def add_property(self, name: str, description: str, getter: Callable)
    def add_method(self, name: str, description: str, parameters: List[Parameter], callback: Callable)
    async def get_descriptor_json(self) -> str
    async def get_state_json(self) -> str
    async def invoke(self, command: dict) -> dict
```

**关键要求：**

- 所有属性 getter 函数必须是异步的 (`async def`)
- 所有方法 callback 函数必须是异步的
- 设备名称必须全局唯一

#### 2. Property 属性系统

Property 用于定义设备的可读状态，支持自动类型推断：

```python
class Property:
    def __init__(self, name: str, description: str, getter: Callable):
        # 强制要求getter必须是异步函数
        if not inspect.iscoroutinefunction(getter):
            raise TypeError(f"Property getter for '{name}' must be an async function.")
```

**支持的属性类型：**

- `boolean`: 布尔值
- `number`: 整数
- `string`: 字符串
- `float`: 浮点数
- `array`: 数组
- `object`: 对象

#### 3. Method 方法系统

Method 用于定义设备的可执行操作：

```python
class Method:
    def __init__(self, name: str, description: str, parameters: List[Parameter], callback: Callable):
        # 强制要求回调函数必须是异步函数
        if not inspect.iscoroutinefunction(callback):
            raise TypeError(f"Method callback for '{name}' must be an async function.")
```

#### 4. Parameter 参数系统

Parameter 定义方法的参数规范：

```python
class Parameter:
    def __init__(self, name: str, description: str, type_: str, required: bool = True):
        self.name = name
        self.description = description
        self.type = type_
        self.required = required
    
    def get_value(self):
        return self.value
```

**支持的参数类型：**

- `ValueType.BOOLEAN`: 布尔值
- `ValueType.NUMBER`: 整数
- `ValueType.STRING`: 字符串
- `ValueType.FLOAT`: 浮点数
- `ValueType.ARRAY`: 数组
- `ValueType.OBJECT`: 对象

#### 5. ThingManager 管理器

ThingManager 采用单例模式，负责设备的注册、状态管理和方法调用：

```python
from src.iot.thing_manager import ThingManager

class ThingManager:
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ThingManager()
        return cls._instance
    
    def add_thing(self, thing: Thing)
    async def get_states_json(self, delta: bool = False) -> Tuple[bool, str]
    async def get_descriptors_json(self) -> str
    async def invoke(self, command: dict) -> dict
```

**核心功能：**

- 设备注册和管理
- 状态缓存和增量更新
- 方法调用分发
- 设备描述信息查询

## 设备实现模式

### 1. 基础设备 - Lamp

最简单的设备实现模式：

```python
import asyncio
from src.iot.thing import Thing

class Lamp(Thing):
    def __init__(self):
        super().__init__("Lamp", "一个测试用的灯")
        self.power = False
        
        # 注册属性 - getter必须是异步函数
        self.add_property("power", "灯是否打开", self.get_power)
        
        # 注册方法 - callback必须是异步函数
        self.add_method("TurnOn", "打开灯", [], self._turn_on)
        self.add_method("TurnOff", "关闭灯", [], self._turn_off)
    
    async def get_power(self):
        return self.power
    
    async def _turn_on(self, params):
        self.power = True
        return {"status": "success", "message": "灯已打开"}
    
    async def _turn_off(self, params):
        self.power = False
        return {"status": "success", "message": "灯已关闭"}
```

### 2. 带参数设备 - Speaker

带参数验证的设备实现：

```python
import asyncio
from src.iot.thing import Thing, Parameter, ValueType
from src.utils.volume_controller import VolumeController

class Speaker(Thing):
    def __init__(self):
        super().__init__("Speaker", "当前 AI 机器人的扬声器")
        
        # 初始化音量控制器
        self.volume_controller = None
        try:
            if VolumeController.check_dependencies():
                self.volume_controller = VolumeController()
                self.volume = self.volume_controller.get_volume()
            else:
                self.volume = 70
        except Exception:
            self.volume = 70
        
        # 注册属性
        self.add_property("volume", "当前音量值", self.get_volume)
        
        # 注册带参数的方法
        self.add_method(
            "SetVolume",
            "设置音量",
            [Parameter("volume", "0到100之间的整数", ValueType.NUMBER, True)],
            self._set_volume,
        )
    
    async def get_volume(self):
        if self.volume_controller:
            try:
                self.volume = self.volume_controller.get_volume()
            except Exception:
                pass
        return self.volume
    
    async def _set_volume(self, params):
        # 从Parameter对象获取值
        volume = params["volume"].get_value()
        
        # 参数验证
        if not (0 <= volume <= 100):
            raise ValueError("音量必须在0-100之间")
        
        self.volume = volume
        try:
            if self.volume_controller:
                # 异步调用系统API
                await asyncio.to_thread(self.volume_controller.set_volume, volume)
            return {"success": True, "message": f"音量已设置为: {volume}"}
        except Exception as e:
            return {"success": False, "message": f"设置音量失败: {e}"}
```

### 3. 复杂设备 - CountdownTimer

异步任务管理的设备实现：

```python
import asyncio
import json
from typing import Dict
from asyncio import Task
from src.iot.thing import Thing, Parameter
from src.iot.thing_manager import ThingManager

class CountdownTimer(Thing):
    def __init__(self):
        super().__init__("CountdownTimer", "一个用于延迟执行命令的倒计时器")
        
        # 任务管理
        self._timers: Dict[int, Task] = {}
        self._next_timer_id = 0
        self._lock = asyncio.Lock()
        
        # 注册方法
        self.add_method(
            "StartCountdown",
            "启动一个倒计时，结束后执行指定命令",
            [
                Parameter("command", "要执行的IoT命令 (JSON格式字符串)", "string", True),
                Parameter("delay", "延迟时间（秒），默认为5秒", "integer", False)
            ],
            self._start_countdown,
        )
        
        self.add_method(
            "CancelCountdown",
            "取消指定的倒计时",
            [Parameter("timer_id", "要取消的计时器ID", "integer", True)],
            self._cancel_countdown,
        )
    
    async def _start_countdown(self, params_dict):
        # 处理必需参数
        command_param = params_dict.get("command")
        command_str = command_param.get_value() if command_param else None
        
        if not command_str:
            return {"status": "error", "message": "缺少 'command' 参数值"}
        
        # 处理可选参数
        delay_param = params_dict.get("delay")
        delay = (
            delay_param.get_value()
            if delay_param and delay_param.get_value() is not None
            else 5
        )
        
        # 验证命令格式
        try:
            json.loads(command_str)
        except json.JSONDecodeError:
            return {"status": "error", "message": "命令格式错误，无法解析JSON"}
        
        # 创建异步任务
        async with self._lock:
            timer_id = self._next_timer_id
            self._next_timer_id += 1
            task = asyncio.create_task(
                self._delayed_execution(delay, timer_id, command_str)
            )
            self._timers[timer_id] = task
        
        return {
            "status": "success",
            "message": f"倒计时 {timer_id} 已启动，将在 {delay} 秒后执行",
            "timer_id": timer_id
        }
    
    async def _delayed_execution(self, delay: int, timer_id: int, command_str: str):
        try:
            await asyncio.sleep(delay)
            # 执行命令
            command_dict = json.loads(command_str)
            thing_manager = ThingManager.get_instance()
            result = await thing_manager.invoke(command_dict)
            print(f"倒计时 {timer_id} 执行结果: {result}")
        except asyncio.CancelledError:
            print(f"倒计时 {timer_id} 被取消")
        finally:
            async with self._lock:
                self._timers.pop(timer_id, None)
    
    async def _cancel_countdown(self, params_dict):
        timer_id_param = params_dict.get("timer_id")
        timer_id = timer_id_param.get_value() if timer_id_param else None
        
        if timer_id is None:
            return {"status": "error", "message": "缺少 'timer_id' 参数值"}
        
        async with self._lock:
            if timer_id in self._timers:
                task = self._timers.pop(timer_id)
                task.cancel()
                return {"status": "success", "message": f"倒计时 {timer_id} 已取消"}
            else:
                return {"status": "error", "message": "计时器不存在"}
```

### 4. 多线程设备 - Camera

集成多线程和外部服务的设备实现：

```python
import threading
import base64
import cv2
from src.iot.thing import Thing
from src.iot.things.CameraVL.VL import ImageAnalyzer

class Camera(Thing):
    def __init__(self):
        super().__init__("Camera", "摄像头管理")
        self.cap = None
        self.is_running = False
        self.camera_thread = None
        self.result = ""
        
        # 初始化VL分析器
        self.VL = ImageAnalyzer.get_instance()
        
        # 注册属性
        self.add_property("power", "摄像头是否打开", self.get_power)
        self.add_property("result", "识别画面的内容", self.get_result)
        
        # 注册方法
        self.add_method("start_camera", "打开摄像头", [], self.start_camera)
        self.add_method("stop_camera", "关闭摄像头", [], self.stop_camera)
        self.add_method("capture_frame_to_base64", "识别画面", [], self.capture_frame_to_base64)
    
    async def get_power(self):
        return self.is_running
    
    async def get_result(self):
        return self.result
    
    async def start_camera(self, params):
        if self.camera_thread and self.camera_thread.is_alive():
            return {"status": "info", "message": "摄像头已在运行"}
        
        self.camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
        self.camera_thread.start()
        return {"status": "success", "message": "摄像头已启动"}
    
    async def stop_camera(self, params):
        self.is_running = False
        if self.camera_thread:
            self.camera_thread.join()
            self.camera_thread = None
        return {"status": "success", "message": "摄像头已停止"}
    
    async def capture_frame_to_base64(self, params):
        if not self.cap or not self.cap.isOpened():
            return {"status": "error", "message": "摄像头未打开"}
        
        ret, frame = self.cap.read()
        if not ret:
            return {"status": "error", "message": "无法读取画面"}
        
        # 转换为base64
        _, buffer = cv2.imencode('.jpg', frame)
        frame_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # 使用VL分析器识别画面
        self.result = str(self.VL.analyze_image(frame_base64))
        
        return {"status": "success", "result": self.result}
    
    def _camera_loop(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            return
        
        self.is_running = True
        while self.is_running:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            cv2.imshow("Camera", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.is_running = False
        
        self.cap.release()
        cv2.destroyAllWindows()
```

## 设备注册和管理

### 1. 设备注册

在应用程序启动时注册设备：

```python
from src.iot.thing_manager import ThingManager
from src.iot.things.lamp import Lamp
from src.iot.things.speaker import Speaker

def initialize_iot_devices():
    # 获取设备管理器实例
    manager = ThingManager.get_instance()
    
    # 注册设备
    manager.add_thing(Lamp())
    manager.add_thing(Speaker())
    
    print(f"已注册 {len(manager.things)} 个设备")
```

### 2. 设备状态查询

```python
# 获取所有设备状态
changed, states = await manager.get_states_json(delta=False)
print(f"设备状态: {states}")

# 获取变化的状态（增量更新）
changed, delta_states = await manager.get_states_json(delta=True)
if changed:
    print(f"状态变化: {delta_states}")
```

### 3. 设备方法调用

```python
# 调用设备方法
command = {
    "name": "Lamp",
    "method": "TurnOn",
    "parameters": {}
}
result = await manager.invoke(command)
print(f"执行结果: {result}")

# 带参数的方法调用
command = {
    "name": "Speaker",
    "method": "SetVolume",
    "parameters": {"volume": 80}
}
result = await manager.invoke(command)
```

## 开发最佳实践

### 1. 异步编程

**所有属性 getter 和方法 callback 必须是异步函数：**

```python
# 正确的异步属性
async def get_power(self):
    return self.power

# 正确的异步方法
async def turn_on(self, params):
    self.power = True
    return {"status": "success"}

# 错误：同步函数会抛出异常
def get_power(self):  # TypeError!
    return self.power
```

### 2. 参数处理

**正确处理必需和可选参数：**

```python
async def my_method(self, params):
    # 处理必需参数
    required_value = params["required_param"].get_value()
    
    # 处理可选参数
    optional_value = None
    if "optional_param" in params:
        optional_value = params["optional_param"].get_value()
    
    # 参数验证
    if not isinstance(required_value, str):
        return {"status": "error", "message": "参数类型错误"}
    
    return {"status": "success", "result": required_value}
```

### 3. 错误处理

**实现适当的错误处理：**

```python
async def risky_operation(self, params):
    try:
        # 执行可能失败的操作
        result = await self.perform_operation()
        return {"status": "success", "result": result}
    except ValueError as e:
        return {"status": "error", "message": f"参数错误: {e}"}
    except Exception as e:
        logger.error(f"操作失败: {e}", exc_info=True)
        return {"status": "error", "message": "操作失败"}
```

### 4. 资源管理

**正确管理设备资源：**

```python
class MyDevice(Thing):
    def __init__(self):
        super().__init__("MyDevice", "我的设备")
        self.resource = None
        self._lock = asyncio.Lock()
    
    async def acquire_resource(self, params):
        async with self._lock:
            if self.resource is None:
                self.resource = await self.create_resource()
            return {"status": "success"}
    
    async def cleanup(self):
        """设备清理方法"""
        if self.resource:
            await self.resource.close()
            self.resource = None
```

### 5. 日志记录

**使用统一的日志系统：**

```python
from src.utils.logging_config import get_logger

class MyDevice(Thing):
    def __init__(self):
        super().__init__("MyDevice", "我的设备")
        self.logger = get_logger(self.__class__.__name__)
    
    async def my_method(self, params):
        self.logger.info("方法被调用")
        try:
            result = await self.perform_operation()
            self.logger.info(f"操作成功: {result}")
            return {"status": "success", "result": result}
        except Exception as e:
            self.logger.error(f"操作失败: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
```

## 迁移说明

**重要提示**: 项目正在从 IoT 设备模式向 MCP (Model Context Protocol) 工具模式迁移：

1. **倒计时器**: 已迁移到 MCP 工具，提供更好的 AI 集成
2. **其他设备**: 根据复杂度可能会陆续迁移
3. **新功能**: 建议考虑直接使用 MCP 工具框架

当前 IoT 架构仍然稳定可用，适合：

- 简单的设备控制
- 学习和演示
- 快速原型开发

## 注意事项

1. **异步要求**: 所有属性 getter 和方法 callback 必须是异步函数
2. **参数处理**: 方法参数通过 Parameter 对象传递，需要调用 `get_value()` 获取值
3. **错误处理**: 实现适当的错误处理和反馈机制
4. **资源管理**: 正确管理设备资源，避免资源泄漏
5. **设备名称**: 确保设备名称全局唯一
6. **返回格式**: 方法返回应包含 `status` 和 `message` 字段

## 总结

py-xiaozhi 的 IoT 架构提供了完整的设备抽象和管理框架，支持异步操作、类型安全和状态管理。通过遵循本指南的最佳实践，可以快速开发出稳定可靠的 IoT 设备。随着项目向 MCP 工具模式迁移，建议新功能考虑使用 MCP 工具框架。
