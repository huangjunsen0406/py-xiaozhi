# -*- coding: utf-8 -*-
"""
CLI模式设备激活流程 提供与GUI激活窗口相同的功能，但使用纯终端输出.
"""

import asyncio
from datetime import datetime
from typing import Optional

from src.core.system_initializer import SystemInitializer
from src.utils.device_activator import DeviceActivator
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class CLIActivation:
    """
    CLI模式设备激活处理器.
    """

    def __init__(self):
        # 组件实例
        self.system_initializer: Optional[SystemInitializer] = None
        self.device_activator: Optional[DeviceActivator] = None

        # 状态管理
        self.current_stage = None
        self.activation_data = None
        self.is_activated = False

        self.logger = logger

    async def run_activation_process(self) -> bool:
        """运行完整的CLI激活流程.

        Returns:
            bool: 激活是否成功
        """
        try:
            self._print_header()
            self._log_and_print("开始系统初始化流程")

            self.system_initializer = SystemInitializer()

            # 运行四阶段初始化
            success = await self._run_initialization_with_progress()

            if success:
                self._log_and_print("系统初始化完成")
                return await self._check_activation_status()
            else:
                self._log_and_print("系统初始化失败")
                return False

        except KeyboardInterrupt:
            self._log_and_print("\n用户中断激活流程")
            return False
        except Exception as e:
            self.logger.error(f"CLI激活过程异常: {e}", exc_info=True)
            self._log_and_print(f"激活异常: {e}")
            return False

    def _print_header(self):
        """
        打印CLI激活流程头部信息.
        """
        print("\n" + "=" * 60)
        print("小智AI客户端 - 设备激活流程")
        print("=" * 60)
        print("正在初始化设备，请稍候...")
        print()

    async def _run_initialization_with_progress(self) -> bool:
        """
        运行初始化并显示进度.
        """
        try:
            # 第一阶段：设备身份准备
            self._print_stage_header("第一阶段：设备身份准备", 1, 4)
            await self.system_initializer.stage_1_device_fingerprint()
            self._update_device_info()
            self._print_stage_complete(1, 4)

            # 第二阶段：配置管理初始化
            self._print_stage_header("第二阶段：配置管理初始化", 2, 4)
            await self.system_initializer.stage_2_config_management()
            self._print_stage_complete(2, 4)

            # 第三阶段：OTA获取配置
            self._print_stage_header("第三阶段：OTA配置获取", 3, 4)
            await self.system_initializer.stage_3_ota_config()
            self._print_stage_complete(3, 4)

            # 第四阶段：激活流程准备
            self._print_stage_header("第四阶段：激活流程准备", 4, 4)
            self.system_initializer.stage_4_activation_ready()
            self._print_stage_complete(4, 4)

            return True

        except Exception as e:
            self.logger.error(f"初始化阶段失败: {e}")
            self._log_and_print(f"初始化失败: {e}")
            return False

    def _print_stage_header(self, stage_name: str, current: int, total: int):
        """
        打印阶段头部信息.
        """
        progress = f"[{current}/{total}]"
        print(f"\n{progress} {stage_name}")
        print("-" * 40)

    def _print_stage_complete(self, current: int, total: int):
        """
        打印阶段完成信息.
        """
        progress_percent = int((current / total) * 100)
        filled = int(progress_percent / 5)
        progress_bar = "█" * filled + "░" * (20 - filled)
        print(f"完成 [{progress_bar}] {progress_percent}%")

    def _update_device_info(self):
        """
        更新设备信息显示.
        """
        if (
            not self.system_initializer
            or not self.system_initializer.device_fingerprint
        ):
            return

        device_fp = self.system_initializer.device_fingerprint

        # 获取设备信息
        serial_number = device_fp.get_serial_number()
        mac_address = device_fp.get_mac_address_from_efuse()
        is_activated = device_fp.is_activated()
        self.is_activated = is_activated

        # 显示设备信息
        print("📱 设备信息:")
        print(f"   序列号: {serial_number if serial_number else '--'}")
        print(f"   MAC地址: {mac_address if mac_address else '--'}")
        status_text = "已激活" if is_activated else "未激活"
        print(f"   激活状态: {status_text}")

        activated_text = "已激活" if is_activated else "未激活"
        self._log_and_print(
            f"📱 设备信息更新 - 序列号: {serial_number}, " f"激活状态: {activated_text}"
        )

    async def _check_activation_status(self) -> bool:
        """
        检查激活状态.
        """
        if self.is_activated:
            self._log_and_print("\n设备已激活，无需重复激活")
            return True
        else:
            # 检查是否有激活数据
            activation_data = self.system_initializer.get_activation_data()
            if activation_data:
                self._log_and_print("\n检测到激活请求，准备激活流程")
                return await self._start_activation_process(activation_data)
            else:
                self._log_and_print("\n未获取到激活数据")
                print("错误: 未获取到激活数据，请检查网络连接")
                return False

    async def _start_activation_process(self, activation_data: dict) -> bool:
        """
        开始激活流程.
        """
        try:
            self.activation_data = activation_data

            # 显示激活信息
            self._show_activation_info(activation_data)

            # 初始化设备激活器
            config_manager = self.system_initializer.get_config_manager()
            self.device_activator = DeviceActivator(config_manager)

            # 开始激活流程
            self._log_and_print("\n开始设备激活流程...")
            print("正在连接激活服务器，请保持网络连接...")

            activation_success = await asyncio.to_thread(
                self.device_activator.process_activation, activation_data
            )

            if activation_success:
                self._log_and_print("\n设备激活成功！")
                self._print_activation_success()
                return True
            else:
                self._log_and_print("\n设备激活失败")
                self._print_activation_failure()
                return False

        except Exception as e:
            self.logger.error(f"激活流程异常: {e}", exc_info=True)
            self._log_and_print(f"\n激活异常: {e}")
            return False

    def _show_activation_info(self, activation_data: dict):
        """
        显示激活信息.
        """
        code = activation_data.get("code", "------")
        message = activation_data.get("message", "请访问xiaozhi.me输入验证码")

        print("\n" + "=" * 60)
        print("设备激活信息")
        print("=" * 60)
        print(f"激活验证码: {code}")
        print(f"激活说明: {message}")
        print("=" * 60)

        # 格式化显示验证码（每个字符间加空格）
        formatted_code = " ".join(code)
        print(f"\n验证码（请在网站输入）: {formatted_code}")
        print("\n请按以下步骤完成激活:")
        print("1. 打开浏览器访问 xiaozhi.me")
        print("2. 登录您的账户")
        print("3. 选择添加设备")
        print(f"4. 输入验证码: {formatted_code}")
        print("5. 确认添加设备")
        print("\n等待激活确认中，请在网站完成操作...")

        self._log_and_print(f"激活验证码: {code}")
        self._log_and_print(f"激活说明: {message}")

    def _print_activation_success(self):
        """
        打印激活成功信息.
        """
        print("\n" + "=" * 60)
        print("设备激活成功！")
        print("=" * 60)
        print("设备已成功添加到您的账户")
        print("配置已自动更新")
        print("准备启动小智AI客户端...")
        print("=" * 60)

    def _print_activation_failure(self):
        """
        打印激活失败信息.
        """
        print("\n" + "=" * 60)
        print("设备激活失败")
        print("=" * 60)
        print("可能的原因:")
        print("• 网络连接不稳定")
        print("• 验证码输入错误或已过期")
        print("• 服务器暂时不可用")
        print("\n解决方案:")
        print("• 检查网络连接")
        print("• 重新运行程序获取新验证码")
        print("• 确保在网站正确输入验证码")
        print("=" * 60)

    def _log_and_print(self, message: str):
        """
        同时记录日志和打印到终端.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        print(log_message)
        self.logger.info(message)

    def get_activation_result(self) -> dict:
        """
        获取激活结果.
        """
        device_fingerprint = None
        config_manager = None

        if self.system_initializer:
            device_fingerprint = self.system_initializer.device_fingerprint
            config_manager = self.system_initializer.config_manager

        return {
            "is_activated": self.is_activated,
            "device_fingerprint": device_fingerprint,
            "config_manager": config_manager,
        }
