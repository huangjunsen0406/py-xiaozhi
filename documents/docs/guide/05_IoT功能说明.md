# IoT功能说明

## 概述

py-xiaozhi项目中的IoT（物联网）模块提供了一个灵活、可扩展的设备控制框架，支持通过语音命令控制多种虚拟和物理设备。本文档详细介绍IoT模块的架构、使用方法以及如何扩展自定义设备。

## 核心架构

IoT模块采用分层设计，由以下主要组件构成：

```
├── iot                          # IoT设备相关模块
│   ├── things                   # 具体设备实现目录 
│   │   ├── lamp.py              # 灯设备实现
│   │   ├── speaker.py           # 音量控制实现
│   │   ├── music_player.py      # 音乐播放器实现
│   │   ├── CameraVL/            # 摄像头与视觉识别集成设备
│   │   ├── temperature_sensor.py# 温度传感器示例实现
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

### 4. 摄像头与视觉识别 (CameraVL)

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

## 注意事项

1. 设备属性更新后，会自动通过WebSocket推送状态到服务端和UI界面
2. 设备方法的实现应该考虑异步操作，避免阻塞主线程
3. 参数类型和格式应严格遵循ValueType中定义的类型
4. 新增设备时应确保设备ID全局唯一
5. 所有设备方法应该实现适当的错误处理和反馈机制

## 高级主题：Home Assistant集成

### 通过MQTT控制Home Assistant

Home Assistant是一个流行的开源家庭自动化平台，支持通过MQTT协议控制各种智能设备。以下是如何创建一个与Home Assistant集成的设备示例：

```python
import paho.mqtt.client as mqtt
import json
import time
from src.iot.thing import Thing, Parameter, ValueType
from src.utils.logging_config import get_logger
from src.utils.config_manager import ConfigManager

logger = get_logger(__name__)

