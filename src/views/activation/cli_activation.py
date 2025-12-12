# -*- coding: utf-8 -*-
"""
CLI模式设备激活流程 提供与GUI激活窗口相同的功能，但使用纯终端输出.
"""

from datetime import datetime
from typing import Optional

from src.activation import ActivationService
from src.logging import get_logger

logger = get_logger()


class CLIActivation:
    """
    CLI模式设备激活处理器.
    """

    def __init__(self, activation_service: Optional[ActivationService] = None):
        # 使用统一的激活服务
        self.activation_service = activation_service

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

            # 如果已经提供了ActivationService实例，直接使用
            if self.activation_service:
                self._log_and_print("使用已初始化的系统")
                self._update_device_info()
                return await self._start_activation_process()
            else:
                # 否则创建新的实例并运行初始化
                self._log_and_print("开始系统初始化流程")
                self.activation_service = await ActivationService.get_instance()

                # 运行初始化流程
                init_result = await self.activation_service.initialize()

                if init_result.get("success", False):
                    self._update_device_info()

                    # 显示状态消息
                    status_message = init_result.get("message", "")
                    if status_message:
                        self._log_and_print(status_message)

                    # 检查是否需要激活
                    if init_result.get("need_activation_ui", True):
                        return await self._start_activation_process()
                    else:
                        # 无需激活，直接完成
                        self.is_activated = True
                        self._log_and_print("设备已激活，无需进一步操作")
                        return True
                else:
                    error_msg = init_result.get("error", "初始化失败")
                    self._log_and_print(f"错误: {error_msg}")
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

    def _update_device_info(self):
        """
        更新设备信息显示.
        """
        if not self.activation_service:
            return

        # 获取设备信息
        serial_number = self.activation_service.get_serial_number()
        mac_address = self.activation_service.get_mac_address()

        # 获取激活状态
        activation_status = self.activation_service.get_activation_status()
        local_activated = activation_status.get("local_activated", False)
        server_activated = activation_status.get("server_activated", False)
        status_consistent = activation_status.get("status_consistent", True)

        # 更新激活状态
        self.is_activated = local_activated

        # 显示设备信息
        print("📱 设备信息:")
        print(f"   序列号: {serial_number if serial_number else '--'}")
        print(f"   MAC地址: {mac_address if mac_address else '--'}")

        # 显示激活状态
        if not status_consistent:
            if local_activated and not server_activated:
                status_text = "状态不一致(需重新激活)"
            else:
                status_text = "状态不一致(已自动修复)"
        else:
            status_text = "已激活" if local_activated else "未激活"

        print(f"   激活状态: {status_text}")

    async def _start_activation_process(self) -> bool:
        """
        开始激活流程.
        """
        try:
            # 获取激活数据
            activation_data = self.activation_service.get_activation_data()

            if not activation_data:
                self._log_and_print("\n未获取到激活数据")
                print("错误: 未获取到激活数据，请检查网络连接")
                return False

            self.activation_data = activation_data

            # 显示激活信息
            self._show_activation_info(activation_data)

            # 开始激活流程
            self._log_and_print("\n开始设备激活流程...")
            print("正在连接激活服务器，请保持网络连接...")

            activation_success = await self.activation_service.activate(activation_data)

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
        return {
            "is_activated": self.is_activated,
            "activation_service": self.activation_service,
            "config_manager": self.activation_service.get_config_manager() if self.activation_service else None,
        }
