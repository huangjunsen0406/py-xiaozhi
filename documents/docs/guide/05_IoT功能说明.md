# IoT功能说明

## 概述

py-xiaozhi项目中的IoT（物联网）模块提供了一个灵活、可扩展的设备控制框架，支持通过语音命令控制多种虚拟和物理设备。本文档详细介绍IoT模块的架构、使用方法以及如何扩展自定义设备。
如需执行完立马同步状态和播报结果请参考相机模块和温湿度模块

## 核心架构

IoT模块采用分层设计，由以下主要组件构成：

```
├── iot                          # IoT设备相关模块
│   ├── things                   # 具体设备实现目录 
│   │   ├── lamp.py              # 灯设备实现
│   │   ├── speaker.py           # 音量控制实现
│   │   ├── music_player.py      # 音乐播放器实现
│   │   ├── countdown_timer.py   # 倒计时器实现
│   │   ├── ha_control.py        # Home Assistant设备控制
│   │   ├── CameraVL/            # 摄像头与视觉识别集成设备
│   │   ├── temperature_sensor.py# 温度传感器实现
│   │   └── query_bridge_rag.py  # RAG检索桥接设备
│   ├── thing.py                 # IoT设备基类和工具类定义
│   │   ├── Thing                # IoT设备抽象基类
│   │   ├── Property             # 设备属性类
│   │   ├── Parameter            # 设备方法参数类
│   │   └── Method               # 设备方法类
│   └── thing_manager.py         # IoT设备管理器
│       └── ThingManager         # 单例模式实现的设备管理器
```

### 核心类说明

1. **Thing（设备基类）**：
   - 所有IoT设备的抽象基类
   - 提供属性和方法的注册机制
   - 提供状态和描述的JSON序列化

2. **Property（属性类）**：
   - 定义设备的可变状态（如开/关、亮度等）
   - 支持布尔、数字和字符串三种基本类型
   - 使用getter回调实时获取设备状态

3. **Method（方法类）**：
   - 定义设备可执行的操作（如打开、关闭等）
   - 支持带参数的方法调用
   - 通过callback处理具体操作实现

4. **Parameter（参数类）**：
   - 定义方法的参数规范
   - 包含名称、描述、类型和是否必需等信息

5. **ThingManager（设备管理器）**：
   - 集中管理所有IoT设备实例
   - 处理设备注册和命令分发
   - 提供设备描述和状态查询接口

## 命令处理流程

以下是语音命令被处理并执行IoT设备控制的完整流程：

```
                              +-------------------+
                              |    用户语音指令    |
                              +-------------------+
                                       |
                                       v
                              +-------------------+
                              |     语音识别      |
                              |     (STT)        |
                              +-------------------+
                                       |
                                       v
                              +-------------------+
                              |    语义理解       |
                              |    (LLM)         |
                              +-------------------+
                                       |
                                       v
                              +-------------------+
                              |   物联网命令生成   |
                              +-------------------+
                                       |
                                       v
+------------------------------+       |       +------------------------------+
|    WebSocket服务端处理        |       |       |     Application._handle_iot_message()
|                             <--------+------->                             |
+------------------------------+               +------------------------------+
                                                           |
                                                           v
                                               +------------------------------+
                                               |   ThingManager.invoke()      |
                                               +------------------------------+
                                                           |
                      +-------------------------+----------+------------+
                      |                         |                       |
                      v                         v                       v
      +---------------+-------+    +------------+---------+   +---------+----------+
      |       Lamp            |    |      Speaker         |   |    MusicPlayer     |
      | (控制灯设备)           |    | (控制系统音量)        |   | (音乐播放器)        |
      +---------------+-------+    +------------+---------+   +---------+----------+
                      |                         |                       |
                      v                         v                       v
      +---------------+-------+    +------------+---------+   +---------+----------+
      |  执行设备相关操作      |    |   执行设备相关操作     |   |  执行设备相关操作   |
      +---------------+-------+    +------------+---------+   +---------+----------+
                      |                         |                       |
                      +-------------------------+-----------------------+
                                               |
                                               v
                                   +-----------------------------+
                                   |    更新设备状态              |
                                   |    Application._update_iot_states()
                                   +-----------------------------+
                                               |
                                               v
                                   +-----------------------------+
                                   |   发送状态更新到服务器       |
                                   |   send_iot_states()         |
                                   +-----------------------------+
                                               |
                                               v
                                   +-----------------------------+
                                   |     语音或界面反馈结果       |
                                   +-----------------------------+
```

