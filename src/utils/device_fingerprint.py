import hashlib
import hmac
import json
import platform
from pathlib import Path
from typing import Dict, Optional, Tuple

import machineid
import psutil

from src.utils.logging_config import get_logger
from src.utils.resource_finder import find_config_dir

# 获取日志记录器
logger = get_logger(__name__)


class DeviceFingerprint:
    """设备指纹收集器 - 用于生成唯一的设备标识"""

    _instance = None

    def __new__(cls):
        """
        确保单例模式.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """
        初始化设备指纹收集器.
        """
        if self._initialized:
            return
        self._initialized = True

        self.system = platform.system()
        self._efuse_cache: Optional[Dict] = None  # efuse数据缓存

        # 初始化文件路径
        self._init_file_paths()

        # 确保efuse文件在初始化时就存在且完整
        self._ensure_efuse_file()

    def _init_file_paths(self):
        """
        初始化文件路径.
        """
        config_dir = find_config_dir()
        if config_dir:
            self.efuse_file = config_dir / "efuse.json"
            logger.debug(f"使用配置目录: {config_dir}")
        else:
            # 备用方案：使用相对路径并确保目录存在
            config_path = Path("config")
            config_path.mkdir(parents=True, exist_ok=True)
            self.efuse_file = config_path / "efuse.json"
            logger.info(f"创建配置目录: {config_path.absolute()}")

    def get_hostname(self) -> str:
        """
        获取计算机主机名.
        """
        return platform.node()

    def _normalize_mac_address(self, mac_address: str) -> str:
        """标准化MAC地址格式为小写冒号分隔格式.

        Args:
            mac_address: 原始MAC地址，可能使用连字符、冒号或其他分隔符

        Returns:
            str: 标准化后的MAC地址，格式为 "00:00:00:00:00:00"
        """
        if not mac_address:
            return mac_address

        # 移除所有可能的分隔符，只保留十六进制字符
        clean_mac = "".join(c for c in mac_address if c.isalnum())

        # 确保长度为12个字符（6个字节的十六进制表示）
        if len(clean_mac) != 12:
            logger.warning(f"MAC地址长度不正确: {mac_address} -> {clean_mac}")
            return mac_address.lower()

        # 重新格式化为标准的冒号分隔格式
        formatted_mac = ":".join(clean_mac[i : i + 2] for i in range(0, 12, 2))

        # 转换为小写
        return formatted_mac.lower()

    def get_mac_address(self) -> Optional[str]:
        """
        获取主要网卡的MAC地址.
        """
        try:
            # 获取所有网络接口的地址信息
            net_if_addrs = psutil.net_if_addrs()

            # 优先选择非回环接口的MAC地址
            for iface, addrs in net_if_addrs.items():
                # 跳过回环接口
                if iface.lower().startswith(("lo", "loopback")):
                    continue

                for snic in addrs:
                    if snic.family == psutil.AF_LINK and snic.address:
                        # 标准化MAC地址格式
                        normalized_mac = self._normalize_mac_address(snic.address)
                        # 过滤掉无效的MAC地址
                        if normalized_mac != "00:00:00:00:00:00":
                            return normalized_mac

            # 如果没有找到合适的MAC地址，返回None
            logger.warning("未找到有效的MAC地址")
            return None

        except Exception as e:
            logger.error(f"获取MAC地址时发生错误: {e}")
            return None

    def get_machine_id(self) -> Optional[str]:
        """
        获取设备唯一标识.
        """
        try:
            return machineid.id()
        except machineid.MachineIdNotFound:
            logger.warning("未找到机器ID")
            return None
        except Exception as e:
            logger.error(f"获取机器ID时发生错误: {e}")
            return None

    def _generate_fresh_fingerprint(self) -> Dict:
        """
        生成全新的设备指纹（不依赖缓存或文件）.
        """
        return {
            "system": self.system,
            "hostname": self.get_hostname(),
            "mac_address": self.get_mac_address(),
            "machine_id": self.get_machine_id(),
        }

    def generate_fingerprint(self) -> Dict:
        """
        生成完整的设备指纹（优先从efuse.json读取）.
        """
        # 首先尝试从efuse.json读取设备指纹
        if self.efuse_file.exists():
            try:
                efuse_data = self._load_efuse_data()
                if efuse_data.get("device_fingerprint"):
                    logger.debug("从efuse.json读取设备指纹")
                    return efuse_data["device_fingerprint"]
            except Exception as e:
                logger.warning(f"读取efuse.json中的设备指纹失败: {e}")

        # 如果读取失败或不存在，则生成新的设备指纹
        logger.info("生成新的设备指纹")
        return self._generate_fresh_fingerprint()

    def generate_hardware_hash(self) -> str:
        """
        根据硬件信息生成唯一的哈希值.
        """
        fingerprint = self.generate_fingerprint()

        # 提取最不可变的硬件标识符
        identifiers = []

        # 主机名
        hostname = fingerprint.get("hostname")
        if hostname:
            identifiers.append(hostname)

        # MAC地址
        mac_address = fingerprint.get("mac_address")
        if mac_address:
            identifiers.append(mac_address)

        # 机器ID
        machine_id = fingerprint.get("machine_id")
        if machine_id:
            identifiers.append(machine_id)

        # 如果没有任何标识符，使用系统信息作为备用
        if not identifiers:
            identifiers.append(self.system)
            logger.warning("未找到硬件标识符，使用系统信息作为备用")

        # 将所有标识符连接起来并计算哈希值
        fingerprint_str = "||".join(identifiers)
        return hashlib.sha256(fingerprint_str.encode("utf-8")).hexdigest()

    def generate_serial_number(self) -> str:
        """
        生成设备序列号.
        """
        fingerprint = self.generate_fingerprint()

        # 优先使用主网卡MAC地址生成序列号
        mac_address = fingerprint.get("mac_address")

        if not mac_address:
            # 如果没有MAC地址，使用机器ID或主机名
            machine_id = fingerprint.get("machine_id")
            hostname = fingerprint.get("hostname")

            if machine_id:
                identifier = machine_id[:12]  # 取前12位
            elif hostname:
                identifier = hostname.replace("-", "").replace("_", "")[:12]
            else:
                identifier = "unknown"

            short_hash = hashlib.md5(identifier.encode()).hexdigest()[:8].upper()
            return f"SN-{short_hash}-{identifier.upper()}"

        # 确保MAC地址为小写且没有冒号
        mac_clean = mac_address.lower().replace(":", "")
        short_hash = hashlib.md5(mac_clean.encode()).hexdigest()[:8].upper()
        serial_number = f"SN-{short_hash}-{mac_clean}"
        return serial_number

    def _ensure_efuse_file(self):
        """
        确保efuse文件存在且包含完整信息.
        """
        logger.info(f"检查efuse文件: {self.efuse_file.absolute()}")

        # 先生成设备指纹（这样可以确保硬件信息可用）
        fingerprint = self._generate_fresh_fingerprint()
        mac_address = fingerprint.get("mac_address")

        if not self.efuse_file.exists():
            logger.info("efuse.json文件不存在，创建新文件")
            self._create_new_efuse_file(fingerprint, mac_address)
        else:
            logger.info("efuse.json文件已存在，验证完整性")
            self._validate_and_fix_efuse_file(fingerprint, mac_address)

    def _create_new_efuse_file(self, fingerprint: Dict, mac_address: Optional[str]):
        """
        创建新的efuse文件.
        """
        # 生成序列号和HMAC密钥
        serial_number = self.generate_serial_number()
        hmac_key = self.generate_hardware_hash()

        logger.info(f"生成序列号: {serial_number}")
        logger.debug(f"生成HMAC密钥: {hmac_key[:8]}...")  # 只记录前8位

        # 创建完整的efuse数据
        efuse_data = {
            "mac_address": mac_address,
            "serial_number": serial_number,
            "hmac_key": hmac_key,
            "activation_status": False,
            "device_fingerprint": fingerprint,
        }

        # 确保目录存在
        self.efuse_file.parent.mkdir(parents=True, exist_ok=True)

        # 写入数据
        success = self._save_efuse_data(efuse_data)
        if success:
            logger.info(f"已创建efuse配置文件: {self.efuse_file}")
        else:
            logger.error("创建efuse配置文件失败")

    def _validate_and_fix_efuse_file(
        self, fingerprint: Dict, mac_address: Optional[str]
    ):
        """
        验证并修复efuse文件的完整性.
        """
        try:
            efuse_data = self._load_efuse_data_from_file()

            # 检查必要字段是否存在
            required_fields = [
                "mac_address",
                "serial_number",
                "hmac_key",
                "activation_status",
                "device_fingerprint",
            ]
            missing_fields = [
                field for field in required_fields if field not in efuse_data
            ]

            if missing_fields:
                logger.warning(f"efuse配置文件缺少字段: {missing_fields}")
                self._fix_missing_fields(
                    efuse_data, missing_fields, fingerprint, mac_address
                )
            else:
                logger.debug("efuse配置文件完整性检查通过")
                # 更新缓存
                self._efuse_cache = efuse_data

        except Exception as e:
            logger.error(f"验证efuse配置文件时出错: {e}")
            # 如果验证失败，重新创建文件
            logger.info("重新创建efuse配置文件")
            self._create_new_efuse_file(fingerprint, mac_address)

    def _fix_missing_fields(
        self,
        efuse_data: Dict,
        missing_fields: list,
        fingerprint: Dict,
        mac_address: Optional[str],
    ):
        """
        修复缺失的字段.
        """
        for field in missing_fields:
            if field == "device_fingerprint":
                efuse_data[field] = fingerprint
            elif field == "mac_address":
                efuse_data[field] = mac_address
            elif field == "serial_number":
                efuse_data[field] = self.generate_serial_number()
            elif field == "hmac_key":
                efuse_data[field] = self.generate_hardware_hash()
            elif field == "activation_status":
                efuse_data[field] = False

        # 保存修复后的数据
        success = self._save_efuse_data(efuse_data)
        if success:
            logger.info("已修复efuse配置文件")
        else:
            logger.error("修复efuse配置文件失败")

    def _load_efuse_data_from_file(self) -> Dict:
        """
        直接从文件加载efuse数据（不使用缓存）.
        """
        with open(self.efuse_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_efuse_data(self) -> Dict:
        """
        加载efuse数据（带缓存）.
        """
        # 如果有缓存，直接返回
        if self._efuse_cache is not None:
            return self._efuse_cache

        try:
            data = self._load_efuse_data_from_file()
            # 缓存数据
            self._efuse_cache = data
            return data
        except Exception as e:
            logger.error(f"加载efuse数据失败: {e}")
            # 返回空的默认数据，但不缓存
            return {
                "mac_address": None,
                "serial_number": None,
                "hmac_key": None,
                "activation_status": False,
                "device_fingerprint": {},
            }

    def _save_efuse_data(self, data: Dict) -> bool:
        """
        保存efuse数据.
        """
        try:
            # 确保目录存在
            self.efuse_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.efuse_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # 更新缓存
            self._efuse_cache = data
            logger.debug(f"efuse数据已保存到: {self.efuse_file}")
            return True
        except Exception as e:
            logger.error(f"保存efuse数据失败: {e}")
            return False

    def ensure_device_identity(self) -> Tuple[Optional[str], Optional[str], bool]:
        """
        确保设备身份信息已加载 - 返回序列号、HMAC密钥和激活状态

        Returns:
            Tuple[Optional[str], Optional[str], bool]: (序列号, HMAC密钥, 激活状态)
        """
        # 加载efuse数据（此时文件应该已经存在且完整）
        efuse_data = self._load_efuse_data()

        # 获取序列号、HMAC密钥和激活状态
        serial_number = efuse_data.get("serial_number")
        hmac_key = efuse_data.get("hmac_key")
        is_activated = efuse_data.get("activation_status", False)

        return serial_number, hmac_key, is_activated

    def has_serial_number(self) -> bool:
        """
        检查是否有序列号.
        """
        efuse_data = self._load_efuse_data()
        return efuse_data.get("serial_number") is not None

    def get_serial_number(self) -> Optional[str]:
        """
        获取序列号.
        """
        efuse_data = self._load_efuse_data()
        return efuse_data.get("serial_number")

    def get_hmac_key(self) -> Optional[str]:
        """
        获取HMAC密钥.
        """
        efuse_data = self._load_efuse_data()
        return efuse_data.get("hmac_key")

    def get_mac_address_from_efuse(self) -> Optional[str]:
        """
        从efuse.json获取MAC地址.
        """
        efuse_data = self._load_efuse_data()
        return efuse_data.get("mac_address")

    def set_activation_status(self, status: bool) -> bool:
        """
        设置激活状态.
        """
        efuse_data = self._load_efuse_data()
        efuse_data["activation_status"] = status
        return self._save_efuse_data(efuse_data)

    def is_activated(self) -> bool:
        """
        检查设备是否已激活.
        """
        efuse_data = self._load_efuse_data()
        return efuse_data.get("activation_status", False)

    def generate_hmac(self, challenge: str) -> Optional[str]:
        """
        使用HMAC密钥生成签名.
        """
        if not challenge:
            logger.error("挑战字符串不能为空")
            return None

        hmac_key = self.get_hmac_key()

        if not hmac_key:
            logger.error("未找到HMAC密钥，无法生成签名")
            return None

        try:
            # 计算HMAC-SHA256签名
            signature = hmac.new(
                hmac_key.encode(), challenge.encode(), hashlib.sha256
            ).hexdigest()

            return signature
        except Exception as e:
            logger.error(f"生成HMAC签名失败: {e}")
            return None

    @classmethod
    def get_instance(cls) -> "DeviceFingerprint":
        """
        获取设备指纹实例.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
