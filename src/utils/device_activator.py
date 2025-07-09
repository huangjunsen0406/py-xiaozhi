import asyncio
import json
from typing import Optional

import aiohttp

from src.utils.common_utils import handle_verification_code
from src.utils.device_fingerprint import DeviceFingerprint
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class DeviceActivator:
    """设备激活管理器 - 全异步版本"""

    def __init__(self, config_manager):
        """
        初始化设备激活器.
        """
        self.logger = get_logger(__name__)
        self.config_manager = config_manager
        # 使用device_fingerprint实例来管理设备身份
        self.device_fingerprint = DeviceFingerprint.get_instance()
        # 确保设备身份信息已创建
        self._ensure_device_identity()

        # 当前激活任务
        self._activation_task: Optional[asyncio.Task] = None

    def _ensure_device_identity(self):
        """
        确保设备身份信息已创建.
        """
        (
            serial_number,
            hmac_key,
            is_activated,
        ) = self.device_fingerprint.ensure_device_identity()
        self.logger.info(
            f"设备身份信息: 序列号: {serial_number}, 激活状态: {'已激活' if is_activated else '未激活'}"
        )

    def cancel_activation(self):
        """
        取消激活流程.
        """
        if self._activation_task and not self._activation_task.done():
            self.logger.info("正在取消激活任务")
            self._activation_task.cancel()

    def has_serial_number(self) -> bool:
        """
        检查是否有序列号.
        """
        return self.device_fingerprint.has_serial_number()

    def get_serial_number(self) -> str:
        """
        获取序列号.
        """
        return self.device_fingerprint.get_serial_number()

    def get_hmac_key(self) -> str:
        """
        获取HMAC密钥.
        """
        return self.device_fingerprint.get_hmac_key()

    def set_activation_status(self, status: bool) -> bool:
        """
        设置激活状态.
        """
        return self.device_fingerprint.set_activation_status(status)

    def is_activated(self) -> bool:
        """
        检查设备是否已激活.
        """
        return self.device_fingerprint.is_activated()

    def generate_hmac(self, challenge: str) -> str:
        """
        使用HMAC密钥生成签名.
        """
        return self.device_fingerprint.generate_hmac(challenge)

    async def process_activation(self, activation_data: dict) -> bool:
        """异步处理激活流程.

        Args:
            activation_data: 包含激活信息的字典，至少应该包含challenge和code

        Returns:
            bool: 激活是否成功
        """
        try:
            # 记录当前任务
            self._activation_task = asyncio.current_task()

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

                # 使用device_fingerprint生成序列号和HMAC密钥
                (
                    serial_number,
                    hmac_key,
                    _,
                ) = self.device_fingerprint.ensure_device_identity()

                if serial_number and hmac_key:
                    self.logger.info("已自动创建设备序列号和HMAC密钥")
                else:
                    self.logger.error("创建序列号或HMAC密钥失败")
                    return False

            # 显示激活信息给用户
            self.logger.info(f"激活提示: {message}")
            self.logger.info(f"验证码: {code}")

            # 构建验证码提示文本并打印
            text = f".请登录到控制面板添加设备，输入验证码：{' '.join(code)}..."
            print("\n==================")
            print(text)
            print("==================\n")
            handle_verification_code(text)

            # 使用语音播放验证码
            try:
                # 在非阻塞的线程中播放语音
                from src.utils.common_utils import play_audio_nonblocking

                play_audio_nonblocking(text)
                self.logger.info("正在播放验证码语音提示")
            except Exception as e:
                self.logger.error(f"播放验证码语音失败: {e}")

            # 尝试激活设备，传递验证码信息
            return await self.activate(challenge, code)

        except asyncio.CancelledError:
            self.logger.info("激活流程被取消")
            return False

    async def activate(self, challenge: str, code: str = None) -> bool:
        """异步执行激活流程.

        Args:
            challenge: 服务器发送的挑战字符串
            code: 验证码，用于重试时播放

        Returns:
            bool: 激活是否成功
        """
        try:
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
                    "hmac": hmac_signature,
                }
            }

            # 获取激活URL
            ota_url = self.config_manager.get_config(
                "SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL"
            )
            if not ota_url:
                self.logger.error("未找到OTA URL配置")
                return False

            # 确保URL以斜杠结尾
            if not ota_url.endswith("/"):
                ota_url += "/"

            activate_url = f"{ota_url}activate"
            self.logger.info(f"激活URL: {activate_url}")

            # 设置请求头
            headers = {
                "Activation-Version": "2",
                "Device-Id": self.config_manager.get_config("SYSTEM_OPTIONS.DEVICE_ID"),
                "Client-Id": self.config_manager.get_config("SYSTEM_OPTIONS.CLIENT_ID"),
                "Content-Type": "application/json",
            }

            # 打印调试信息
            self.logger.debug(f"请求头: {headers}")
            payload_str = json.dumps(payload, indent=2, ensure_ascii=False)
            self.logger.debug(f"请求负载: {payload_str}")

            # 重试逻辑
            max_retries = 60  # 最长等待5分钟
            retry_interval = 5  # 设置5秒的重试间隔

            error_count = 0
            last_error = None

            # 创建aiohttp会话，设置合理的超时时间
            timeout = aiohttp.ClientTimeout(total=10)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                for attempt in range(max_retries):
                    try:
                        self.logger.info(
                            f"尝试激活 (尝试 {attempt + 1}/{max_retries})..."
                        )

                        # 每次重试时播放验证码（从第2次开始）
                        if attempt > 0 and code:
                            try:
                                from src.utils.common_utils import (
                                    play_audio_nonblocking,
                                )

                                text = f".请登录到控制面板添加设备，输入验证码：{' '.join(code)}..."
                                play_audio_nonblocking(text)
                                self.logger.info(f"重试播放验证码: {code}")
                            except Exception as e:
                                self.logger.error(f"重试播放验证码失败: {e}")

                        # 发送激活请求
                        async with session.post(
                            activate_url, headers=headers, json=payload
                        ) as response:
                            # 读取响应
                            response_text = await response.text()

                            # 打印完整响应
                            self.logger.warning(f"\n激活响应 (HTTP {response.status}):")
                            try:
                                response_json = json.loads(response_text)
                                self.logger.warning(json.dumps(response_json, indent=2))
                            except json.JSONDecodeError:
                                self.logger.warning(response_text)

                            # 检查响应状态码
                            if response.status == 200:
                                # 激活成功
                                self.logger.info("设备激活成功!")
                                self.set_activation_status(True)
                                return True

                            elif response.status == 202:
                                # 等待用户输入验证码
                                self.logger.info("等待用户输入验证码，继续等待...")

                                # 使用可取消的等待
                                await asyncio.sleep(retry_interval)

                            else:
                                # 处理其他错误但继续重试
                                error_msg = "未知错误"
                                try:
                                    error_data = json.loads(response_text)
                                    error_msg = error_data.get(
                                        "error", f"未知错误 (状态码: {response.status})"
                                    )
                                except json.JSONDecodeError:
                                    error_msg = (
                                        f"服务器返回错误 (状态码: {response.status})"
                                    )

                                # 记录错误但不终止流程
                                if error_msg != last_error:
                                    self.logger.warning(
                                        f"服务器返回: {error_msg}，继续等待验证码激活"
                                    )
                                    last_error = error_msg

                                # 计数连续相同错误
                                if "Device not found" in error_msg:
                                    error_count += 1
                                    if error_count >= 5 and error_count % 5 == 0:
                                        self.logger.warning(
                                            "\n提示: 如果错误持续出现，可能需要在网站上刷新页面获取新验证码\n"
                                        )

                                # 使用可取消的等待
                                await asyncio.sleep(retry_interval)

                    except asyncio.CancelledError:
                        # 响应取消信号
                        self.logger.info("激活流程被取消")
                        return False

                    except aiohttp.ClientError as e:
                        self.logger.warning(f"网络请求失败: {e}，重试中...")
                        await asyncio.sleep(retry_interval)

                    except asyncio.TimeoutError as e:
                        self.logger.warning(f"请求超时: {e}，重试中...")
                        await asyncio.sleep(retry_interval)

                    except Exception as e:
                        # 获取异常的详细信息
                        import traceback

                        error_detail = (
                            str(e) if str(e) else f"{type(e).__name__}: 未知错误"
                        )
                        self.logger.warning(
                            f"激活过程中发生错误: {error_detail}，重试中..."
                        )
                        # 调试模式下打印完整的异常信息
                        self.logger.debug(f"完整异常信息: {traceback.format_exc()}")
                        await asyncio.sleep(retry_interval)

            # 达到最大重试次数
            self.logger.error(
                f"激活失败，达到最大重试次数 ({max_retries})，最后错误: {last_error}"
            )
            return False

        except asyncio.CancelledError:
            self.logger.info("激活流程被取消")
            return False
