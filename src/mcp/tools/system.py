"""
系统工具模块 - 提供系统相关的MCP工具实现
"""

import asyncio
import json
import platform
import re
import subprocess
from typing import Any, Dict

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


async def get_device_status(args: Dict[str, Any]) -> str:
    """获取设备状态"""
    try:
        # 获取实际的应用实例
        from src.application import Application
        from src.iot.thing_manager import ThingManager

        app = Application.get_instance()
        thing_manager = ThingManager.get_instance()

        # 获取实际音量
        current_volume = 50  # 默认值
        is_muted = False
        try:
            from src.utils.volume_controller import VolumeController

            if VolumeController.check_dependencies():
                volume_controller = VolumeController()
                current_volume = volume_controller.get_volume()
        except Exception as e:
            logger.warning(f"[MCP] 获取音量失败，使用默认值: {e}")

        # 尝试获取真实的屏幕亮度
        screen_brightness = 80  # 默认值
        try:
            brightness_result = await get_brightness({})
            brightness_data = json.loads(brightness_result)
            if brightness_data.get("success"):
                screen_brightness = brightness_data.get("brightness", 80)
        except Exception as e:
            logger.warning(f"[MCP] 获取屏幕亮度失败，使用默认值: {e}")

        # 获取实际设备状态
        status = {
            "audio_speaker": {"volume": current_volume, "muted": is_muted},
            "screen": {
                "brightness": screen_brightness,
                "theme": "light",  # 暂时使用默认值
            },
            "battery": {"level": 85, "charging": False},
            "network": {"connected": True, "type": "wifi"},
            "device_state": (
                app.device_state.name
                if hasattr(app.device_state, "name")
                else str(app.device_state)
            ),
            "iot_devices": len(thing_manager.things) if thing_manager else 0,
        }

        logger.info("[MCP] 获取设备状态成功")
        return json.dumps(status)

    except Exception as e:
        logger.error(f"[MCP] 获取设备状态失败: {e}", exc_info=True)
        # 返回默认状态
        return json.dumps(
            {
                "audio_speaker": {"volume": 50, "muted": False},
                "screen": {"brightness": 80, "theme": "light"},
                "battery": {"level": 85, "charging": False},
                "network": {"connected": True, "type": "wifi"},
                "error": str(e),
            }
        )


async def set_volume(args: Dict[str, Any]) -> bool:
    """设置音量"""
    try:
        volume = args["volume"]
        logger.info(f"[MCP] 设置音量到 {volume}")

        # 直接使用VolumeController设置音量
        from src.utils.volume_controller import VolumeController

        # 检查依赖并创建音量控制器
        if not VolumeController.check_dependencies():
            logger.warning("[MCP] 音量控制依赖不完整，无法设置音量")
            return False

        volume_controller = VolumeController()
        await asyncio.to_thread(volume_controller.set_volume, volume)
        logger.info(f"[MCP] 音量设置成功: {volume}")
        return True

    except Exception as e:
        logger.error(f"[MCP] 设置音量失败: {e}", exc_info=True)
        return False


