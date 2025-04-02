import json
import time
from typing import Dict
from datetime import datetime

from src.iot.thing import Thing, Parameter, ValueType
from src.network.mqtt_client import MqttClient



class TemperatureSensor(Thing):
    def __init__(self):
        super().__init__("TemperatureSensor", "温度传感器设备")
        self.temperature = 0.0  # 初始温度值为0摄氏度
        self.humidity = 0.0  # 初始湿度值为0%
        self.last_update_time = 0  # 最后一次更新时间
        self.is_running = False
        self.mqtt_client = None

        print("[IoT设备] 温度传感器接收端初始化完成")

        # 定义属性
        self.add_property("temperature", "当前温度(摄氏度)", 
                          lambda: self.temperature)
        self.add_property("humidity", "当前湿度(%)", 
                          lambda: self.humidity)
        self.add_property("last_update_time", "最后更新时间", 
                          lambda: self.last_update_time)

        self.add_method("getTemperature", "获取温度传感器数据",
                        [],
                        lambda params: self.get_temperature())

        # 初始化MQTT客户端
        self._init_mqtt()

    def _init_mqtt(self):
        """初始化MQTT客户端"""
        from src.utils.config_manager import ConfigManager
        config = ConfigManager.get_instance()
        try:
            self.mqtt_client = MqttClient(
                server=config.get_config("TEMPERATURE_SENSOR_MQTT_INFO.endpoint"),
                port=config.get_config("TEMPERATURE_SENSOR_MQTT_INFO.port"),
                username=config.get_config("TEMPERATURE_SENSOR_MQTT_INFO.username"),
                password=config.get_config("TEMPERATURE_SENSOR_MQTT_INFO.password"),
                # 订阅传感器数据发送的主题
                subscribe_topic=config.get_config("TEMPERATURE_SENSOR_MQTT_INFO.subscribe_topic"),
            )
            
            # 设置自定义消息处理回调
            self.mqtt_client.client.on_message = self._on_mqtt_message
            
            # 连接MQTT服务器
            self.mqtt_client.connect()
            self.mqtt_client.start()
            print("[温度传感器] MQTT客户端已连接")
        except Exception as e:
            print(f"[温度传感器] MQTT连接失败: {e}")

    def _on_mqtt_message(self, client, userdata, msg):
        """处理MQTT消息"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            print(f"[温度传感器] 收到数据 - 主题: {topic}, 内容: {payload}")
            
            # 尝试将消息解析为JSON
            try:
                data = json.loads(payload)
                
                # 如果收到的是温度传感器数据
                if 'temperature' in data and 'humidity' in data:
                    # 更新温度和湿度
                    self.temperature = data.get('temperature')
                    self.humidity = data.get('humidity')
                    
                    # 处理时间戳 - 支持多种格式
                    timestamp = data.get('timestamp')
                    if timestamp is not None:
                        # 如果是字符串格式（ISO时间）
                        if isinstance(timestamp, str):
                            try:
                                # 尝试解析ISO格式的时间字符串
                                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                self.last_update_time = int(dt.timestamp())
                            except ValueError:
                                # 如果解析失败，使用当前时间
                                self.last_update_time = int(time.time())
                        else:
                            # 如果是数字，直接使用
                            self.last_update_time = int(timestamp)
                    else:
                        # 如果没有提供时间戳，使用当前时间
                        self.last_update_time = int(time.time())
                    
                    # 输出更新信息
                    update_time = time.strftime(
                        '%Y-%m-%d %H:%M:%S', 
                        time.localtime(self.last_update_time)
                    )
                    print(f"[温度传感器] 更新数据: 温度={self.temperature}°C, "
                          f"湿度={self.humidity}%, 时间={update_time}")
                    
            except json.JSONDecodeError:
                print(f"[温度传感器] 无法解析JSON消息: {payload}")
                
        except Exception as e:
            print(f"[温度传感器] 处理MQTT消息时出错: {e}")

    def _request_sensor_data(self):
        """请求所有传感器报告当前状态"""
        if self.mqtt_client:
            # 兼容两种命令格式
            command = {
                "command": "get_data",
                "action": "get_data",  # 增加action字段支持
                "timestamp": int(time.time())
            }
            self.mqtt_client.publish(json.dumps(command))
            print("[温度传感器] 已发送数据请求命令")
            
    def send_command(self, action_name, **kwargs):
        """发送命令到传感器"""
        if self.mqtt_client:
            command = {
                "command": action_name,
                "action": action_name,
                "timestamp": int(time.time())
            }
            # 添加任何额外参数
            command.update(kwargs)
            
            self.mqtt_client.publish(json.dumps(command))
            print(f"[温度传感器] 已发送命令: {action_name}")
            return True
        return False

    def get_temperature(self):
        return {"success": True, "message": f"[温度传感器] 更新数据: 温度={self.temperature}°C, "
                          f"湿度={self.humidity}%, 时间={self.last_update_time}"}

    def __del__(self):
        """析构函数，确保资源被正确释放"""
        if self.mqtt_client:
            try:
                self.mqtt_client.stop()
            except Exception:
                pass


# 测试代码
# if __name__ == "__main__":
#     # 创建温度传感器接收端实例
#     sensor = TemperatureSensor()
#
#     # 启动传感器接收
#     sensor.invoke({"method": "Start"})
#
#     try:
#         # 运行10分钟
#         print("温度传感器接收端已启动，等待接收数据...")
#         print("按Ctrl+C可停止程序")
#         print("也可以输入'send'发送数据请求命令")
#
#         while True:
#             cmd = input("> ")
#             if cmd.lower() == 'send':
#                 sensor.send_command("get_data")
#             elif cmd.lower() == 'quit' or cmd.lower() == 'exit':
#                 break
#             elif cmd.lower() == 'help':
#                 print("命令列表:")
#                 print("  send  - 发送数据请求命令")
#                 print("  quit  - 退出程序")
#                 print("  help  - 显示帮助")
#             time.sleep(0.1)
#
#     except KeyboardInterrupt:
#         print("\n程序被用户中断")
#     finally:
#         # 停止传感器接收
#         sensor.invoke({"method": "Stop"})