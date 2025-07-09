# 🏠 IoT功能说明

## 🌟 概述

py-xiaozhi项目中的IoT（物联网）模块提供了一个灵活、可扩展的设备控制框架，采用Thing-based架构设计，支持通过自然语言命令控制多种虚拟和物理设备。系统集成了丰富的设备类型支持，从基础的灯光控制到复杂的多媒体播放器，为用户提供统一的智能家居控制体验。

### 🎯 核心特性
- 🔧 **Thing-based架构**: 统一的设备抽象模型
- 🗣️ **自然语言控制**: 支持灵活的语音命令解析  
- 📡 **多协议支持**: WebSocket/MQTT双协议通信
- 🔌 **可扩展性**: 简单易用的设备扩展接口

> **重要提示**: 如需执行完成后立即同步状态和播报结果，请参考摄像头模块和温湿度模块的实现模式。

## 🏗️ 系统架构

### 📁 目录结构

IoT模块采用分层设计，由以下主要组件构成：
- 以下iot模块已经移植到mcp去了
```
├── src/iot/                    # IoT设备相关模块
│   ├── things/                 # 具体设备实现目录
│   │   ├── lamp.py            # 💡 灯光设备实现
│   │   ├── speaker.py         # 🔊 系统音量控制
│   │   ├── music_player.py    # 🎵 音乐播放器
│   │   ├── camera.py          # 📷 摄像头设备
│   │   ├── temperature_humidity.py  # 🌡️ 温湿度传感器
│   │   └── ...                # 更多设备类型
│   ├── thing.py               # 🔧 IoT设备基类和工具类定义
│   │   ├── Thing              # IoT设备抽象基类
│   │   ├── Property           # 设备属性类
│   │   ├── Parameter          # 设备方法参数类
│   │   └── Method             # 设备方法类
│   └── thing_manager.py       # 📋 IoT设备管理器
│       └── ThingManager       # 单例模式实现的设备管理器
```

### 🔧 核心类详解

#### 1. **Thing（设备基类）**
- **作用**: 所有IoT设备的抽象基类
- **功能**: 
  - 提供属性和方法的统一注册机制
  - 支持设备状态和描述的JSON序列化
  - 实现设备生命周期管理
  - 提供设备发现和描述接口

#### 2. **Property（属性类）**
- **作用**: 定义设备的可读/可写状态
- **支持类型**: 
  - `BOOLEAN` - 布尔值（开/关状态）
  - `NUMBER` - 数值（温度、亮度等）
  - `STRING` - 字符串（设备名称、状态描述等）
- **特性**: 使用getter回调实时获取设备状态

#### 3. **Method（方法类）**
- **作用**: 定义设备可执行的操作
- **功能**: 
  - 支持带参数的方法调用
  - 通过callback处理具体操作实现
  - 提供方法执行结果反馈

#### 4. **Parameter（参数类）**
- **作用**: 定义方法的参数规范
- **包含信息**: 
  - 参数名称和描述
  - 参数类型和是否必需
  - 参数验证规则

#### 5. **ThingManager（设备管理器）**
- **作用**: 集中管理所有IoT设备实例
- **功能**: 
  - 设备注册和生命周期管理
  - 命令分发和执行
  - 设备状态查询和更新
  - 设备发现和描述接口

## 🔄 命令处理流程

### 📋 完整处理链路

以下是语音命令被处理并执行IoT设备控制的完整流程：

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           IoT设备控制完整流程                                      │
└─────────────────────────────────────────────────────────────────────────────────┘

    🎤 用户语音指令                    📱 设备状态反馈
    "打开客厅的灯"                     "灯已打开"
         │                               ↑
         ▼                               │
    🧠 语音识别(STT)                    🔊 TTS语音合成
    文本转换处理                        │
         │                               │
         ▼                               │
    🤖 语义理解(LLM)                    📋 状态更新处理
    意图识别与解析                      │
         │                               │
         ▼                               │
    ⚙️ IoT命令生成                     🔄 设备状态同步
    结构化指令生成                      │
         │                               │
         ▼                               │
    📡 网络传输                        📊 状态数据收集
    WebSocket/MQTT                      │
         │                               │
         ▼                               │
    🏠 Application.handle_iot_message()  │
    IoT消息处理入口                      │
         │                               │
         ▼                               │
    📋 ThingManager.invoke()             │
    设备管理器调用                      │
         │                               │
         ▼                               │
    ┌─────────────────────────────────────────────────────────────┐
    │                    设备执行层                                │
    │  💡 Lamp      🔊 Speaker    🎵 MusicPlayer   📷 Camera      │
    │  灯光控制      音量控制      音乐播放        摄像头控制        │
    └─────────────────────────────────────────────────────────────┘
                               │
                               ▼
                    🔧 设备具体操作执行
                    (GPIO/API/硬件控制)
                               │
                               ▼
                    📤 执行结果返回
                    success/error状态
                               │
                               ▼
                    🔄 Application.update_iot_states()
                    状态更新通知
                               │
                               ▼
                    📡 send_iot_states()
                    推送状态到服务器
                               │
                               ▼
                    🎯 用户反馈处理
                    语音/界面状态更新