## 内置设备说明

### 1. 灯设备 (Lamp)

虚拟灯设备，用于演示基本的IoT控制功能。

**属性**：
- `power`：灯的开关状态（布尔值）

**方法**：
- `TurnOn`：打开灯
- `TurnOff`：关闭灯

**语音命令示例**：
- "打开灯"
- "关闭灯"

### 2. 系统音量控制 (Speaker)

控制系统音量的设备，可调整应用程序的音量大小。

**属性**：
- `volume`：当前音量值（0-100）

**方法**：
- `SetVolume`：设置音量级别

**语音命令示例**：
- "把音量调到50%"
- "音量调小一点"
- "音量调大"

### 3. 音乐播放器 (MusicPlayer)

功能丰富的在线音乐播放器，支持歌曲搜索、播放控制和歌词显示。

**属性**：
- `current_song`：当前播放的歌曲
- `playing`：播放状态
- `total_duration`：歌曲总时长
- `current_position`：当前播放位置
- `progress`：播放进度

**方法**：
- `Play`：播放指定歌曲
- `Pause`：暂停播放
- `GetDuration`：获取播放信息

**语音命令示例**：
- "播放音乐周杰伦的稻香，通过iot音乐播放器播放"
- "暂停播放"
- "播放下一首"

### 4. 倒计时器 (CountdownTimer)

一个用于延迟执行命令的倒计时器设备，可以设置定时任务。

**属性**：
- 无可查询属性

**方法**：
- `StartCountdown`：启动一个倒计时，结束后执行指定命令
  - `command`：要执行的IoT命令（JSON格式字符串）
  - `delay`：延迟时间（秒），默认为5秒
- `CancelCountdown`：取消指定的倒计时
  - `timer_id`：要取消的计时器ID

**语音命令示例**：
- "设置5秒后打开灯"
- "10秒后把音量调到70%"
- "取消倒计时3"

### 5. 温度传感器 (TemperatureSensor)

通过MQTT协议连接的温湿度传感器设备，可以实时获取环境温湿度数据。

**属性**：
- `temperature`：当前温度（摄氏度）
- `humidity`：当前湿度（%）
- `last_update_time`：最后更新时间（时间戳）

**方法**：
- 无可调用方法，设备自动通过MQTT接收数据并更新状态

**特殊功能**：
- 当接收到新的温湿度数据时，会自动通过语音播报结果

**语音命令示例**：
- "查询当前室内温度"
- "室内湿度是多少"
- "温湿度传感器状态"

### 6. Home Assistant设备控制 (HomeAssistantDevice)

通过HTTP API连接到Home Assistant智能家居平台，控制各种智能设备。

#### 6.1 HomeAssistant灯设备 (HomeAssistantLight)

**属性**：
- `state`：灯的状态（on/off）
- `brightness`：灯的亮度（0-100）
- `last_update`：最后更新时间戳

**方法**：
- `TurnOn`：打开灯
- `TurnOff`：关闭灯
- `SetBrightness`：设置灯的亮度
  - `brightness`：亮度值（0-100%）

**语音命令示例**：
- "打开客厅灯"
- "把卧室灯亮度调到60%"
- "关闭所有灯"

#### 6.2 HomeAssistant开关 (HomeAssistantSwitch)

**属性**：
- `state`：开关状态（on/off）
- `last_update`：最后更新时间戳

**方法**：
- `TurnOn`：打开开关
- `TurnOff`：关闭开关

**语音命令示例**：
- "打开电风扇"
- "关闭空调"

#### 6.3 HomeAssistant数值控制器 (HomeAssistantNumber)

**属性**：
- `state`：当前状态（on/off）
- `value`：当前数值
- `min_value`：最小值
- `max_value`：最大值
- `last_update`：最后更新时间戳

**方法**：
- `TurnOn`：打开设备
- `TurnOff`：关闭设备
- `SetValue`：设置数值
  - `value`：要设置的数值

**语音命令示例**：
- "把空调温度设为26度"
- "将风扇转速调到3档"