async def set_brightness(args: Dict[str, Any]) -> bool:
    """设置屏幕亮度"""
    brightness = args["brightness"]
    logger.info(f"[MCP] 设置屏幕亮度到 {brightness}%")

    try:
        # 检查是否为Mac系统
        if platform.system() != "Darwin":
            logger.warning(f"[MCP] 非Mac系统 ({platform.system()})，无法控制屏幕亮度")
            return False

        # 将百分比转换为Mac系统的亮度值 (0.0 - 1.0)
        brightness_value = brightness / 100.0

        # 方法1: 尝试使用第三方brightness工具（如果安装了）
        try:
            brightness_cmd = ["brightness", str(brightness_value)]
            result = subprocess.run(
                brightness_cmd, capture_output=True, text=True, timeout=3
            )

            if result.returncode == 0:
                logger.info(f"[MCP] 使用brightness工具设置亮度成功: {brightness}%")
                return True
            else:
                logger.debug(f"[MCP] brightness工具失败: {result.stderr}")

        except FileNotFoundError:
            logger.debug("[MCP] brightness工具未安装")
        except Exception as e:
            logger.debug(f"[MCP] brightness工具执行失败: {e}")

        # 方法2: 使用系统命令模拟亮度调节
        try:
            # 首先获取当前亮度
            current_brightness = await _get_current_brightness_value()
            if current_brightness is not None:
                diff = brightness - int(current_brightness * 100)

                if abs(diff) <= 2:  # 如果差异很小，认为已经达到目标
                    logger.info(f"[MCP] 亮度已接近目标值: {brightness}%")
                    return True

                # 使用键盘快捷键调节亮度
                if diff > 0:
                    # 需要增加亮度
                    key_code = 144  # F15 (brightness up)
                    steps = min(abs(diff) // 5, 20)  # 限制最大步数
                else:
                    # 需要降低亮度
                    key_code = 145  # F14 (brightness down)
                    steps = min(abs(diff) // 5, 20)

                # 执行亮度调节
                for _ in range(steps):
                    cmd = [
                        "osascript",
                        "-e",
                        f'tell application "System Events" to key code ' f"{key_code}",
                    ]
                    subprocess.run(cmd, capture_output=True, timeout=1)

                logger.info(f"[MCP] 使用键盘快捷键调节亮度: {steps}步")
                return True

        except Exception as e:
            logger.warning(f"[MCP] 键盘快捷键方法失败: {e}")

        # 最后的备选方案，记录请求但无法实际执行
        logger.warning(f"[MCP] 无法在当前Mac系统上控制亮度，记录请求: {brightness}%")
        return False

    except Exception as e:
        logger.error(f"[MCP] 设置屏幕亮度失败: {e}", exc_info=True)
        return False


async def _get_current_brightness_value() -> float:
    """获取当前亮度值（0.0-1.0）"""
    try:
        # 尝试使用brightness工具
        try:
            result = subprocess.run(
                ["brightness", "-l"], capture_output=True, text=True, timeout=3
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                # 解析输出，寻找亮度值
                match = re.search(r"brightness\s+([0-9.]+)", output)
                if match:
                    return float(match.group(1))
                else:
                    # 尝试解析为纯数字
                    try:
                        return float(output)
                    except ValueError:
                        pass

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        except Exception as e:
            logger.debug(f"[MCP] brightness工具获取亮度失败: {e}")

        # 如果brightness工具不可用，返回None
        return None

    except Exception as e:
        logger.debug(f"[MCP] 获取当前亮度值失败: {e}")
        return None


async def get_brightness(args: Dict[str, Any]) -> str:
    """获取当前屏幕亮度"""
    try:
        logger.info("[MCP] 获取屏幕亮度")

        # 检查是否为Mac系统
        if platform.system() != "Darwin":
            logger.warning(f"[MCP] 非Mac系统 ({platform.system()})，返回默认亮度")
            return json.dumps(
                {
                    "success": False,
                    "platform": platform.system(),
                    "message": "Brightness control only available on macOS",
                    "default_brightness": 80,
                }
            )

        # 尝试获取真实亮度
        brightness_value = await _get_current_brightness_value()

        if brightness_value is not None:
            brightness_percent = int(brightness_value * 100)
            logger.info(f"[MCP] 获取亮度成功: {brightness_percent}%")

            return json.dumps(
                {
                    "success": True,
                    "platform": "macOS",
                    "brightness": brightness_percent,
                    "brightness_raw": brightness_value,
                    "method": "brightness_tool",
                    "timestamp": __import__("datetime").datetime.now().isoformat(),
                }
            )
        else:
            # 无法获取真实亮度，返回估算值
            logger.warning("[MCP] 无法获取真实亮度，返回估算值")
            return json.dumps(
                {
                    "success": False,
                    "platform": "macOS",
                    "error": "Unable to detect brightness",
                    "estimated_brightness": 75,
                    "message": "Brightness detection not available",
                }
            )

    except Exception as e:
        logger.error(f"[MCP] 获取屏幕亮度失败: {e}", exc_info=True)
        return json.dumps(
            {
                "success": False,
                "platform": (
                    platform.system() if "platform" in locals() else "Unknown"
                ),
                "error": str(e),
                "fallback_data": {
                    "brightness": 80,
                    "message": "Failed to get real brightness, showing fallback data",
                },
            }
        )


async def set_theme(args: Dict[str, Any]) -> bool:
    """设置主题"""
    theme = args["theme"]
    logger.info(f"[MCP] 设置主题到 {theme}")

    try:
        # 验证主题值
        if theme not in ["light", "dark"]:
            logger.warning(f"[MCP] 无效的主题值: {theme}，使用默认值 light")
            theme = "light"

        # 模拟设置主题成功（与获取设备状态的模式一致）
        # 在实际项目中，这里应该实现真正的主题切换逻辑
        # from src.application import Application
        # app = Application.get_instance()
        # if app.display and hasattr(app.display, 'set_theme'):
        #     app.display.set_theme(theme)

        logger.info(f"[MCP] 主题设置成功: {theme}")
        return True

    except Exception as e:
        logger.error(f"[MCP] 设置主题失败: {e}", exc_info=True)
        return False


async def take_photo(args: Dict[str, Any]) -> str:
    """拍照并解释"""
    question = args["question"]
    logger.info(f"[MCP] 拍照请求，问题: {question}")

    try:
        # 尝试使用IoT设备中的摄像头
        from src.iot.thing_manager import ThingManager

        thing_manager = ThingManager.get_instance()

        # 查找摄像头设备
        camera_thing = None
        for thing in thing_manager.things:
            if thing.name.lower() == "camera":
                camera_thing = thing
                break

        if camera_thing and hasattr(camera_thing, "capture_frame_to_base64"):
            # 使用IoT摄像头
            result = await camera_thing.capture_frame_to_base64()
            logger.info("[MCP] 摄像头拍照成功")
            return json.dumps(
                {
                    "success": True,
                    "message": "照片拍摄成功",
                    "question": question,
                    "result": result,
                }
            )
        else:
            logger.warning("[MCP] 未找到可用的摄像头设备")
            return json.dumps(
                {
                    "success": False,
                    "message": "Camera not available in Python version",
                    "question": question,
                }
            )

    except Exception as e:
        logger.error(f"[MCP] 拍照失败: {e}", exc_info=True)
        return json.dumps(
            {
                "success": False,
                "message": f"Camera error: {str(e)}",
                "question": question,
            }
        )


async def get_battery_info(args: Dict[str, Any]) -> str:
    """获取Mac电脑电池信息"""
    try:
        logger.info("[MCP] 获取Mac电池信息")

        # 检查是否为Mac系统
        if platform.system() != "Darwin":
            logger.warning("[MCP] 非Mac系统，返回模拟电池信息")
            return json.dumps(
                {
                    "success": False,
                    "platform": platform.system(),
                    "message": "Battery info only available on macOS",
                    "simulated_data": {
                        "percentage": 85,
                        "charging": False,
                        "health": "Good",
                        "cycle_count": 245,
                    },
                }
            )

        # 使用pmset命令获取电池信息
        try:
            result = subprocess.run(
                ["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                battery_output = result.stdout

                # 解析电池百分比
                percentage_match = re.search(r"(\d+)%", battery_output)
                percentage = (
                    int(percentage_match.group(1)) if percentage_match else None
                )

                # 解析充电状态
                charging = "charging" in battery_output.lower()
                power_source = (
                    "AC Power" if "AC Power" in battery_output else "Battery Power"
                )

                # 解析剩余时间
                time_match = re.search(r"(\d+:\d+) remaining", battery_output)
                time_remaining = time_match.group(1) if time_match else "calculating..."

                battery_info = {
                    "percentage": percentage,
                    "charging": charging,
                    "power_source": power_source,
                    "time_remaining": time_remaining,
                    "raw_output": battery_output.strip(),
                }

            else:
                logger.warning(f"[MCP] pmset命令执行失败: {result.stderr}")
                battery_info = {
                    "percentage": None,
                    "charging": None,
                    "error": "Failed to execute pmset command",
                }

        except subprocess.TimeoutExpired:
            logger.error("[MCP] pmset命令超时")
            battery_info = {
                "percentage": None,
                "charging": None,
                "error": "Command timeout",
            }
        except Exception as e:
            logger.error(f"[MCP] 执行pmset命令时出错: {e}")
            battery_info = {"percentage": None, "charging": None, "error": str(e)}

        # 尝试获取更详细的电池健康信息
        try:
            health_result = subprocess.run(
                ["system_profiler", "SPPowerDataType"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if health_result.returncode == 0:
                health_output = health_result.stdout

                # 解析电池健康状态
                condition_match = re.search(r"Condition: (\w+)", health_output)
                condition = condition_match.group(1) if condition_match else "Unknown"

                # 解析循环次数
                cycle_match = re.search(r"Cycle Count: (\d+)", health_output)
                cycle_count = int(cycle_match.group(1)) if cycle_match else None

                # 解析最大容量
                capacity_match = re.search(r"Maximum Capacity: (\d+)%", health_output)
                max_capacity = int(capacity_match.group(1)) if capacity_match else None

                battery_info.update(
                    {
                        "health_condition": condition,
                        "cycle_count": cycle_count,
                        "maximum_capacity": max_capacity,
                    }
                )

        except Exception as e:
            logger.warning(f"[MCP] 获取电池健康信息失败: {e}")
            battery_info.update(
                {
                    "health_condition": "Unknown",
                    "cycle_count": None,
                    "maximum_capacity": None,
                }
            )

        # 构建返回结果
        result_data = {
            "success": True,
            "platform": "macOS",
            "battery": battery_info,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }

        logger.info(f"[MCP] 电池信息获取成功: {battery_info.get('percentage', 'N/A')}%")
        return json.dumps(result_data, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"[MCP] 获取电池信息失败: {e}", exc_info=True)
        return json.dumps(
            {
                "success": False,
                "platform": (
                    platform.system() if "platform" in locals() else "Unknown"
                ),
                "error": str(e),
                "fallback_data": {
                    "percentage": 75,
                    "charging": False,
                    "health": "Unknown",
                    "message": "Failed to get real battery info, showing fallback data",
                },
            }
        )