```

### 🎯 关键处理节点

1. **语音识别阶段**: 将用户语音转换为文本指令
2. **语义理解阶段**: LLM解析用户意图并生成结构化命令
3. **命令分发阶段**: ThingManager根据设备ID分发命令
4. **设备执行阶段**: 具体设备执行相应操作
5. **状态同步阶段**: 设备状态更新并推送到服务器
6. **用户反馈阶段**: 通过语音或界面告知用户执行结果

## 扩展自定义设备

要添加新的IoT设备，需要遵循以下步骤：

### 1. 创建设备类

在`src/iot/things/`目录下创建新的Python文件，定义设备类：

```python
from src.iot.thing import Thing, Parameter, ValueType

class MyCustomDevice(Thing):
    """
    自定义IoT设备实现示例
    
    此类演示了如何创建一个符合项目IoT架构的自定义设备，
    包括属性定义、方法注册以及实际功能实现
    """
    
    def __init__(self):
        # 调用父类初始化方法，设置设备名称和描述
        # 第一个参数是设备ID(全局唯一)，第二个参数是对设备的描述文本
        super().__init__("MyCustomDevice", "自定义设备描述")
        
        # 设备状态变量定义
        self.status = False  # 定义设备的开关状态，初始为关闭(False)
        self.parameter_value = 0  # 定义设备的参数值，初始为0
        self.last_update_time = 0  # 记录最后一次状态更新的时间戳
        
        # 设备初始化日志
        print("[IoT设备] 自定义设备初始化完成")
        
        # =========================
        # 注册设备属性（状态值）
        # =========================
        
        # 注册status属性，使其可被查询
        # 参数1: 属性名称 - 在JSON中显示的键名
        # 参数2: 属性描述 - 对此属性的解释说明
        # 参数3: getter回调函数 - 用于实时获取属性值的lambda函数
        self.add_property("status", "设备开关状态(True为开启，False为关闭)", 
                         lambda: self.status)
        
        # 注册parameter_value属性
        self.add_property("parameter_value", "设备参数值(0-100)", 
                         lambda: self.parameter_value)
        
        # 注册last_update_time属性
        self.add_property("last_update_time", "最后一次状态更新时间", 
                         lambda: self.last_update_time)
        
        # =========================
        # 注册设备方法（可执行的操作）
        # =========================
        
        # 注册TurnOn方法，用于打开设备
        # 参数1: 方法名称 - 用于API调用的标识符
        # 参数2: 方法描述 - 对此方法功能的说明
        # 参数3: 参数列表 - 空列表表示无参数
        # 参数4: 回调函数 - 执行实际功能的lambda函数，调用内部的_turn_on方法
        self.add_method(
            "TurnOn",  # 方法名称
            "打开设备",  # 方法描述
            [],  # 无参数
            lambda params: self._turn_on()  # 回调函数，调用内部的_turn_on方法
        )
        
        # 注册TurnOff方法，用于关闭设备
        self.add_method(
            "TurnOff", 
            "关闭设备",
            [], 
            lambda params: self._turn_off()
        )
        
        # 注册SetParameter方法，用于设置参数值
        # 此方法需要一个参数value
        self.add_method(
            "SetParameter", 
            "设置设备参数值(范围0-100)",
            # 定义方法所需参数:
            [
                # 创建参数对象: 
                # 参数1: 参数名称 - API中的参数键名
                # 参数2: 参数描述 - 对此参数的说明
                # 参数3: 参数类型 - 值类型(NUMBER表示数字类型)
                # 参数4: 是否必需 - True表示此参数必须提供
                Parameter("value", "参数值(0-100之间的数字)", ValueType.NUMBER, True)
            ],
            # 回调函数 - 从params字典中提取参数值并传递给_set_parameter方法
            lambda params: self._set_parameter(params["value"].get_value())
        )
        
        # 注册GetStatus方法，用于获取设备状态信息
        self.add_method(
            "GetStatus",
            "获取设备完整状态信息",
            [],  # 无参数
            lambda params: self._get_status()
        )
    
    # =========================
    # 内部方法实现（实际功能）
    # =========================
    
    def _turn_on(self):
        """
        打开设备的内部实现方法
        
        返回:
            dict: 包含操作状态和消息的字典
        """
        self.status = True  # 修改设备状态为开启
        self.last_update_time = int(time.time())  # 更新状态变更时间
        
        # 这里可以添加实际的硬件控制代码，如GPIO操作、串口通信等
        print(f"[IoT设备] 自定义设备已打开")
        
        # 返回操作结果，包含状态和消息
        return {
            "status": "success",  # 操作状态: success或error
            "message": "设备已打开"  # 操作结果消息
        }
    
    def _turn_off(self):
        """
        关闭设备的内部实现方法
        
        返回:
            dict: 包含操作状态和消息的字典
        """
        self.status = False  # 修改设备状态为关闭
        self.last_update_time = int(time.time())  # 更新状态变更时间
        
        # 这里可以添加实际的硬件控制代码
        print(f"[IoT设备] 自定义设备已关闭")
        
        # 返回操作结果
        return {
            "status": "success",
            "message": "设备已关闭"
        }
    
    def _set_parameter(self, value):
        """
        设置设备参数值的内部实现方法
        
        参数:
            value (float): 要设置的参数值
            
        返回:
            dict: 包含操作状态和消息的字典
            
        异常:
            ValueError: 如果参数值超出有效范围
        """
        # 参数值验证
        if not isinstance(value, (int, float)):
            return {"status": "error", "message": "参数必须是数字"}
        
        if not 0 <= value <= 100:
            return {"status": "error", "message": "参数值必须在0-100之间"}
        
        # 设置参数值
        self.parameter_value = value
        self.last_update_time = int(time.time())  # 更新状态变更时间
        
        # 这里可以添加实际的参数设置代码
        print(f"[IoT设备] 自定义设备参数已设置为: {value}")
        
        # 返回操作结果
        return {
            "status": "success",
            "message": f"参数已设置为 {value}",
            "value": value
        }
    
    def _get_status(self):
        """
        获取设备完整状态的内部实现方法
        
        返回:
            dict: 包含设备所有状态信息的字典
        """
        # 返回设备的完整状态信息
        return {
            "status": "success",
            "device_status": {
                "is_on": self.status,
                "parameter": self.parameter_value,
                "last_update": self.last_update_time
            }
        }

