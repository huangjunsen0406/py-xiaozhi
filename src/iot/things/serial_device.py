import serial
import threading
from src.iot.thing import Thing
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class SerialDevice:
    """
    串口设备基类
    
    提供基本的串口通信功能，包括打开、关闭、发送和接收数据
    """
    def __init__(self, port="/dev/ttyUSB0", baudrate=115200, timeout=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.read_thread = None
        self.read_callback = None
        self._running = False

    def open(self):
        """打开串口连接并启动读取线程"""
        try:
            self.ser = serial.Serial(
                self.port, 
                self.baudrate, 
                timeout=self.timeout
            )
            self._running = True
            logger.info(f"[SerialDevice] 打开串口: {self.port} 成功")

            self.read_thread = threading.Thread(
                target=self._read_loop, 
                daemon=True
            )
            self.read_thread.start()
        except serial.SerialException as e:
            logger.error(f"[SerialDevice] 串口打开失败: {e}")
        except Exception as e:
            logger.error(f"[SerialDevice] 串口打开时出现未知错误: {e}")

    def _read_loop(self):
        """内部方法：持续读取串口数据的循环"""
        while self._running and self.ser and self.ser.is_open:
            try:
                line = self.ser.readline().decode(
                    'utf-8', 
                    errors='ignore'
                ).strip()
                if line and self.read_callback:
                    self.read_callback(line)
            except Exception as e:
                logger.error(f"[SerialDevice] 串口读取错误: {e}")

    def set_read_callback(self, callback):
        """设置接收数据回调函数"""
        self.read_callback = callback

    def send(self, data: str):
        """发送数据到串口设备"""
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(data.encode('utf-8'))
                logger.info(f"[SerialDevice] 发送: {data.strip()}")
                return True
            except Exception as e:
                logger.error(f"[SerialDevice] 发送失败: {e}")
                return False
        else:
            logger.error("[SerialDevice] 串口未打开，无法发送数据")
            return False

    def close(self):
        """关闭串口连接"""
        self._running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info(f"[SerialDevice] 串口 {self.port} 已关闭")


class SerialPort(Thing):
    """
    串口通信物联网设备
    
    提供串口通信功能，可通过Thing接口调用相关方法
    """
    def __init__(self, serial_dev: SerialDevice = None):
        super().__init__("SerialPort", "串口通信")
        
        # 设备状态属性
        self.is_connected = False
        self.last_command = ""
        
        self.serial_dev = serial_dev if serial_dev else SerialDevice()

        # 添加设备属性
        self.add_property(
            "is_connected", 
            "是否已连接", 
            lambda: self.is_connected
        )
        self.add_property(
            "last_command", 
            "最后一次发送的命令", 
            lambda: self.last_command
        )

        # 尝试打开串口
        try:
            self.serial_dev.open()
            self.is_connected = (self.serial_dev.ser and 
                                 self.serial_dev.ser.is_open)
        except Exception as e:
            logger.error(f"[SerialPort] 串口初始化失败: {e}")
            self.is_connected = False

        logger.info("[SerialPort] 串口初始化完成")

        # 定义控制方法
        self.add_method("ForwardMovement", "前进", [],
                        lambda params: self._send_command("w\n"))
        self.add_method("StopMovement", "停止", [],
                        lambda params: self._send_command("q\n"))
        self.add_method("BackwardMovement", "后退", [],
                        lambda params: self._send_command("s\n"))
        self.add_method("DriveLookLeft", "左转", [],
                        lambda params: self._send_command("a\n"))
        self.add_method("DriveLookRight", "右转", [],
                        lambda params: self._send_command("d\n"))
        self.add_method("Dance", "跳舞", [],
                        lambda params: self._send_command("M1\n"))
        self.add_method("StopDance", "停止跳舞", [],
                        lambda params: self._send_command("M0\n"))

    def _send_command(self, command: str):
        """
        发送命令并返回标准响应格式
        
        Args:
            command: 要发送的命令字符串
            
        Returns:
            Dict: 包含status和message的字典
        """
        self.last_command = command.strip()
        success = self.serial_dev.send(command)
        
        if success:
            logger.info(f"[SerialPort] 命令 '{command.strip()}' 发送成功")
            return {
                "status": "success", 
                "message": f"命令 '{command.strip()}' 已发送"
            }
        else:
            logger.error(f"[SerialPort] 命令 '{command.strip()}' 发送失败")
            return {
                "status": "error", 
                "message": f"命令 '{command.strip()}' 发送失败"
            }
