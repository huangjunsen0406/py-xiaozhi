import time

import requests

from src.iot.thing import Parameter, Thing, ValueType
from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class HomeAssistantDevice(Thing):
    """Home Assistant设备基类.

    提供所有Home Assistant设备的通用功能
    """

    def __init__(self, entity_id, friendly_name=None, device_type="设备"):
        """初始化Home Assistant设备.

        参数:
            entity_id: Home Assistant中的实体ID
            friendly_name: 显示名称，如不提供则使用entity_id
            device_type: 设备类型描述，用于日志和显示
        """
        self.entity_id = entity_id
        name = friendly_name or entity_id.replace(".", "_")
        super().__init__(
            name, f"Home Assistant{device_type}: {friendly_name or entity_id}"
        )

        # 设备状态
        self.state = "off"  # 默认关闭状态
        self.last_update = int(time.time())  # 当前时间戳

        # HA API配置
        config = ConfigManager.get_instance()
        self.ha_config = {
            "url": config.get_config("HOME_ASSISTANT.URL", "http://123.60.32.150:8123"),
            "token": config.get_config("HOME_ASSISTANT.TOKEN", ""),
        }

        # HA API请求头
        self.headers = {
            "Authorization": f"Bearer {self.ha_config['token']}",
            "Content-Type": "application/json",
        }

        # 注册基本属性
        self.add_property("state", "设备状态 (on/off)", lambda: self.state)
        self.add_property("last_update", "最后更新时间戳", lambda: self.last_update)

        # 注册基本方法
        self.add_method("TurnOn", "打开设备", [], lambda params: self._turn_on())

        self.add_method("TurnOff", "关闭设备", [], lambda params: self._turn_off())

    def _update_state(self):
        """获取设备当前状态."""
        try:
            url = f"{self.ha_config['url']}/api/states/{self.entity_id}"
            response = requests.get(url, headers=self.headers, timeout=5)

            if response.status_code == 200:
                data = response.json()
                self.state = data.get("state", "off")
                self.last_update = int(time.time())

                # 子类可以覆盖此方法以处理额外的属性
                self._process_attributes(data.get("attributes", {}))

                logger.info(f"设备 {self.entity_id} 状态已更新: state={self.state}")
                return True
            else:
                logger.error(
                    f"获取设备状态失败, 状态码: {response.status_code}, 响应: {response.text}"
                )
                return False
        except Exception as e:
            logger.error(f"获取设备状态出错: {e}")
            return False

    def _process_attributes(self, attributes):
        """处理设备属性，由子类覆盖以处理特定属性."""

    def _call_service(self, service_domain, service_action, payload):
        """调用Home Assistant服务.

        参数:
            service_domain: 服务域，例如 'light'、'switch'
            service_action: 服务动作，例如 'turn_on'、'turn_off'
            payload: 请求参数
        """
        try:
            url = (
                f"{self.ha_config['url']}/api/services/"
                f"{service_domain}/{service_action}"
            )

            response = requests.post(url, headers=self.headers, json=payload, timeout=5)

            if response.status_code in [200, 201]:
                # 更新本地状态
                if service_action == "turn_on":
                    self.state = "on"
                elif service_action == "turn_off":
                    self.state = "off"

                self.last_update = int(time.time())
                logger.info(f"发送命令: {service_action} 到 {self.entity_id}")

                # 延迟更新状态以获取设备最新状态
                time.sleep(1)
                self._update_state()

                return {
                    "status": "success",
                    "message": f"已发送{service_action}命令到 {self.entity_id}",
                }
            else:
                logger.error(
                    f"发送{service_action}命令失败, 状态码: {response.status_code}, "
                    f"响应: {response.text}"
                )

                return {
                    "status": "error",
                    "message": f"发送命令失败, HTTP状态码: {response.status_code}",
                }
        except Exception as e:
            logger.error(f"发送{service_action}命令出错: {e}")
            return {"status": "error", "message": f"发送命令失败: {e}"}

    def _turn_on(self):
        """打开设备，子类需要实现此方法."""
        raise NotImplementedError("子类必须实现_turn_on方法")

    def _turn_off(self):
        """关闭设备，子类需要实现此方法."""
        raise NotImplementedError("子类必须实现_turn_off方法")


class HomeAssistantLight(HomeAssistantDevice):
    """通过HTTP API控制Home Assistant中的灯设备.

    支持开关和亮度调节功能
    """

    def __init__(self, entity_id, friendly_name=None):
        """初始化Home Assistant灯设备.

        参数:
            entity_id: Home Assistant中的实体ID，例如 'light.living_room'
            friendly_name: 显示名称，如不提供则使用entity_id
        """
        super().__init__(entity_id, friendly_name, device_type="灯设备")

        # 灯特有属性
        self.brightness = 0  # 默认亮度值为0

        # 注册灯特有属性
        self.add_property("brightness", "灯的亮度 (0-100)", lambda: self.brightness)

        # 注册灯特有方法
        self.add_method(
            "SetBrightness",
            "设置灯的亮度",
            [Parameter("brightness", "亮度值 (0-100)", ValueType.NUMBER, True)],
            lambda params: self._set_brightness(params["brightness"].get_value()),
        )

        # 初始化时更新状态
        try:
            self._update_state()
        except Exception as e:
            logger.error(f"初始化时更新设备状态失败: {e}")

        logger.info(f"Home Assistant灯设备初始化完成: {self.entity_id}")

    def _process_attributes(self, attributes):
        """处理灯特有的属性."""
        if "brightness" in attributes and attributes["brightness"] is not None:
            self.brightness = min(int(attributes["brightness"] * 100 / 255), 100)
        else:
            # 如果没有亮度属性，设置默认值
            self.brightness = 100 if self.state == "on" else 0

    def _turn_on(self):
        """打开灯."""
        return self._call_service("light", "turn_on", {"entity_id": self.entity_id})

    def _turn_off(self):
        """关闭灯."""
        return self._call_service("light", "turn_off", {"entity_id": self.entity_id})

    def _set_brightness(self, brightness_percent):
        """设置灯的亮度.

        参数:
            brightness_percent: 亮度百分比 (0-100)
        """
        try:
            # 验证输入
            if not 0 <= brightness_percent <= 100:
                return {"status": "error", "message": "亮度必须在0-100之间"}

            # 将百分比转换为Home Assistant使用的0-255范围
            brightness = int(brightness_percent * 255 / 100)

            payload = {"entity_id": self.entity_id, "brightness": brightness}

            # 调用服务
            result = self._call_service("light", "turn_on", payload)

            if result["status"] == "success":
                self.brightness = brightness_percent
                return {
                    "status": "success",
                    "message": f"已将 {self.entity_id} 亮度设置为 {brightness_percent}%",
                }

            return result

        except Exception as e:
            logger.error(f"设置亮度出错: {e}")
            return {"status": "error", "message": f"设置亮度失败: {e}"}


