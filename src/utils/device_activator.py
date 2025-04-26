import json
import hashlib
import hmac
import time
import requests
import uuid
from pathlib import Path

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class DeviceActivator:
    """设备激活管理器 - 与ConfigManager配合使用"""

    def __init__(self, config_manager):
        """初始化设备激活器"""
        self.logger = get_logger(__name__)
        self.config_manager = config_manager
        self.efuse_file = Path(__file__).parent.parent.parent / "config" / "efuse.json"
        self._ensure_efuse_file()

    def _ensure_efuse_file(self):
        """确保efuse文件存在"""
        if not self.efuse_file.exists():
            # 创建默认efuse数据
            default_data = {
                "serial_number": None,
                "hmac_key": None,
                "activation_status": False
            }

            # 确保目录存在
            self.efuse_file.parent.mkdir(parents=True, exist_ok=True)

            # 写入默认数据
            with open(self.efuse_file, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"已创建efuse配置文件: {self.efuse_file}")

    def _load_efuse_data(self) -> dict:
        """加载efuse数据"""
        try:
            with open(self.efuse_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"加载efuse数据失败: {e}")
            return {
                "serial_number": None,
                "hmac_key": None,
                "activation_status": False
            }

    def _save_efuse_data(self, data: dict) -> bool:
        """保存efuse数据"""
        try:
            with open(self.efuse_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self.logger.error(f"保存efuse数据失败: {e}")
            return False

    def has_serial_number(self) -> bool:
        """检查是否有序列号"""
        efuse_data = self._load_efuse_data()
        return efuse_data.get("serial_number") is not None

    def get_serial_number(self) -> str:
        """获取序列号"""
        efuse_data = self._load_efuse_data()
        return efuse_data.get("serial_number")

    def burn_serial_number(self, serial_number: str) -> bool:
        """烧录序列号到模拟efuse"""
        efuse_data = self._load_efuse_data()

        # 检查是否已有序列号
        if efuse_data.get("serial_number") is not None:
            self.logger.warning("已存在序列号，无法重新烧录")
            return False

        # 更新序列号
        efuse_data["serial_number"] = serial_number
        result = self._save_efuse_data(efuse_data)

        if result:
            self.logger.info(f"序列号 {serial_number} 已成功烧录")

        return result

    def burn_hmac_key(self, hmac_key: str) -> bool:
        """烧录HMAC密钥到模拟efuse"""
        efuse_data = self._load_efuse_data()

        # 检查是否已有HMAC密钥
        if efuse_data.get("hmac_key") is not None:
            self.logger.warning("已存在HMAC密钥，无法重新烧录")
            return False

        # 更新HMAC密钥
        efuse_data["hmac_key"] = hmac_key
        result = self._save_efuse_data(efuse_data)

        if result:
            self.logger.info("HMAC密钥已成功烧录")

        return result

    def get_hmac_key(self) -> str:
        """获取HMAC密钥"""
        efuse_data = self._load_efuse_data()
        return efuse_data.get("hmac_key")

    def set_activation_status(self, status: bool) -> bool:
        """设置激活状态"""
        efuse_data = self._load_efuse_data()
        efuse_data["activation_status"] = status
        return self._save_efuse_data(efuse_data)

    def is_activated(self) -> bool:
        """检查设备是否已激活"""
        efuse_data = self._load_efuse_data()
        return efuse_data.get("activation_status", False)

    def generate_hmac(self, challenge: str) -> str:
        """使用HMAC密钥生成签名"""
        hmac_key = self.get_hmac_key()

        if not hmac_key:
            self.logger.error("未找到HMAC密钥，无法生成签名")
            return None

        try:
            # 计算HMAC-SHA256签名
            signature = hmac.new(
                hmac_key.encode(),
                challenge.encode(),
                hashlib.sha256
            ).hexdigest()

            return signature
        except Exception as e:
            self.logger.error(f"生成HMAC签名失败: {e}")
            return None

    def process_activation(self, activation_data: dict) -> bool:
        """
        处理激活流程

        Args:
            activation_data: 包含激活信息的字典，至少应该包含challenge和code

        Returns:
            bool: 激活是否成功
        """
        # 检查是否有激活挑战和验证码
        if not activation_data.get("challenge"):
            self.logger.error("激活数据中缺少challenge字段")
            return False

        if not activation_data.get("code"):
            self.logger.error("激活数据中缺少code字段")
            return False

        challenge = activation_data["challenge"]
        code = activation_data["code"]
        message = activation_data.get("message", "请在xiaozhi.me输入验证码")

        # 检查序列号
        if not self.has_serial_number():
            self.logger.error("设备没有序列号，无法进行激活")
            print("\n错误: 设备没有序列号，无法进行激活。请确保efuse.json文件已正确创建")
            print("正在重新创建efuse.json文件并重新尝试...")

            # 尝试创建序列号和HMAC密钥
            serial_number = f"SN-{uuid.uuid4().hex[:16].upper()}"
            hmac_key = uuid.uuid4().hex

            success1 = self.burn_serial_number(serial_number)
            success2 = self.burn_hmac_key(hmac_key)

            if success1 and success2:
                self.logger.info("已自动创建设备序列号和HMAC密钥")
                print(f"已自动创建设备序列号: {serial_number}")
            else:
                self.logger.error("创建序列号或HMAC密钥失败")
                return False

        # 显示激活信息给用户
        self.logger.info(f"激活提示: {message}")
        self.logger.info(f"验证码: {code}")
        print("\n==================")
        print(f"请登录到控制面板添加设备，输入验证码：{code}")
        print("==================\n")

        # 尝试激活设备
        return self.activate(challenge)

    def activate(self, challenge: str) -> bool:
        """
        执行激活流程

        Args:
            challenge: 服务器发送的挑战字符串

        Returns:
            bool: 激活是否成功
        """
        # 检查序列号
        serial_number = self.get_serial_number()
        if not serial_number:
            self.logger.error("设备没有序列号，无法完成HMAC验证步骤")
            return False

        # 计算HMAC签名
        hmac_signature = self.generate_hmac(challenge)
        if not hmac_signature:
            self.logger.error("无法生成HMAC签名，激活失败")
            return False

        # 包装一层外部payload，符合服务器期望格式
        payload = {
            "Payload": {
                "algorithm": "hmac-sha256",
                "serial_number": serial_number,
                "challenge": challenge,
                "hmac": hmac_signature
            }
        }

        # 获取激活URL
        ota_url = self.config_manager.get_config(
            "SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL")
        if not ota_url:
            self.logger.error("未找到OTA URL配置")
            return False

        # 确保URL以斜杠结尾
        if not ota_url.endswith('/'):
            ota_url += '/'

        activate_url = f"{ota_url}activate"

        # 获取激活版本设置
        activation_version_setting = self.config_manager.get_config(
            "SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION", "v2")

        # 确定使用哪个版本的激活协议
        if activation_version_setting in ["v1", "1"]:
            activation_version = "1"
        else:
            activation_version = "2"

        self.logger.info(f"OTA请求使用激活版本: {activation_version} "
                         f"(配置值: {activation_version_setting})")

        # 设置请求头
        headers = {
            "Activation-Version": activation_version,
            "Device-Id": self.config_manager.get_config("SYSTEM_OPTIONS.DEVICE_ID"),
            "Client-Id": self.config_manager.get_config("SYSTEM_OPTIONS.CLIENT_ID"),
            "Content-Type": "application/json"
        }

        # 重试逻辑
        max_retries = 60  # 增加重试次数，最长等待5分钟
        retry_interval = 5  # 设置5秒的重试间隔

        error_count = 0
        last_error = None

        for attempt in range(max_retries):
            try:
                self.logger.info(f"尝试激活 (尝试 {attempt + 1}/{max_retries})...")

                # 发送激活请求
                response = requests.post(
                    activate_url,
                    headers=headers,
                    json=payload,
                    timeout=10
                )

                # 打印完整响应
                print(f"\n激活响应 (HTTP {response.status_code}):")
                try:
                    response_json = response.json()
                    print(json.dumps(response_json, indent=2))

                    # 保存激活请求和响应到文件
                    try:
                        log_dir = Path("logs")
                        log_dir.mkdir(exist_ok=True)

                        # 保存激活请求
                        with open(log_dir / "activate_request.json", "w", encoding="utf-8") as f:
                            request_data = {
                                "url": activate_url,
                                "headers": headers,
                                "payload": payload
                            }
                            json.dump(request_data, f, indent=4, ensure_ascii=False)

                        # 保存激活响应
                        with open(log_dir / "activate_response.json", "w", encoding="utf-8") as f:
                            json.dump(response_json, f, indent=4, ensure_ascii=False)

                        self.logger.info("激活请求和响应已保存到logs目录")
                    except Exception as e:
                        self.logger.error(f"保存激活日志失败: {e}")

                except Exception:
                    print(response.text)

                # 检查响应状态码
                if response.status_code == 200:
                    # 激活成功
                    self.logger.info("设备激活成功!")
                    print("\n*** 设备激活成功! ***\n")
                    self.set_activation_status(True)
                    return True
                elif response.status_code == 202:
                    # 等待用户输入验证码
                    self.logger.info("等待用户输入验证码，继续等待...")
                    print("\n等待用户在网站输入验证码，继续等待...\n")
                    time.sleep(retry_interval)
                else:
                    # 处理其他错误但继续重试
                    error_msg = "未知错误"
                    try:
                        error_data = response.json()
                        error_msg = error_data.get(
                            'error',
                            f"未知错误 (状态码: {response.status_code})"
                        )
                    except Exception:
                        error_msg = f"服务器返回错误 (状态码: {response.status_code})"

                    # 记录错误但不终止流程
                    if error_msg != last_error:
                        # 只在错误消息改变时记录，避免重复日志
                        self.logger.warning(f"服务器返回: {error_msg}，继续等待验证码激活")
                        print(f"\n服务器返回: {error_msg}，继续等待验证码激活...\n")
                        last_error = error_msg

                    # 计数连续相同错误
                    if "Device not found" in error_msg:
                        error_count += 1
                        if error_count >= 5 and error_count % 5 == 0:
                            # 每5次相同错误，提示用户可能需要重新获取验证码
                            print("\n提示: 如果错误持续出现，可能需要在网站上刷新页面获取新验证码\n")

                    time.sleep(retry_interval)

            except requests.Timeout:
                time.sleep(retry_interval)
            except Exception as e:
                self.logger.warning(f"激活过程中发生错误: {e}，重试中...")
                print(f"激活过程中发生错误: {e}，重试中...")
                time.sleep(retry_interval)

        # 只有在达到最大重试次数后才真正失败
        self.logger.error(f"激活失败，达到最大重试次数 ({max_retries})，最后错误: {last_error}")
        print("\n激活失败，达到最大等待时间，请重新获取验证码并尝试激活\n")
        return False 