### 2. 注册设备

在程序启动时注册设备到ThingManager：

```python
# 在Application._initialize_iot_devices方法中
from src.iot.thing_manager import ThingManager
from src.iot.things.my_custom_device import MyCustomDevice
from src.utils.logging_config import get_logger

# 获取日志记录器实例
logger = get_logger(__name__)

def _initialize_iot_devices(self):
    """
    初始化并注册所有IoT设备
    此方法在应用程序启动时被调用
    """
    # 记录日志：开始初始化IoT设备
    logger.info("开始初始化IoT设备...")
    
    # 获取设备管理器单例实例
    # ThingManager使用单例模式，确保全局只有一个管理器实例
    thing_manager = ThingManager.get_instance()
    
    # 创建自定义设备实例
    my_device = MyCustomDevice()
    
    # 将设备实例添加到设备管理器
    # 一旦添加，设备将可以通过API和语音命令访问
    thing_manager.add_thing(my_device)
    
    # 记录成功添加设备的日志
    logger.info(f"已添加自定义设备: {my_device.name}")
    
    # 可以在这里继续添加其他设备...
    
    # 记录设备初始化完成的日志
    logger.info(f"IoT设备初始化完成，共注册了 {len(thing_manager.things)} 个设备")
```

### 3. 设备通信（可选）

如果设备需要与实体硬件通信，可以通过各种协议实现：

- MQTT：用于与标准物联网设备通信
- HTTP：用于REST API调用
- 串口/GPIO：用于直接硬件控制

## 使用示例

### 基本设备控制

1. 启动应用程序
2. 使用语音指令"打开灯"
3. 系统识别指令并执行lamp.py中的TurnOn方法
4. 灯设备状态更新，反馈给用户"灯已打开"

## 注意事项

1. 设备属性更新后，会自动通过WebSocket推送状态到服务端和UI界面
2. 设备方法的实现应该考虑异步操作，避免阻塞主线程
3. 参数类型和格式应严格遵循ValueType中定义的类型
4. 新增设备时应确保设备ID全局唯一
5. 所有设备方法应该实现适当的错误处理和反馈机制

### 通信协议限制

当前IoT协议(1.0版本)存在以下限制：

1. **单向控制流**：大模型只能下发指令，无法立即获取指令执行结果
2. **状态更新延迟**：设备状态变更需要等到下一轮对话时，通过读取property属性值才能获知
3. **异步反馈**：如果需要操作结果反馈，必须通过设备属性的方式间接实现

### 最佳实践

1. **使用有意义的属性名称**：属性名称应清晰表达其含义，便于大模型理解和使用

2. **不产生歧义的方法描述**：为每个方法提供明确的自然语言描述，帮助大模型更准确地理解和调用