class HomeAssistantLight(Thing):
    """
    通过MQTT协议控制Home Assistant中的灯设备
    
    支持开关、亮度调节和颜色调整功能
    """
    
    def __init__(self, entity_id, friendly_name=None):
        """
        初始化Home Assistant灯设备
        
        参数:
            entity_id: Home Assistant中的实体ID，例如 'light.living_room'
            friendly_name: 显示名称，如不提供则使用entity_id
        """
        self.entity_id = entity_id
        name = friendly_name or entity_id.replace(".", "_")
        super().__init__(name, f"Home Assistant灯设备: {friendly_name or entity_id}")
        
        # 设备状态
        self.state = "off"
        self.brightness = 255  # 亮度值 0-255
        self.rgb_color = [255, 255, 255]  # RGB颜色
        
        # MQTT客户端配置
        config = ConfigManager.get_instance()
        self.mqtt_config = {
            "host": config.get_config("HOME_ASSISTANT.MQTT.host", "localhost"),
            "port": config.get_config("HOME_ASSISTANT.MQTT.port", 1883),
            "username": config.get_config("HOME_ASSISTANT.MQTT.username", ""),
            "password": config.get_config("HOME_ASSISTANT.MQTT.password", ""),
            "command_topic": f"homeassistant/light/{self.entity_id}/set",
            "state_topic": f"homeassistant/light/{self.entity_id}/state"
        }
        
        # 创建MQTT客户端
        self._setup_mqtt_client()
        
        # 注册属性
        self.add_property("state", "灯的状态 (on/off)", lambda: self.state)
        self.add_property("brightness", "灯的亮度 (0-255)", lambda: self.brightness)
        self.add_property("rgb_color", "灯的RGB颜色", lambda: self.rgb_color)
        
        # 注册方法
        self.add_method(
            "TurnOn", 
            "打开灯",
            [],
            lambda params: self._turn_on()
        )
        
        self.add_method(
            "TurnOff", 
            "关闭灯",
            [],
            lambda params: self._turn_off()
        )
        
        self.add_method(
            "SetBrightness", 
            "设置灯的亮度",
            [Parameter("brightness", "亮度值 (0-100)", ValueType.NUMBER, True)],
            lambda params: self._set_brightness(params["brightness"].get_value())
        )
        
        self.add_method(
            "SetColor", 
            "设置灯的颜色",
            [
                Parameter("red", "红色分量 (0-255)", ValueType.NUMBER, True),
                Parameter("green", "绿色分量 (0-255)", ValueType.NUMBER, True),
                Parameter("blue", "蓝色分量 (0-255)", ValueType.NUMBER, True)
            ],
            lambda params: self._set_color(
                params["red"].get_value(),
                params["green"].get_value(),
                params["blue"].get_value()
            )
        )
        
        # 刷新设备状态
        self._request_state()
    
    def _setup_mqtt_client(self):
        """设置MQTT客户端"""
        self.mqtt_client = mqtt.Client()
        
        # 设置认证
        if self.mqtt_config["username"] and self.mqtt_config["password"]:
            self.mqtt_client.username_pw_set(
                self.mqtt_config["username"], 
                self.mqtt_config["password"]
            )
        
        # 设置回调
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        self.mqtt_client.on_disconnect = self._on_disconnect
        
        # 连接MQTT服务器
        try:
            self.mqtt_client.connect(
                self.mqtt_config["host"], 
                self.mqtt_config["port"], 
                60
            )
            self.mqtt_client.loop_start()
            logger.info(f"MQTT客户端已连接到 {self.mqtt_config['host']}:{self.mqtt_config['port']}")
        except Exception as e:
            logger.error(f"MQTT连接失败: {e}")
    
    def _on_connect(self, client, userdata, flags, rc):
        """连接回调"""
        if rc == 0:
            logger.info(f"已成功连接到MQTT服务器，订阅主题: {self.mqtt_config['state_topic']}")
            # 订阅状态主题
            client.subscribe(self.mqtt_config["state_topic"])
            # 请求当前状态
            self._request_state()
        else:
            logger.error(f"连接MQTT服务器失败，返回码: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """断开连接回调"""
        logger.warning(f"与MQTT服务器断开连接，返回码: {rc}")
        if rc != 0:
            logger.info("尝试重新连接...")
            time.sleep(5)
            try:
                client.reconnect()
            except Exception as e:
                logger.error(f"重连失败: {e}")
    
    def _on_message(self, client, userdata, msg):
        """消息回调"""
        try:
            payload = json.loads(msg.payload.decode())
            logger.debug(f"收到MQTT消息: {payload}")
            
            # 更新设备状态
            if "state" in payload:
                self.state = payload["state"]
            if "brightness" in payload:
                self.brightness = payload["brightness"]
            if "rgb_color" in payload and isinstance(payload["rgb_color"], list):
                self.rgb_color = payload["rgb_color"]
                
            logger.info(f"设备 {self.entity_id} 状态已更新: state={self.state}, brightness={self.brightness}")
        except Exception as e:
            logger.error(f"处理MQTT消息时出错: {e}")
    
    def _request_state(self):
        """请求设备当前状态"""
        try:
            self.mqtt_client.publish(
                f"homeassistant/light/{self.entity_id}/get", 
                ""
            )
            logger.debug(f"已请求设备 {self.entity_id} 的状态")
        except Exception as e:
            logger.error(f"请求设备状态失败: {e}")
    
    def _turn_on(self):
        """打开灯"""
        try:
            payload = {
                "state": "on"
            }
            self.mqtt_client.publish(
                self.mqtt_config["command_topic"],
                json.dumps(payload)
            )
            self.state = "on"
            logger.info(f"发送命令: 打开灯 {self.entity_id}")
            return {"status": "success", "message": f"已发送打开命令到 {self.entity_id}"}
        except Exception as e:
            logger.error(f"发送打开命令失败: {e}")
            return {"status": "error", "message": f"发送命令失败: {e}"}
    
    def _turn_off(self):
        """关闭灯"""
        try:
            payload = {
                "state": "off"
            }
            self.mqtt_client.publish(
                self.mqtt_config["command_topic"],
                json.dumps(payload)
            )
            self.state = "off"
            logger.info(f"发送命令: 关闭灯 {self.entity_id}")
            return {"status": "success", "message": f"已发送关闭命令到 {self.entity_id}"}
        except Exception as e:
            logger.error(f"发送关闭命令失败: {e}")
            return {"status": "error", "message": f"发送命令失败: {e}"}
    
    def _set_brightness(self, brightness_percent):
        """
        设置灯的亮度
        
        参数:
            brightness_percent: 亮度百分比 (0-100)
        """
        try:
            # 验证输入
            if not 0 <= brightness_percent <= 100:
                return {"status": "error", "message": "亮度必须在0-100之间"}
            
            # 将百分比转换为Home Assistant使用的0-255范围
            brightness = int(brightness_percent * 255 / 100)
            
            payload = {
                "state": "on",
                "brightness": brightness
            }
            
            self.mqtt_client.publish(
                self.mqtt_config["command_topic"],
                json.dumps(payload)
            )
            
            self.state = "on"
            self.brightness = brightness
            
            logger.info(f"发送命令: 设置灯 {self.entity_id} 亮度为 {brightness_percent}%")
            return {
                "status": "success", 
                "message": f"已将 {self.entity_id} 亮度设置为 {brightness_percent}%"
            }
        except Exception as e:
            logger.error(f"设置亮度失败: {e}")
            return {"status": "error", "message": f"设置亮度失败: {e}"}
    
    def _set_color(self, red, green, blue):
        """
        设置灯的颜色
        
        参数:
            red: 红色分量 (0-255)
            green: 绿色分量 (0-255)
            blue: 蓝色分量 (0-255)
        """
        try:
            # 验证输入
            for value, color in [(red, "红"), (green, "绿"), (blue, "蓝")]:
                if not 0 <= value <= 255:
                    return {"status": "error", "message": f"{color}色值必须在0-255之间"}
            
            payload = {
                "state": "on",
                "rgb_color": [red, green, blue]
            }
            
            self.mqtt_client.publish(
                self.mqtt_config["command_topic"],
                json.dumps(payload)
            )
            
            self.state = "on"
            self.rgb_color = [red, green, blue]
            
            logger.info(f"发送命令: 设置灯 {self.entity_id} 颜色为 RGB({red},{green},{blue})")
            return {
                "status": "success", 
                "message": f"已将 {self.entity_id} 颜色设置为 RGB({red},{green},{blue})"
            }
        except Exception as e:
            logger.error(f"设置颜色失败: {e}")
            return {"status": "error", "message": f"设置颜色失败: {e}"}
```

### 配置和使用Home Assistant设备

1. **配置文件设置**

在`config/config.json`中添加Home Assistant MQTT配置：

```json
{
  "HOME_ASSISTANT": {
    "MQTT": {
      "host": "你的Home Assistant IP地址",
      "port": 1883,
      "username": "mqtt用户名",
      "password": "mqtt密码"
    },
    "DEVICES": [
      {
        "entity_id": "light.living_room",
        "friendly_name": "客厅灯"
      },
      {
        "entity_id": "light.bedroom",
        "friendly_name": "卧室灯"
      }
    ]
  }
}
```

2. **注册Home Assistant设备**

在`Application._initialize_iot_devices`方法中添加：

```python
# 添加Home Assistant设备
from src.iot.things.ha_light import HomeAssistantLight

# 从配置中读取Home Assistant设备列表
ha_devices = self.config.get_config("HOME_ASSISTANT.DEVICES", [])
for device in ha_devices:
    entity_id = device.get("entity_id")
    friendly_name = device.get("friendly_name")
    if entity_id:
        thing_manager.add_thing(HomeAssistantLight(entity_id, friendly_name))
        logger.info(f"已添加Home Assistant设备: {friendly_name or entity_id}")
```

3. **语音命令示例**

- "打开客厅灯"
- "把卧室灯调暗一点"
- "将客厅灯设置为蓝色"
- "关闭所有灯"

### Home Assistant设备使用说明

1. **先决条件**
   - 已安装并配置好Home Assistant
   - Home Assistant已启用MQTT集成
   - 已在Home Assistant中配置好智能灯设备

2. **注意事项**
   - 需要确保MQTT服务器允许外部连接
   - Home Assistant中的实体ID要与配置文件中一致
   - MQTT主题格式可能需要根据你的Home Assistant配置进行调整 

### 通信协议限制

当前IoT协议(1.0版本)存在以下限制：

1. **单向控制流**：大模型只能下发指令，无法立即获取指令执行结果
2. **状态更新延迟**：设备状态变更需要等到下一轮对话时，通过读取property属性值才能获知
3. **异步反馈**：如果需要操作结果反馈，必须通过设备属性的方式间接实现

### 最佳实践

1. **使用有意义的属性名称**：属性名称应清晰表达其含义，便于大模型理解和使用

2. **不产生歧义的方法描述**：为每个方法提供明确的自然语言描述，帮助大模型更准确地理解和调用