#### 6.4 HomeAssistant按钮 (HomeAssistantButton)

**属性**：
- `state`：当前状态（on/off，通常为虚拟状态）
- `last_update`：最后更新时间戳

**方法**：
- `TurnOn`：激活按钮（执行Press操作）
- `TurnOff`：形式方法，大多数情况下无实际效果
- `Press`：按下按钮，触发按钮关联的动作

**语音命令示例**：
- "按下门铃按钮"
- "触发紧急模式"
- "启动场景播放"

### 7. 摄像头与视觉识别 (CameraVL)

集成摄像头控制和视觉识别功能，可以捕获画面并进行智能分析。

**功能**：
- 摄像头开启/关闭
- 画面智能识别
- 视觉内容分析

**语音命令示例**：
- "打开摄像头"
- "识别画面"
- "关闭摄像头"

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

### 音乐播放控制

1. 使用指令"播放音乐周杰伦的稻香，通过iot音乐播放器播放"
2. 系统解析指令并调用MusicPlayer的Play方法
3. 播放器搜索歌曲，开始播放，并显示歌词
4. 可以继续使用"暂停播放"等命令控制播放

### 倒计时控制示例

1. 使用指令"设置5秒后打开灯"
2. 系统解析指令并调用CountdownTimer的StartCountdown方法
3. 5秒后自动执行打开灯的命令
4. 返回操作结果"倒计时已设置"

### Home Assistant设备控制示例

1. 使用指令"把客厅灯调暗一点"
2. 系统解析指令并调用HomeAssistantLight的SetBrightness方法
3. 通过HTTP API向Home Assistant发送亮度调整命令
4. 返回操作结果"客厅灯亮度已调整"

## 注意事项

1. 设备属性更新后，会自动通过WebSocket推送状态到服务端和UI界面
2. 设备方法的实现应该考虑异步操作，避免阻塞主线程
3. 参数类型和格式应严格遵循ValueType中定义的类型
4. 新增设备时应确保设备ID全局唯一
5. 所有设备方法应该实现适当的错误处理和反馈机制

## 高级主题：Home Assistant集成

### 通过HTTP API控制Home Assistant

Home Assistant是一个流行的开源家庭自动化平台，本项目通过HTTP API与Home Assistant集成，支持控制各种智能设备。以下是Home Assistant集成的关键点：

1. **配置文件设置**

在`config/config.json`中添加Home Assistant配置：

```json
{
  "HOME_ASSISTANT": {
    "URL": "http://your-homeassistant-url:8123",
    "TOKEN": "your-long-lived-access-token",
    "DEVICES": [
      {
        "entity_id": "light.cuco_cn_573924446_v3_s_13_indicator_light",
        "friendly_name": "米家智能插座3-冰箱  指示灯"
      },
      {
        "entity_id": "switch.cuco_cn_573924446_v3_on_p_2_1",
        "friendly_name": "米家智能插座3-冰箱  开关 开关"
      }
    ]
  }
}
```
### 配置ha地址和密钥
![Image](./images/home_assistatnt配置.png)
### 设备选择
- 左上角开关处点击可以切换设备类型
- 选中设备后天机右下角添加选中设备
- 导入后需要重启小智等待程序加载完成就可以通过语音控制了
![Image](./images/设备选择.png)
### 导入后
![Image](./images/导入ha.png)
2. **支持的设备类型**

- `light`: 灯设备，支持开关和亮度控制
- `switch`: 开关设备，支持开关控制
- `number`: 数值控制器，支持设置数值
- `button`: 按钮设备，支持按下操作

3. **语音命令示例**

- "打开客厅灯"
- "把卧室灯调暗一点"
- "将空调温度设为26度"
- "关闭所有灯"

### 通信协议限制

当前IoT协议(1.0版本)存在以下限制：

1. **单向控制流**：大模型只能下发指令，无法立即获取指令执行结果
2. **状态更新延迟**：设备状态变更需要等到下一轮对话时，通过读取property属性值才能获知
3. **异步反馈**：如果需要操作结果反馈，必须通过设备属性的方式间接实现

### 最佳实践

1. **使用有意义的属性名称**：属性名称应清晰表达其含义，便于大模型理解和使用

2. **不产生歧义的方法描述**：为每个方法提供明确的自然语言描述，帮助大模型更准确地理解和调用