# -*- coding: utf-8 -*-
"""
统一激活服务
"""

import asyncio
import hashlib
import hmac
import json
import platform
import socket
import ssl
from pathlib import Path
from typing import Dict, Optional, Tuple, TypedDict

import aiohttp
import machineid
import psutil

from src.constants.system import SystemConstants
from src.logging import get_logger
from src.utils.config_manager import ConfigManager
from src.utils.resource_finder import get_config_dir

logger = get_logger()


class ActivationResult(TypedDict, total=False):
    """激活结果类型."""

    success: bool
    need_activation_ui: bool
    message: str
    error: str
    local_activated: bool
    server_activated: bool
    status_consistent: bool
    activation_version: str


class ActivationService:
    """
    统一激活服务.
    """

    _instance: Optional["ActivationService"] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self.logger = get_logger()
        self._initialized = False

        # 配置管理器
        self.config_manager = ConfigManager.get_instance()

        # 设备身份相关
        self._efuse_cache: Optional[Dict] = None
        self._efuse_file: Optional[Path] = None
        self._system = platform.system()

        # 激活状态
        self._activation_data: Optional[Dict] = None
        self._activation_status = {
            "local_activated": False,
            "server_activated": False,
            "status_consistent": True,
        }

        # 激活流程控制
        self._activation_task: Optional[asyncio.Task] = None
        self._is_activating = False

        # OTA相关
        self._local_ip: Optional[str] = None

    @classmethod
    async def get_instance(cls) -> "ActivationService":
        """获取单例实例（异步）."""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    instance = cls()
                    await instance._async_init()
                    cls._instance = instance
        return cls._instance

    @classmethod
    def get_instance_sync(cls) -> "ActivationService":
        """获取单例实例（同步，用于已初始化后）."""
        if cls._instance is None:
            raise RuntimeError("ActivationService 尚未初始化，请先调用 get_instance()")
        return cls._instance

    async def _async_init(self):
        """异步初始化."""
        if self._initialized:
            return

        # 初始化文件路径
        self._init_file_paths()

        # 确保设备身份信息
        self._ensure_efuse_file()

        # 获取本地IP
        self._local_ip = await self._get_local_ip()

        self._initialized = True
        self.logger.info("ActivationService 初始化完成")

    # ========== 公共接口 ==========

    async def initialize(self) -> ActivationResult:
        """
        初始化设备并检查激活状态.

        Returns:
            ActivationResult: 初始化结果
        """
        self.logger.info("开始系统初始化流程")

        try:
            # 1. 确保设备身份
            serial_number, hmac_key, is_activated = self._ensure_device_identity()
            self._activation_status["local_activated"] = is_activated

            self.logger.info(f"设备序列号: {serial_number}")
            self.logger.info(f"本地激活状态: {'已激活' if is_activated else '未激活'}")

            # 2. 初始化配置
            self._initialize_config()

            # 3. 获取OTA配置
            ota_result = await self._fetch_ota_config()

            # 4. 获取激活版本
            activation_version = self.config_manager.get_config(
                "SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION", "v1"
            )
            self.logger.info(f"激活版本: {activation_version}")

            # 5. 根据激活版本决定流程
            if activation_version == "v1":
                self.logger.info("v1协议：无需激活流程")
                return ActivationResult(
                    success=True,
                    need_activation_ui=False,
                    message="v1协议初始化完成",
                    local_activated=True,
                    server_activated=True,
                    status_consistent=True,
                    activation_version=activation_version,
                )

            # v2协议：分析激活状态
            result = self._analyze_activation_status()
            result["activation_version"] = activation_version
            return result

        except Exception as e:
            self.logger.error(f"系统初始化失败: {e}")
            return ActivationResult(
                success=False,
                need_activation_ui=False,
                message="初始化失败",
                error=str(e),
            )

    async def activate(self, activation_data: Optional[Dict] = None) -> bool:
        """
        执行激活流程.

        Args:
            activation_data: 激活数据，如果为空则使用缓存的数据

        Returns:
            bool: 激活是否成功
        """
        data = activation_data or self._activation_data
        if not data:
            self.logger.error("没有激活数据")
            return False

        challenge = data.get("challenge")
        code = data.get("code")

        if not challenge or not code:
            self.logger.error("激活数据缺少必要字段")
            return False

        try:
            self._is_activating = True
            self._activation_task = asyncio.current_task()

            # 显示激活信息
            self._show_activation_info(data)

            # 执行激活
            return await self._do_activate(challenge, code)

        except asyncio.CancelledError:
            self.logger.info("激活流程被取消")
            return False
        finally:
            self._is_activating = False
            self._activation_task = None

    def cancel_activation(self):
        """取消激活流程."""
        if self._activation_task and not self._activation_task.done():
            self.logger.info("正在取消激活任务")
            self._activation_task.cancel()

    def get_device_info(self) -> Dict:
        """获取设备信息."""
        efuse_data = self._load_efuse_data()
        return {
            "serial_number": efuse_data.get("serial_number"),
            "mac_address": efuse_data.get("mac_address"),
        }

    def get_serial_number(self) -> Optional[str]:
        """获取序列号."""
        return self._load_efuse_data().get("serial_number")

    def get_mac_address(self) -> Optional[str]:
        """获取MAC地址."""
        return self._load_efuse_data().get("mac_address")

    def get_activation_status(self) -> Dict:
        """获取激活状态."""
        return self._activation_status.copy()

    def get_activation_data(self) -> Optional[Dict]:
        """获取激活数据."""
        return self._activation_data

    def is_activated(self) -> bool:
        """检查是否已激活."""
        return self._load_efuse_data().get("activation_status", False)

    def is_activating(self) -> bool:
        """检查是否正在激活."""
        return self._is_activating

    def get_config_manager(self) -> ConfigManager:
        """获取配置管理器."""
        return self.config_manager

    # ========== 设备身份管理（私有方法） ==========

    def _init_file_paths(self):
        """初始化文件路径."""
        config_dir = get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        self._efuse_file = config_dir / "efuse.json"
        self.logger.debug(f"efuse文件路径: {self._efuse_file}")

    def _ensure_efuse_file(self):
        """确保efuse文件存在且完整."""
        fingerprint = self._generate_fresh_fingerprint()
        mac_address = fingerprint.get("mac_address")

        if not self._efuse_file.exists():
            self.logger.info("创建efuse.json文件")
            self._create_efuse_file(fingerprint, mac_address)
        else:
            self._validate_efuse_file(fingerprint, mac_address)

    def _create_efuse_file(self, fingerprint: Dict, mac_address: Optional[str]):
        """创建efuse文件."""
        serial_number = self._generate_serial_number_from_fingerprint(fingerprint)
        hmac_key = self._generate_hmac_key_from_fingerprint(fingerprint)

        efuse_data = {
            "mac_address": mac_address,
            "serial_number": serial_number,
            "hmac_key": hmac_key,
            "activation_status": False,
            "device_fingerprint": fingerprint,
        }

        self._save_efuse_data(efuse_data)
        self.logger.info(f"已创建efuse配置: 序列号={serial_number}")

    def _validate_efuse_file(self, fingerprint: Dict, mac_address: Optional[str]):
        """验证并修复efuse文件."""
        try:
            efuse_data = self._load_efuse_data_from_file()
            required_fields = ["mac_address", "serial_number", "hmac_key", "activation_status"]
            missing = [f for f in required_fields if f not in efuse_data]

            if missing:
                self.logger.warning(f"efuse缺少字段: {missing}")
                for field in missing:
                    if field == "mac_address":
                        efuse_data[field] = mac_address
                    elif field == "serial_number":
                        efuse_data[field] = self._generate_serial_number_from_fingerprint(fingerprint)
                    elif field == "hmac_key":
                        efuse_data[field] = self._generate_hmac_key_from_fingerprint(fingerprint)
                    elif field == "activation_status":
                        efuse_data[field] = False
                self._save_efuse_data(efuse_data)
            else:
                self._efuse_cache = efuse_data

        except Exception as e:
            self.logger.error(f"验证efuse失败: {e}，重新创建")
            self._create_efuse_file(fingerprint, mac_address)

    def _ensure_device_identity(self) -> Tuple[Optional[str], Optional[str], bool]:
        """确保设备身份信息，返回 (序列号, HMAC密钥, 是否激活)."""
        efuse_data = self._load_efuse_data()
        return (
            efuse_data.get("serial_number"),
            efuse_data.get("hmac_key"),
            efuse_data.get("activation_status", False),
        )

    def _generate_fresh_fingerprint(self) -> Dict:
        """生成新的设备指纹."""
        return {
            "system": self._system,
            "hostname": platform.node(),
            "mac_address": self._get_primary_mac_address(),
            "machine_id": self._get_machine_id(),
        }

    def _get_primary_mac_address(self) -> Optional[str]:
        """获取主要网卡MAC地址."""
        try:
            for iface, addrs in psutil.net_if_addrs().items():
                if iface.lower().startswith(("lo", "loopback")):
                    continue
                for snic in addrs:
                    if snic.family == psutil.AF_LINK and snic.address:
                        mac = self._normalize_mac(snic.address)
                        if mac != "00:00:00:00:00:00":
                            return mac
        except Exception as e:
            self.logger.error(f"获取MAC地址失败: {e}")
        return None

    def _normalize_mac(self, mac: str) -> str:
        """标准化MAC地址格式."""
        clean = "".join(c for c in mac if c.isalnum())
        if len(clean) != 12:
            return mac.lower()
        return ":".join(clean[i:i+2] for i in range(0, 12, 2)).lower()

    def _get_machine_id(self) -> Optional[str]:
        """获取机器ID."""
        try:
            return machineid.id()
        except Exception:
            return None

    def _generate_serial_number_from_fingerprint(self, fingerprint: Dict) -> str:
        """从指纹生成序列号."""
        mac = fingerprint.get("mac_address")
        if mac:
            mac_clean = mac.lower().replace(":", "")
            short_hash = hashlib.md5(mac_clean.encode()).hexdigest()[:8].upper()
            return f"SN-{short_hash}-{mac_clean}"

        machine_id = fingerprint.get("machine_id")
        hostname = fingerprint.get("hostname")
        identifier = (machine_id or hostname or "unknown")[:12]
        short_hash = hashlib.md5(identifier.encode()).hexdigest()[:8].upper()
        return f"SN-{short_hash}-{identifier.upper()}"

    def _generate_hmac_key_from_fingerprint(self, fingerprint: Dict) -> str:
        """从指纹生成HMAC密钥."""
        identifiers = []
        for key in ["hostname", "mac_address", "machine_id"]:
            if fingerprint.get(key):
                identifiers.append(fingerprint[key])
        if not identifiers:
            identifiers.append(self._system)
        return hashlib.sha256("||".join(identifiers).encode()).hexdigest()

    def _generate_hmac_signature(self, challenge: str) -> Optional[str]:
        """生成HMAC签名."""
        hmac_key = self._load_efuse_data().get("hmac_key")
        if not hmac_key or not challenge:
            return None
        return hmac.new(hmac_key.encode(), challenge.encode(), hashlib.sha256).hexdigest()

    def _set_activation_status(self, status: bool) -> bool:
        """设置激活状态."""
        efuse_data = self._load_efuse_data()
        efuse_data["activation_status"] = status
        return self._save_efuse_data(efuse_data)

    def _load_efuse_data(self) -> Dict:
        """加载efuse数据（带缓存）."""
        if self._efuse_cache is not None:
            return self._efuse_cache
        try:
            return self._load_efuse_data_from_file()
        except Exception:
            return {"activation_status": False}

    def _load_efuse_data_from_file(self) -> Dict:
        """从文件加载efuse数据."""
        with open(self._efuse_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            self._efuse_cache = data
            return data

    def _save_efuse_data(self, data: Dict) -> bool:
        """保存efuse数据."""
        try:
            self._efuse_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._efuse_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._efuse_cache = data
            return True
        except Exception as e:
            self.logger.error(f"保存efuse失败: {e}")
            return False

    # ========== 配置初始化（私有方法） ==========

    def _initialize_config(self):
        """初始化配置."""
        # 确保CLIENT_ID存在
        self.config_manager.initialize_client_id()

        # 从设备身份初始化DEVICE_ID
        device_id = self.config_manager.get_config("SYSTEM_OPTIONS.DEVICE_ID")
        if not device_id:
            mac = self.get_mac_address()
            if mac:
                self.config_manager.update_config("SYSTEM_OPTIONS.DEVICE_ID", mac)
                self.logger.info(f"已设置DEVICE_ID: {mac}")

        self.logger.info(f"CLIENT_ID: {self.config_manager.get_config('SYSTEM_OPTIONS.CLIENT_ID')}")
        self.logger.info(f"DEVICE_ID: {self.config_manager.get_config('SYSTEM_OPTIONS.DEVICE_ID')}")

    # ========== OTA配置获取（私有方法） ==========

    async def _get_local_ip(self) -> str:
        """获取本机IP."""
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._sync_get_ip)
        except Exception:
            return "127.0.0.1"

    def _sync_get_ip(self) -> str:
        """同步获取IP."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]

    async def _fetch_ota_config(self) -> Dict:
        """获取OTA配置."""
        ota_url = self.config_manager.get_config("SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL")
        device_id = self.config_manager.get_config("SYSTEM_OPTIONS.DEVICE_ID")

        if not ota_url or not device_id:
            raise ValueError("OTA URL 或 DEVICE_ID 未配置")

        headers = self._build_ota_headers()
        payload = self._build_ota_payload()

        self.logger.debug(f"OTA请求: {ota_url}")

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        timeout = aiohttp.ClientTimeout(total=10)
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            async with session.post(ota_url, headers=headers, json=payload) as response:
                if response.status != 200:
                    raise ValueError(f"OTA服务器返回错误: {response.status}")

                data = await response.json()
                self._process_ota_response(data)
                return data

    def _build_ota_headers(self) -> Dict:
        """构建OTA请求头."""
        headers = {
            "Device-Id": self.config_manager.get_config("SYSTEM_OPTIONS.DEVICE_ID"),
            "Client-Id": self.config_manager.get_config("SYSTEM_OPTIONS.CLIENT_ID"),
            "Content-Type": "application/json",
            "User-Agent": f"{SystemConstants.BOARD_TYPE}/{SystemConstants.APP_NAME}-{SystemConstants.APP_VERSION}",
            "Accept-Language": "zh-CN",
        }

        activation_version = self.config_manager.get_config(
            "SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION", "v1"
        )
        if activation_version == "v2":
            headers["Activation-Version"] = SystemConstants.APP_VERSION

        return headers

    def _build_ota_payload(self) -> Dict:
        """构建OTA请求体."""
        hmac_key = self._load_efuse_data().get("hmac_key", "unknown")
        return {
            "application": {
                "version": SystemConstants.APP_VERSION,
                "elf_sha256": hmac_key,
            },
            "board": {
                "type": SystemConstants.BOARD_TYPE,
                "name": SystemConstants.APP_NAME,
                "ip": self._local_ip,
                "mac": self.config_manager.get_config("SYSTEM_OPTIONS.DEVICE_ID"),
            },
        }

    def _process_ota_response(self, data: Dict):
        """处理OTA响应."""
        # 更新MQTT配置
        if "mqtt" in data and data["mqtt"]:
            self.config_manager.update_config("SYSTEM_OPTIONS.NETWORK.MQTT_INFO", data["mqtt"])
            self.logger.info("MQTT配置已更新")

        # 更新WebSocket配置
        if "websocket" in data:
            ws = data["websocket"]
            if ws.get("url"):
                self.config_manager.update_config("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL", ws["url"])
                self.logger.info(f"WebSocket URL: {ws['url']}")
            token = ws.get("token", "test-token") or "test-token"
            self.config_manager.update_config("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN", token)

        # 检查激活数据
        if "activation" in data:
            self.logger.info("检测到激活数据，设备需要激活")
            self._activation_data = data["activation"]
            self._activation_status["server_activated"] = False
        else:
            self.logger.info("无激活数据，设备已授权")
            self._activation_data = None
            self._activation_status["server_activated"] = True

    # ========== 激活状态分析（私有方法） ==========

    def _analyze_activation_status(self) -> ActivationResult:
        """分析激活状态."""
        local = self._activation_status["local_activated"]
        server = self._activation_status["server_activated"]
        consistent = local == server
        self._activation_status["status_consistent"] = consistent

        self.logger.info(f"激活状态分析: 本地={local}, 服务器={server}")

        # 情况1: 都未激活 - 需要激活
        if not local and not server:
            return ActivationResult(
                success=True,
                need_activation_ui=True,
                message="设备需要激活",
                local_activated=local,
                server_activated=server,
                status_consistent=consistent,
            )

        # 情况2: 都已激活 - 正常
        if local and server:
            return ActivationResult(
                success=True,
                need_activation_ui=False,
                message="设备已激活",
                local_activated=local,
                server_activated=server,
                status_consistent=consistent,
            )

        # 情况3: 本地未激活但服务器已激活 - 自动修复
        if not local and server:
            self.logger.warning("自动修复本地激活状态")
            self._set_activation_status(True)
            return ActivationResult(
                success=True,
                need_activation_ui=False,
                message="已自动修复激活状态",
                local_activated=True,
                server_activated=server,
                status_consistent=True,
            )

        # 情况4: 本地已激活但服务器未激活 - 需要重新激活
        self.logger.warning("服务器取消授权，需要重新激活")
        if self._activation_data and "code" in self._activation_data:
            return ActivationResult(
                success=True,
                need_activation_ui=True,
                message="服务器取消授权，需要重新激活",
                local_activated=local,
                server_activated=server,
                status_consistent=consistent,
            )

        return ActivationResult(
            success=True,
            need_activation_ui=False,
            message="保持本地激活状态",
            local_activated=local,
            server_activated=True,
            status_consistent=True,
        )

    # ========== 激活流程执行（私有方法） ==========

    def _show_activation_info(self, data: Dict):
        """显示激活信息."""
        code = data.get("code", "------")
        message = data.get("message", "请在xiaozhi.me输入验证码")

        text = f".请登录到控制面板添加设备，输入验证码：{' '.join(code)}..."
        print("\n==================")
        print(text)
        print("==================\n")

        self.logger.info(f"激活提示: {message}")
        self.logger.info(f"验证码: {code}")

        # 播放语音
        try:
            from src.utils.common_utils import play_audio_nonblocking, handle_verification_code
            handle_verification_code(text)
            play_audio_nonblocking(text)
        except Exception as e:
            self.logger.debug(f"语音播放失败: {e}")

    async def _do_activate(self, challenge: str, code: str) -> bool:
        """执行激活请求."""
        serial_number = self.get_serial_number()
        if not serial_number:
            self.logger.error("无序列号，无法激活")
            return False

        hmac_signature = self._generate_hmac_signature(challenge)
        if not hmac_signature:
            self.logger.error("无法生成HMAC签名")
            return False

        payload = {
            "Payload": {
                "algorithm": "hmac-sha256",
                "serial_number": serial_number,
                "challenge": challenge,
                "hmac": hmac_signature,
            }
        }

        ota_url = self.config_manager.get_config("SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL")
        if not ota_url:
            self.logger.error("OTA URL未配置")
            return False

        activate_url = f"{ota_url.rstrip('/')}/activate"
        headers = {
            "Activation-Version": "2",
            "Device-Id": self.config_manager.get_config("SYSTEM_OPTIONS.DEVICE_ID"),
            "Client-Id": self.config_manager.get_config("SYSTEM_OPTIONS.CLIENT_ID"),
            "Content-Type": "application/json",
        }

        self.logger.info(f"激活URL: {activate_url}")

        max_retries = 60
        retry_interval = 5
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for attempt in range(max_retries):
                try:
                    self.logger.info(f"激活尝试 {attempt + 1}/{max_retries}")

                    # 重试时重新播放验证码
                    if attempt > 0:
                        try:
                            from src.utils.common_utils import play_audio_nonblocking
                            text = f".请登录到控制面板添加设备，输入验证码：{' '.join(code)}..."
                            play_audio_nonblocking(text)
                        except Exception:
                            pass

                    async with session.post(activate_url, headers=headers, json=payload) as response:
                        self.logger.debug(f"激活响应: HTTP {response.status}")

                        if response.status == 200:
                            self.logger.info("设备激活成功!")
                            self._set_activation_status(True)
                            return True

                        if response.status == 202:
                            self.logger.info("等待用户输入验证码...")
                            await asyncio.sleep(retry_interval)
                            continue

                        # 其他错误，继续重试
                        self.logger.warning(f"服务器返回 {response.status}，继续重试")
                        await asyncio.sleep(retry_interval)

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.logger.warning(f"激活请求失败: {e}，重试中...")
                    await asyncio.sleep(retry_interval)

        self.logger.error(f"激活失败，达到最大重试次数 ({max_retries})")
        return False