class HomeAssistantSwitch(HomeAssistantDevice):
    """通过HTTP API控制Home Assistant中的开关设备.

    支持开关功能
    """

    def __init__(self, entity_id, friendly_name=None):
        """初始化Home Assistant开关设备.

        参数:
            entity_id: Home Assistant中的实体ID，例如 'switch.bedroom_switch'
            friendly_name: 显示名称，如不提供则使用entity_id
        """
        super().__init__(entity_id, friendly_name, device_type="开关设备")

        # 初始化时更新状态
        try:
            self._update_state()
        except Exception as e:
            logger.error(f"初始化时更新设备状态失败: {e}")

        logger.info(f"Home Assistant开关设备初始化完成: {self.entity_id}")

    def _turn_on(self):
        """打开开关."""
        return self._call_service("switch", "turn_on", {"entity_id": self.entity_id})

    def _turn_off(self):
        """关闭开关."""
        return self._call_service("switch", "turn_off", {"entity_id": self.entity_id})


class HomeAssistantNumber(HomeAssistantDevice):
    """通过HTTP API控制Home Assistant中的数值型设备（如音量）"""

    def __init__(self, entity_id, friendly_name=None):
        super().__init__(entity_id, friendly_name, device_type="数值设备")

        # 数值设备特有属性
        self.value = 0
        self.min = 0
        self.max = 100
        self.step = 1

        # 注册特有属性
        self.add_property("value", "当前值", lambda: self.value)

        # 注册特有方法
        self.add_method(
            "SetValue",
            "设置数值",
            [Parameter("value", "设置值", ValueType.NUMBER, True)],
            lambda params: self._set_value(params["value"].get_value()),
        )

        try:
            self._update_state()
        except Exception as e:
            logger.error(f"初始化时更新设备状态失败: {e}")

        logger.info(f"Home Assistant数值设备初始化完成: {self.entity_id}")

    def _process_attributes(self, attributes):
        self.min = attributes.get("min", 0)
        self.max = attributes.get("max", 100)
        self.step = attributes.get("step", 1)
        if "value" in attributes:
            self.value = attributes["value"]

    def _turn_on(self):
        """数值设备不支持直接开关."""
        return {"status": "error", "message": "数值设备不支持直接开关操作"}

    def _turn_off(self):
        """数值设备不支持直接开关."""
        return {"status": "error", "message": "数值设备不支持直接开关操作"}

    def _set_value(self, value):
        """设置数值."""
        try:
            # 值校验
            if value < self.min or value > self.max:
                return {
                    "status": "error",
                    "message": f"值必须在{self.min}-{self.max}范围内",
                }

            payload = {"entity_id": self.entity_id, "value": value}

            # 调用服务
            result = self._call_service("number", "set_value", payload)

            if result["status"] == "success":
                self.value = value
                return {
                    "status": "success",
                    "message": f"已将 {self.entity_id} 的值设置为 {value}",
                }

            return result

        except Exception as e:
            logger.error(f"设置值出错: {e}")
            return {"status": "error", "message": f"设置值失败: {e}"}


class HomeAssistantButton(HomeAssistantDevice):
    """通过HTTP API控制Home Assistant中的按钮设备."""

    def __init__(self, entity_id, friendly_name=None):
        super().__init__(entity_id, friendly_name, device_type="按钮设备")

        # 按钮设备只有按下的动作，没有状态
        self.last_pressed = 0  # 上次按下的时间戳

        # 注册按钮特有属性
        self.add_property("last_pressed", "上次按下时间", lambda: self.last_pressed)

        # 注册按钮特有方法
        self.add_method("Press", "按下按钮", [], lambda params: self._press())

        try:
            self._update_state()
        except Exception as e:
            logger.error(f"初始化时更新设备状态失败: {e}")

        logger.info(f"Home Assistant按钮设备初始化完成: {self.entity_id}")

    def _turn_on(self):
        """按钮设备使用Press替代TurnOn."""
        return self._press()

    def _turn_off(self):
        """按钮设备不支持关闭操作."""
        return {"status": "error", "message": "按钮设备不支持关闭操作"}

    def _press(self):
        """按下按钮."""
        try:
            # 在Home Assistant中，按下按钮是调用press服务
            payload = {"entity_id": self.entity_id}

            # 调用服务
            result = self._call_service("button", "press", payload)

            if result["status"] == "success":
                self.last_pressed = int(time.time())
                return {"status": "success", "message": f"已按下 {self.entity_id} 按钮"}

            return result

        except Exception as e:
            logger.error(f"按下按钮出错: {e}")
            return {"status": "error", "message": f"按下按钮失败: {e}"}
