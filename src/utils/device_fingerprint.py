import hashlib
import hmac
import json
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.utils.logging_config import get_logger
from src.utils.resource_finder import find_config_dir

# 获取日志记录器
logger = get_logger(__name__)


class DeviceFingerprint:
    """设备指纹收集器 - 用于生成唯一的设备标识"""

    def __init__(self):
        """初始化设备指纹收集器."""
        self.system = platform.system()
        config_dir = find_config_dir()
        if config_dir:
            self.fingerprint_cache_file = config_dir / ".device_fingerprint"
            self.efuse_file = config_dir / "efuse.json"
            logger.debug(f"使用配置目录: {config_dir}")
        else:
            # 备用方案：使用相对路径
            self.fingerprint_cache_file = Path("config/.device_fingerprint")
            self.efuse_file = Path("config/efuse.json")
            logger.warning("未找到配置目录，使用相对路径作为备用方案")

    def get_hostname(self) -> str:
        """获取计算机主机名."""
        return platform.node()

    def get_all_mac_addresses(self) -> List[Dict[str, str]]:
        """获取所有网络适配器的MAC地址."""
        mac_addresses = []

        try:
            if self.system == "Windows":
                # Windows系统通过WMI获取所有网络适配器
                import wmi

                w = wmi.WMI()
                for nic in w.Win32_NetworkAdapter():
                    if nic.MACAddress:
                        # 确保MAC地址为小写
                        mac_addr = nic.MACAddress.lower() if nic.MACAddress else ""
                        mac_addresses.append(
                            {
                                "name": nic.Name,
                                "mac": mac_addr,
                                "device_id": nic.DeviceID,
                                "adapter_type": getattr(nic, "AdapterType", ""),
                                "net_connection_id": getattr(
                                    nic, "NetConnectionID", ""
                                ),
                                "physical": (
                                    nic.PhysicalAdapter
                                    if hasattr(nic, "PhysicalAdapter")
                                    else False
                                ),
                            }
                        )
            elif self.system == "Linux":
                # Linux系统通过/sys/class/net目录获取网络适配器信息
                import os
                import re

                net_path = "/sys/class/net"
                if os.path.exists(net_path):
                    for interface in os.listdir(net_path):
                        # 排除lo回环接口
                        if interface == "lo":
                            continue

                        # 读取MAC地址
                        address_path = os.path.join(net_path, interface, "address")
                        if os.path.exists(address_path):
                            try:
                                with open(address_path, "r") as f:
                                    mac = f.read().strip().lower()
                                    if mac and re.match(
                                        r"^([0-9a-f]{2}[:-]){5}([0-9a-f]{2})$", mac
                                    ):
                                        # 判断接口类型
                                        is_wireless = os.path.exists(
                                            os.path.join(
                                                net_path, interface, "wireless"
                                            )
                                        )

                                        # 尝试获取接口类型信息
                                        interface_type = (
                                            "无线网卡" if is_wireless else "有线网卡"
                                        )

                                        # 检查是否为虚拟接口
                                        is_virtual = False
                                        if os.path.exists(
                                            os.path.join(net_path, interface, "device")
                                        ):
                                            driver_path = os.path.join(
                                                net_path, interface, "device", "driver"
                                            )
                                            if os.path.exists(driver_path):
                                                driver = os.path.basename(
                                                    os.path.realpath(driver_path)
                                                )
                                                is_virtual = driver in [
                                                    "veth",
                                                    "vboxnet",
                                                    "docker",
                                                    "bridge",
                                                ]

                                        # 判断是否为物理接口
                                        is_physical = not is_virtual

                                        mac_addresses.append(
                                            {
                                                "name": interface,
                                                "mac": mac,
                                                "device_id": interface,
                                                "adapter_type": interface_type,
                                                "net_connection_id": "",
                                                "physical": is_physical,
                                            }
                                        )
                            except Exception as e:
                                logger.error(
                                    f"读取Linux网卡{interface}的MAC地址失败: {e}"
                                )

                # 如果上面的方法失败或没有找到MAC地址，尝试使用ip命令
                if not mac_addresses:
                    try:
                        import subprocess

                        result = subprocess.run(
                            ["ip", "link", "show"], capture_output=True, text=True
                        )
                        if result.returncode == 0:
                            output = result.stdout
                            # 解析ip link show输出
                            current_if = None
                            for line in output.splitlines():
                                # 新接口行
                                if not line.startswith(" "):
                                    match = re.search(r"^\d+:\s+([^:@]+)[@:]", line)
                                    if match:
                                        current_if = match.group(1).strip()
                                        if current_if == "lo":  # 跳过回环接口
                                            current_if = None
                                # MAC地址行
                                elif current_if and "link/ether" in line:
                                    match = re.search(
                                        r"link/ether\s+([0-9a-f:]{17})", line
                                    )
                                    if match:
                                        mac = match.group(1).lower()
                                        mac_addresses.append(
                                            {
                                                "name": current_if,
                                                "mac": mac,
                                                "device_id": current_if,
                                                "adapter_type": "网络接口",
                                                "net_connection_id": "",
                                                "physical": True,  # 假设为物理接口
                                            }
                                        )
                    except Exception as e:
                        logger.error(f"使用ip命令获取MAC地址失败: {e}")

            elif self.system == "Darwin":  # macOS
                # macOS通过networksetup命令获取所有网络接口
                import re
                import subprocess

                try:
                    # 获取所有网络服务
                    result = subprocess.run(
                        ["networksetup", "-listallhardwareports"],
                        capture_output=True,
                        text=True,
                    )

                    if result.returncode == 0:
                        output = result.stdout
                        current_port = None
                        current_device = None
                        current_type = None

                        for line in output.splitlines():
                            # 硬件端口行
                            if line.startswith("Hardware Port:"):
                                current_port = line.split(":", 1)[1].strip()
                                current_type = (
                                    "无线网卡"
                                    if "Wi-Fi" in current_port
                                    or "AirPort" in current_port
                                    else "有线网卡"
                                )
                            # 设备名行
                            elif line.startswith("Device:"):
                                current_device = line.split(":", 1)[1].strip()
                            # MAC地址行
                            elif (
                                line.startswith("Ethernet Address:") and current_device
                            ):
                                mac = line.split(":", 1)[1].strip().lower()
                                # 将':' 添加到MAC地址中
                                if len(mac) == 12:
                                    mac = ":".join(
                                        [mac[i : i + 2] for i in range(0, 12, 2)]
                                    )

                                mac_addresses.append(
                                    {
                                        "name": current_port or current_device,
                                        "mac": mac,
                                        "device_id": current_device,
                                        "adapter_type": current_type or "网络接口",
                                        "net_connection_id": current_port,
                                        "physical": True,  # 假设物理接口
                                    }
                                )

                                # 重置当前记录的值
                                current_port = None
                                current_device = None
                                current_type = None
                except Exception as e:
                    logger.error(f"在macOS上获取MAC地址失败: {e}")

                # 如果上面的方法失败，尝试使用ifconfig命令
                if not mac_addresses:
                    try:
                        result = subprocess.run(
                            ["ifconfig"], capture_output=True, text=True
                        )
                        if result.returncode == 0:
                            output = result.stdout
                            current_if = None

                            for line in output.splitlines():
                                # 新接口行
                                if not line.startswith("\t") and not line.startswith(
                                    " "
                                ):
                                    match = re.search(r"^([a-zA-Z0-9]+):", line)
                                    if match:
                                        current_if = match.group(1)
                                        if current_if == "lo0":  # 跳过回环接口
                                            current_if = None
                                # MAC地址行
                                elif current_if and (
                                    "ether " in line or "lladdr " in line
                                ):
                                    match = re.search(
                                        r"(?:ether|lladdr)\s+([0-9a-f:]{17})", line
                                    )
                                    if match:
                                        mac = match.group(1).lower()
                                        is_physical = not current_if.startswith(
                                            ("vnet", "bridge", "vbox")
                                        )
                                        mac_addresses.append(
                                            {
                                                "name": current_if,
                                                "mac": mac,
                                                "device_id": current_if,
                                                "adapter_type": "网络接口",
                                                "net_connection_id": "",
                                                "physical": is_physical,
                                            }
                                        )
                    except Exception as e:
                        logger.error(f"使用ifconfig获取MAC地址失败: {e}")
        except Exception as e:
            logger.error(f"获取所有MAC地址时出错: {e}")

        return mac_addresses

    def get_mac_address(self) -> Optional[Tuple[str, str]]:
        """智能选择最适合的物理网卡MAC地址.

        Returns:
            Tuple[str, str]: (MAC地址, 网卡类型描述)
        """
        all_macs = self.get_all_mac_addresses()

        # 如果没有找到任何MAC地址，返回None
        if not all_macs:
            return None

        # 对适配器进行分类
        ethernet_adapters = []  # 有线网卡
        wifi_adapters = []  # WiFi网卡
        bluetooth_adapters = []  # 蓝牙适配器
        physical_adapters = []  # 其他物理网卡
        virtual_adapters = []  # 虚拟网卡

        for adapter in all_macs:
            # 确保name和connection_id不是None
            name = str(adapter.get("name", "")).lower()
            # 不使用connection_id进行分类，避免None错误
            physical = adapter.get("physical", False)

            # 主要通过名称来判断网卡类型
            if (
                any(
                    keyword in name
                    for keyword in ["ethernet", "realtek", "intel", "broadcom"]
                )
                and physical
            ):
                ethernet_adapters.append(adapter)
            elif (
                any(
                    keyword in name for keyword in ["wi-fi", "wifi", "wireless", "wlan"]
                )
                and physical
            ):
                wifi_adapters.append(adapter)
            elif "bluetooth" in name:
                bluetooth_adapters.append(adapter)
            elif physical:
                physical_adapters.append(adapter)
            else:
                virtual_adapters.append(adapter)

        # 按优先级选择MAC地址
        if ethernet_adapters:
            return ethernet_adapters[0]["mac"], "有线网卡"
        elif wifi_adapters:
            return wifi_adapters[0]["mac"], "WiFi网卡"
        elif bluetooth_adapters:
            return bluetooth_adapters[0]["mac"], "蓝牙适配器"
        elif physical_adapters:
            return physical_adapters[0]["mac"], "物理网卡"
        elif virtual_adapters:
            return virtual_adapters[0]["mac"], "虚拟网卡"

        # 如果所有分类都为空，返回第一个MAC地址作为备选
        return all_macs[0]["mac"], "未知类型"

    def get_bluetooth_mac_address(self) -> Optional[str]:
        """获取蓝牙适配器的MAC地址."""
        try:
            all_macs = self.get_all_mac_addresses()
            for mac_info in all_macs:
                # 检查名称中是否包含"Bluetooth"关键字
                if "Bluetooth" in mac_info.get("name", ""):
                    return mac_info.get("mac")
            return None
        except Exception as e:
            logger.error(f"获取蓝牙MAC地址时出错: {e}")
            return None

    def get_cpu_info(self) -> Dict:
        """获取CPU信息."""
        cpu_info = {"processor": platform.processor(), "machine": platform.machine()}

        try:
            if self.system == "Windows":
                # Windows系统通过WMI获取CPU信息
                import wmi

                w = wmi.WMI()
                processor = w.Win32_Processor()[0]
                cpu_info["id"] = processor.ProcessorId.strip()
                cpu_info["name"] = processor.Name.strip()
                cpu_info["cores"] = processor.NumberOfCores
            elif self.system == "Linux":
                # Linux系统通过/proc/cpuinfo获取CPU信息
                with open("/proc/cpuinfo", "r") as f:
                    info = f.readlines()

                cpu_id = None
                model_name = None
                cpu_cores = 0

                for line in info:
                    if "serial" in line or "Serial" in line:
                        # 一些Linux系统可能会有CPU序列号
                        cpu_id = line.split(":")[1].strip()
                    elif "model name" in line:
                        model_name = line.split(":")[1].strip()
                    elif "cpu cores" in line:
                        cpu_cores = int(line.split(":")[1].strip())

                if cpu_id:
                    cpu_info["id"] = cpu_id
                if model_name:
                    cpu_info["name"] = model_name
                if cpu_cores:
                    cpu_info["cores"] = cpu_cores
            elif self.system == "Darwin":  # macOS
                # macOS通过系统命令获取CPU信息
                cmd = "sysctl -n machdep.cpu.brand_string"
                model_name = subprocess.check_output(cmd, shell=True).decode().strip()

                cmd = "sysctl -n hw.physicalcpu"
                cpu_cores = int(
                    subprocess.check_output(cmd, shell=True).decode().strip()
                )

                # macOS没有直接暴露CPU ID，使用其他信息组合
                cmd = "ioreg -l | grep IOPlatformUUID"
                try:
                    platform_uuid = (
                        subprocess.check_output(cmd, shell=True).decode().strip()
                    )
                    uuid_match = re.search(
                        r'IOPlatformUUID" = "([^"]+)"', platform_uuid
                    )
                    if uuid_match:
                        cpu_info["id"] = uuid_match.group(1)
                except Exception:
                    pass

                cpu_info["name"] = model_name
                cpu_info["cores"] = cpu_cores
        except Exception as e:
            logger.error(f"获取CPU信息时出错: {e}")

        return cpu_info

    def get_disk_info(self) -> List[Dict]:
        """获取硬盘信息."""
        disks = []

        try:
            if self.system == "Windows":
                # Windows系统通过WMI获取硬盘信息
                import wmi

                w = wmi.WMI()
                for disk in w.Win32_DiskDrive():
                    if disk.SerialNumber:
                        disks.append(
                            {
                                "model": disk.Model.strip(),
                                "serial": disk.SerialNumber.strip(),
                                "size": str(int(disk.Size or 0)),
                            }
                        )
            elif self.system == "Linux":
                # Linux系统通过lsblk命令获取硬盘信息
                cmd = "lsblk -d -o NAME,SERIAL,MODEL,SIZE --json"
                try:
                    result = subprocess.check_output(cmd, shell=True).decode()
                    data = json.loads(result)
                    for device in data.get("blockdevices", []):
                        if device.get("serial"):
                            disks.append(
                                {
                                    "model": device.get("model", "").strip(),
                                    "serial": device.get("serial").strip(),
                                    "size": device.get("size", "").strip(),
                                }
                            )
                except Exception:
                    # 备用方法通过/dev/disk/by-id获取
                    try:
                        disk_ids = os.listdir("/dev/disk/by-id")
                        for disk_id in disk_ids:
                            if (
                                not disk_id.startswith("usb-")
                                and not disk_id.startswith("nvme-eui")
                                and not disk_id.startswith("wwn-")
                                and "part" not in disk_id
                            ):
                                disks.append(
                                    {"model": "Unknown", "serial": disk_id, "size": "0"}
                                )
                    except Exception:
                        pass
            elif self.system == "Darwin":  # macOS
                # macOS通过diskutil命令获取硬盘信息
                cmd = "diskutil list -plist"
                try:
                    import plistlib

                    result = subprocess.check_output(cmd, shell=True)
                    data = plistlib.loads(result)

                    for disk in data.get("AllDisksAndPartitions", []):
                        disk_id = disk.get("DeviceIdentifier")
                        if not disk_id:
                            continue

                        # 获取该磁盘的详细信息
                        cmd = f"diskutil info -plist {disk_id}"
                        disk_info = subprocess.check_output(cmd, shell=True)
                        disk_data = plistlib.loads(disk_info)

                        serial = disk_data.get("IORegistryEntryName") or disk_data.get(
                            "MediaName"
                        )
                        if serial:
                            disks.append(
                                {
                                    "model": disk_data.get("MediaName", "Unknown"),
                                    "serial": serial,
                                    "size": str(disk_data.get("TotalSize", 0)),
                                }
                            )
                except Exception as e:
                    logger.error(f"在macOS上获取磁盘信息时出错: {e}")
        except Exception as e:
            logger.error(f"获取硬盘信息时出错: {e}")

        return disks

    def get_motherboard_info(self) -> Dict:
        """获取主板信息."""
        mb_info = {}

        try:
            if self.system == "Windows":
                # Windows通过WMI获取主板信息
                import wmi

                w = wmi.WMI()
                for board in w.Win32_BaseBoard():
                    mb_info["manufacturer"] = (
                        board.Manufacturer.strip() if board.Manufacturer else ""
                    )
                    mb_info["model"] = board.Product.strip() if board.Product else ""
                    mb_info["serial"] = (
                        board.SerialNumber.strip() if board.SerialNumber else ""
                    )
                    break

                # 如果没有获取到序列号，尝试使用BIOS序列号
                if not mb_info.get("serial"):
                    for bios in w.Win32_BIOS():
                        if bios.SerialNumber:
                            mb_info["bios_serial"] = bios.SerialNumber.strip()
                            break
            elif self.system == "Linux":
                # Linux通过dmidecode命令获取主板信息
                try:
                    cmd = "dmidecode -t 2"
                    result = subprocess.check_output(
                        cmd, shell=True, stderr=subprocess.PIPE
                    ).decode()
                    for line in result.split("\n"):
                        if "Manufacturer" in line:
                            mb_info["manufacturer"] = line.split(":")[1].strip()
                        elif "Product Name" in line:
                            mb_info["model"] = line.split(":")[1].strip()
                        elif "Serial Number" in line:
                            mb_info["serial"] = line.split(":")[1].strip()
                except Exception:
                    # 备用方法从/sys/class/dmi/id获取
                    try:
                        with open("/sys/class/dmi/id/board_vendor", "r") as f:
                            mb_info["manufacturer"] = f.read().strip()
                        with open("/sys/class/dmi/id/board_name", "r") as f:
                            mb_info["model"] = f.read().strip()
                        with open("/sys/class/dmi/id/board_serial", "r") as f:
                            mb_info["serial"] = f.read().strip()
                    except Exception:
                        pass
            elif self.system == "Darwin":  # macOS
                # macOS使用ioreg命令获取主板或系统信息
                try:
                    cmd = (
                        "ioreg -l | grep -E '(board-id|IOPlatformSerialNumber|"
                        "IOPlatformUUID)'"
                    )

                    result = subprocess.check_output(cmd, shell=True).decode()

                    board_id = re.search(r'board-id" = <"([^"]+)">', result)
                    if board_id:
                        mb_info["model"] = board_id.group(1)

                    serial = re.search(r'IOPlatformSerialNumber" = "([^"]+)"', result)
                    if serial:
                        mb_info["serial"] = serial.group(1)

                    uuid_match = re.search(r'IOPlatformUUID" = "([^"]+)"', result)
                    if uuid_match:
                        mb_info["uuid"] = uuid_match.group(1)
                except Exception as e:
                    logger.error(f"在macOS上获取主板信息时出错: {e}")
        except Exception as e:
            logger.error(f"获取主板信息时出错: {e}")

        return mb_info

    def generate_fingerprint(self) -> Dict:
        """生成完整的设备指纹."""
        # 检查是否有缓存的指纹
        cached_fingerprint = self._load_cached_fingerprint()
        if cached_fingerprint:
            return cached_fingerprint

        # 获取主要网卡MAC地址
        mac_address, mac_type = self.get_mac_address()

        # 收集各种硬件信息
        fingerprint = {
            "system": self.system,
            "hostname": self.get_hostname(),
            "mac_address": mac_address,  # 保留系统获取的MAC地址用于兼容
            "mac_type": mac_type,
            "bluetooth_mac": self.get_bluetooth_mac_address(),
            "cpu": self.get_cpu_info(),
            "disks": self.get_disk_info(),
            "motherboard": self.get_motherboard_info(),
        }

        # 缓存指纹
        self._cache_fingerprint(fingerprint)

        return fingerprint

    def _load_cached_fingerprint(self) -> Optional[Dict]:
        """从缓存文件加载指纹."""
        if not self.fingerprint_cache_file.exists():
            return None

        try:
            with open(self.fingerprint_cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载缓存的设备指纹时出错: {e}")
            return None

    def _cache_fingerprint(self, fingerprint: Dict):
        """缓存指纹到文件."""
        try:
            # 确保目录存在
            self.fingerprint_cache_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.fingerprint_cache_file, "w", encoding="utf-8") as f:
                json.dump(fingerprint, f, indent=2, ensure_ascii=False)

            logger.info("设备指纹已缓存到文件")
        except Exception as e:
            logger.error(f"缓存设备指纹时出错: {e}")

    def generate_hardware_hash(self) -> str:
        """根据硬件信息生成唯一的哈希值."""
        fingerprint = self.generate_fingerprint()

        # 提取最不可变的硬件标识符
        identifiers = []

        # 主机名
        hostname = fingerprint.get("hostname")
        if hostname:
            identifiers.append(hostname)

        # CPU ID
        if fingerprint.get("cpu", {}).get("id"):
            identifiers.append(fingerprint["cpu"]["id"])
        else:
            identifiers.append(fingerprint.get("cpu", {}).get("name", "unknown_cpu"))

        # 主板序列号
        mb_serial = fingerprint.get("motherboard", {}).get("serial")
        if mb_serial and mb_serial != "To be filled by O.E.M.":  # 排除默认值
            identifiers.append(mb_serial)
        else:
            mb_uuid = fingerprint.get("motherboard", {}).get("uuid")
            if mb_uuid:
                identifiers.append(mb_uuid)

        # 硬盘序列号(使用第一个非空的硬盘序列号)
        for disk in fingerprint.get("disks", []):
            if disk.get("serial") and disk["serial"] != "0000_0000":
                identifiers.append(disk["serial"])
                break

        # 如果没有收集到足够的硬件信息，使用MAC地址作为备选
        if len(identifiers) < 2:
            identifiers.append(fingerprint.get("mac_address", ""))

            # 如果有蓝牙MAC地址，也加入
            if fingerprint.get("bluetooth_mac"):
                identifiers.append(fingerprint.get("bluetooth_mac"))

        # 将所有标识符连接起来并计算哈希值
        fingerprint_str = "||".join(identifiers)
        return hashlib.sha256(fingerprint_str.encode("utf-8")).hexdigest()

    def generate_serial_number(self) -> Tuple[str, str]:
        """生成设备序列号.

        Returns:
            Tuple[str, str]: (序列号, 生成方法说明)
        """
        fingerprint = self.generate_fingerprint()

        # 获取主机名，用于序列号生成
        # hostname = fingerprint.get("hostname", "")
        # short_hostname = "".join(c for c in hostname if c.isalnum())[:8]

        # 优先使用主网卡MAC地址生成序列号
        mac_address = fingerprint.get("mac_address")
        mac_type = fingerprint.get("mac_type", "未知网卡")

        if mac_address:
            # 确保MAC地址为小写且没有冒号
            mac_clean = mac_address.lower().replace(":", "")
            short_hash = hashlib.md5(mac_clean.encode()).hexdigest()[:8].upper()
            serial_number = f"SN-{short_hash}-{mac_clean}"
            return serial_number, mac_type

        # 备选方案: 尝试使用蓝牙MAC地址
        bluetooth_mac = fingerprint.get("bluetooth_mac")
        if bluetooth_mac:
            # 确保MAC地址为小写且没有冒号
            mac_clean = bluetooth_mac.lower().replace(":", "")
            short_hash = hashlib.md5(mac_clean.encode()).hexdigest()[:8].upper()
            serial_number = f"SN-{short_hash}-{mac_clean}"
            return serial_number, "蓝牙MAC地址"

        # 备选方案: 使用常规MAC地址
        mac_address = fingerprint.get("mac_address")
        if mac_address:
            # 确保MAC地址为小写且没有冒号
            mac_clean = mac_address.lower().replace(":", "")
            short_hash = hashlib.md5(mac_clean.encode()).hexdigest()[:8].upper()
            serial_number = f"SN-{short_hash}-{mac_clean}"
            return serial_number, "系统MAC地址"

        # 最后方案: 使用硬件哈希
        hardware_hash = self.generate_hardware_hash()[:16].upper()
        serial_number = f"SN-{hardware_hash}"
        return serial_number, "硬件哈希值"

    def _ensure_efuse_file(self):
        """确保efuse文件存在，如果不存在则创建."""

        serial_number, source = self.generate_serial_number()
        hmac_key = self.generate_hardware_hash()
        print(f"生成序列号: {serial_number} (来源: {source}) hmac_key: {hmac_key}")
        if not self.efuse_file.exists():
            # 创建默认efuse数据
            default_data = {
                "serial_number": serial_number,
                "hmac_key": hmac_key,
                "activation_status": False,
            }

            # 确保目录存在
            self.efuse_file.parent.mkdir(parents=True, exist_ok=True)

            # 写入默认数据
            with open(self.efuse_file, "w", encoding="utf-8") as f:
                json.dump(default_data, f, indent=2, ensure_ascii=False)

            logger.info(f"已创建efuse配置文件: {self.efuse_file}")
            print("新设备：已创建efuse配置文件")
        else:
            logger.info(f"efuse配置文件已存在: {self.efuse_file}")
            # 验证文件内容是否完整
            try:
                efuse_data = self._load_efuse_data()
                # 检查必要字段是否存在
                required_fields = ["serial_number", "hmac_key", "activation_status"]
                missing_fields = [
                    field for field in required_fields if field not in efuse_data
                ]

                if missing_fields:
                    logger.warning(f"efuse配置文件缺少字段: {missing_fields}")

                    # 添加缺失字段，但不修改已有字段
                    for field in missing_fields:
                        efuse_data[field] = (
                            None if field != "activation_status" else False
                        )

                    # 保存修复后的数据
                    self._save_efuse_data(efuse_data)
                    logger.info("已修复efuse配置文件")
            except Exception as e:
                logger.error(f"验证efuse配置文件时出错: {e}")

    def _load_efuse_data(self) -> dict:
        """加载efuse数据."""
        try:
            with open(self.efuse_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载efuse数据失败: {e}")
            return {"serial_number": None, "hmac_key": None, "activation_status": False}

    def _save_efuse_data(self, data: dict) -> bool:
        """保存efuse数据."""
        try:
            with open(self.efuse_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"保存efuse数据失败: {e}")
            return False

    def ensure_device_identity(self) -> Tuple[str, str, bool]:
        """
        确保设备身份信息已加载 - 返回序列号、HMAC密钥和激活状态

        不会创建新的序列号或HMAC密钥，只会读取已有的数据

        Returns:
            Tuple[str, str, bool]: (序列号, HMAC密钥, 激活状态)
        """
        # 只加载现有的efuse数据，不进行创建
        efuse_data = self._load_efuse_data()

        # 获取序列号、HMAC密钥和激活状态
        serial_number = efuse_data.get("serial_number")
        hmac_key = efuse_data.get("hmac_key")
        is_activated = efuse_data.get("activation_status", False)

        # 记录日志但不创建新数据
        if not serial_number:
            logger.warning("efuse.json中没有找到序列号")
        if not hmac_key:
            logger.warning("efuse.json中没有找到HMAC密钥")

        return serial_number, hmac_key, is_activated

    def has_serial_number(self) -> bool:
        """检查是否有序列号."""
        efuse_data = self._load_efuse_data()
        return efuse_data.get("serial_number") is not None

    def get_serial_number(self) -> str:
        """获取序列号."""
        efuse_data = self._load_efuse_data()
        return efuse_data.get("serial_number")

    def get_hmac_key(self) -> str:
        """获取HMAC密钥."""
        efuse_data = self._load_efuse_data()
        return efuse_data.get("hmac_key")

    def set_activation_status(self, status: bool) -> bool:
        """设置激活状态."""
        efuse_data = self._load_efuse_data()
        efuse_data["activation_status"] = status
        return self._save_efuse_data(efuse_data)

    def is_activated(self) -> bool:
        """检查设备是否已激活."""
        efuse_data = self._load_efuse_data()
        return efuse_data.get("activation_status", False)

    def generate_hmac(self, challenge: str) -> str:
        """使用HMAC密钥生成签名."""
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


# 单例模式获取设备指纹
_fingerprint_instance = None


def get_device_fingerprint() -> DeviceFingerprint:
    """获取设备指纹实例（单例模式）"""
    global _fingerprint_instance
    if _fingerprint_instance is None:
        _fingerprint_instance = DeviceFingerprint()
    return _fingerprint_instance
