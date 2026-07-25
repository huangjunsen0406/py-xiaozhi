"""设备身份与 efuse 存储.

efuse.json 仅平铺字段（不写 device_fingerprint 嵌套）::

    {
      "mac_address": "...",
      "serial_number": "...",
      "hmac_key": "...",
      "activation_status": false
    }

生成 SN/HMAC 时仍在内存中采集 fingerprint，不落盘。
旧文件若含 device_fingerprint，加载/校验时剥离并回写。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
from pathlib import Path
from typing import Dict, Optional, Tuple

import machineid
import psutil

from src.logging import get_logger
from src.utils.resource_finder import get_user_data_dir

logger = get_logger()

# 持久化字段（平铺）；其它键（如历史 device_fingerprint）加载时丢弃
_EFUSE_KEYS = (
    "mac_address",
    "serial_number",
    "hmac_key",
    "activation_status",
)


class DeviceIdentity:
    """efuse 文件读写、序列号 / HMAC / MAC."""

    def __init__(self) -> None:
        self._system = platform.system()
        self._efuse_file: Optional[Path] = None
        self._efuse_cache: Optional[Dict] = None

    def init_paths(self) -> None:
        config_dir = get_user_data_dir() / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        self._efuse_file = config_dir / "efuse.json"
        logger.debug(f"efuse文件路径: {self._efuse_file}")

    def ensure_efuse_file(self) -> None:
        fingerprint = self.generate_fresh_fingerprint()
        mac_address = fingerprint.get("mac_address")
        if not self._efuse_file or not self._efuse_file.exists():
            logger.info("创建efuse.json文件")
            self._create_efuse_file(fingerprint, mac_address)
        else:
            self._validate_efuse_file(fingerprint, mac_address)

    def ensure_device_identity(self) -> Tuple[Optional[str], Optional[str], bool]:
        data = self.load_efuse_data()
        return (
            data.get("serial_number"),
            data.get("hmac_key"),
            data.get("activation_status", False),
        )

    def get_serial_number(self) -> Optional[str]:
        return self.load_efuse_data().get("serial_number")

    def get_mac_address(self) -> Optional[str]:
        return self.load_efuse_data().get("mac_address")

    def is_activated(self) -> bool:
        return bool(self.load_efuse_data().get("activation_status", False))

    def set_activation_status(self, status: bool) -> bool:
        data = self.load_efuse_data()
        data["activation_status"] = bool(status)
        return self._save_efuse_data(data)

    def generate_hmac_signature(self, challenge: str) -> Optional[str]:
        hmac_key = self.load_efuse_data().get("hmac_key")
        if not hmac_key or not challenge:
            return None
        return hmac.new(
            hmac_key.encode(), challenge.encode(), hashlib.sha256
        ).hexdigest()

    def load_efuse_data(self) -> Dict:
        if self._efuse_cache is not None:
            return self._efuse_cache
        try:
            return self._load_efuse_data_from_file()
        except Exception:
            return {"activation_status": False}

    def generate_fresh_fingerprint(self) -> Dict:
        """内存采集，仅用于生成 SN/HMAC；不写入 efuse.json."""
        return {
            "system": self._system,
            "hostname": platform.node(),
            "mac_address": self._get_primary_mac_address(),
            "machine_id": self._get_machine_id(),
        }

    def _flat_efuse(
        self,
        *,
        mac_address: Optional[str],
        serial_number: str,
        hmac_key: str,
        activation_status: bool = False,
    ) -> Dict:
        return {
            "mac_address": mac_address,
            "serial_number": serial_number,
            "hmac_key": hmac_key,
            "activation_status": bool(activation_status),
        }

    def _create_efuse_file(self, fingerprint: Dict, mac_address: Optional[str]):
        serial_number = self._generate_serial_number_from_fingerprint(fingerprint)
        hmac_key = self._generate_hmac_key_from_fingerprint(fingerprint)
        efuse_data = self._flat_efuse(
            mac_address=mac_address,
            serial_number=serial_number,
            hmac_key=hmac_key,
            activation_status=False,
        )
        self._save_efuse_data(efuse_data)
        logger.info(f"已创建efuse配置: 序列号={serial_number}")

    def _validate_efuse_file(self, fingerprint: Dict, mac_address: Optional[str]):
        try:
            with open(self._efuse_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                raise TypeError(
                    f"efuse 根节点须为 object，实际为 {type(raw).__name__}"
                )

            had_extra = any(k not in _EFUSE_KEYS for k in raw)
            missing = [f for f in _EFUSE_KEYS if f not in raw]
            if missing:
                logger.warning(f"efuse缺少字段: {missing}")
                for field in missing:
                    if field == "mac_address":
                        raw[field] = mac_address
                    elif field == "serial_number":
                        raw[field] = self._generate_serial_number_from_fingerprint(
                            fingerprint
                        )
                    elif field == "hmac_key":
                        raw[field] = self._generate_hmac_key_from_fingerprint(
                            fingerprint
                        )
                    elif field == "activation_status":
                        raw[field] = False

            flat = self._normalize_efuse_dict(raw)
            if missing or had_extra:
                if had_extra:
                    logger.info(
                        "efuse 已剥离非平铺字段（如 device_fingerprint）"
                    )
                self._save_efuse_data(flat)
            else:
                self._efuse_cache = flat
        except Exception as e:
            logger.error(f"验证efuse失败: {e}，重新创建", exc_info=True)
            self._create_efuse_file(fingerprint, mac_address)

    def _normalize_efuse_dict(self, data: Dict) -> Dict:
        """只保留平铺身份字段."""
        return {
            "mac_address": data.get("mac_address"),
            "serial_number": data.get("serial_number"),
            "hmac_key": data.get("hmac_key"),
            "activation_status": bool(data.get("activation_status", False)),
        }

    def _get_primary_mac_address(self) -> Optional[str]:
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
            logger.error(f"获取MAC地址失败: {e}", exc_info=True)
        return None

    def _normalize_mac(self, mac: str) -> str:
        clean = "".join(c for c in mac if c.isalnum())
        if len(clean) != 12:
            return mac.lower()
        return ":".join(clean[i : i + 2] for i in range(0, 12, 2)).lower()

    def _get_machine_id(self) -> Optional[str]:
        try:
            return machineid.id()
        except Exception as e:
            logger.warning(f"获取 machine_id 失败: {e}", exc_info=True)
            return None

    def _generate_serial_number_from_fingerprint(self, fingerprint: Dict) -> str:
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
        identifiers = []
        for key in ["hostname", "mac_address", "machine_id"]:
            if fingerprint.get(key):
                identifiers.append(fingerprint[key])
        if not identifiers:
            identifiers.append(self._system)
        return hashlib.sha256("||".join(identifiers).encode()).hexdigest()

    def _load_efuse_data_from_file(self) -> Dict:
        with open(self._efuse_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise TypeError(f"efuse 根节点须为 object，实际为 {type(data).__name__}")
        # 内存视图始终平铺；磁盘上的多余键由 ensure/validate 负责剥离回写
        flat = self._normalize_efuse_dict(data)
        self._efuse_cache = flat
        return flat

    def _save_efuse_data(self, data: Dict) -> bool:
        try:
            if not self._efuse_file:
                raise RuntimeError("efuse 路径未初始化")
            flat = self._normalize_efuse_dict(data)
            self._efuse_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._efuse_file.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(flat, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            os.replace(tmp, self._efuse_file)
            self._efuse_cache = flat
            return True
        except Exception as e:
            logger.error(f"保存efuse失败: {e}", exc_info=True)
            return False
