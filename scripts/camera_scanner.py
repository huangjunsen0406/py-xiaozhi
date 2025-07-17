#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 文件名: camera_scanner.py

import json
import logging
import sys
import time
from pathlib import Path

import cv2

# 导入ConfigManager类
from src.utils.config_manager import ConfigManager

# 添加项目根目录到系统路径，以便导入src中的模块
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# 设置日志记录
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("CameraScanner")


def get_camera_capabilities(cam):
    """
    获取摄像头的参数和能力.
    """
    capabilities = {}

    # 获取可用的分辨率
    standard_resolutions = [
        (640, 480),  # VGA
        (800, 600),  # SVGA
        (1024, 768),  # XGA
        (1280, 720),  # HD
        (1280, 960),  # 4:3 HD
        (1920, 1080),  # Full HD
        (2560, 1440),  # QHD
        (3840, 2160),  # 4K UHD
    ]

    supported_resolutions = []
    original_width = int(cam.get(cv2.CAP_PROP_FRAME_WIDTH))
    original_height = int(cam.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # 记录原始分辨率
    capabilities["default_resolution"] = (original_width, original_height)

    # 测试标准分辨率
    for width, height in standard_resolutions:
        cam.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        actual_width = int(cam.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cam.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # 如果设置成功（实际分辨率与请求的相同）
        if actual_width == width and actual_height == height:
            supported_resolutions.append((width, height))

    # 恢复原始分辨率
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, original_width)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, original_height)

    capabilities["supported_resolutions"] = supported_resolutions

    # 获取帧率
    fps = int(cam.get(cv2.CAP_PROP_FPS))
    capabilities["fps"] = fps if fps > 0 else 30  # 默认为30fps

    # 获取后端名称
    backend_name = cam.getBackendName()
    capabilities["backend"] = backend_name

    return capabilities


def detect_cameras():
    """
    检测并列出所有可用摄像头.
    """
    print("\n===== 摄像头设备检测 =====\n")

    # 获取ConfigManager实例
    config_manager = ConfigManager.get_instance()

    # 获取当前相机配置
    current_camera_config = config_manager.get_config("CAMERA", {})
    logger.info(f"当前相机配置: {current_camera_config}")

    # 显示当前配置
    if current_camera_config:
        print("当前摄像头配置:")
        print(f"  - 索引: {current_camera_config.get('camera_index', '未设置')}")
        print(f"  - 分辨率: {current_camera_config.get('frame_width', '未设置')}x{current_camera_config.get('frame_height', '未设置')}")
        print(f"  - 帧率: {current_camera_config.get('fps', '未设置')}")
        print(f"  - VL模型: {current_camera_config.get('models', '未设置')}")
        print("")

    # 存储找到的设备
    camera_devices = []

    # 尝试打开多个摄像头索引
    max_cameras_to_check = 10  # 最多检查10个摄像头索引

    for i in range(max_cameras_to_check):
        try:
            # 尝试打开摄像头
            cap = cv2.VideoCapture(i)

            if cap.isOpened():
                # 获取摄像头信息
                device_name = f"Camera {i}"
                try:
                    # 在某些系统上可能可以获取设备名称
                    device_name = cap.getBackendName() + f" Camera {i}"
                except Exception as e:
                    logger.warning(f"获取设备{i}名称失败: {e}")

                # 读取一帧以确保摄像头正常工作
                ret, frame = cap.read()
                if not ret:
                    print(f"设备 {i}: 打开成功但无法读取画面，跳过")
                    cap.release()
                    continue

                # 获取摄像头能力
                capabilities = get_camera_capabilities(cap)

                # 打印设备信息
                width, height = capabilities["default_resolution"]
                resolutions_str = ", ".join(
                    [f"{w}x{h}" for w, h in capabilities["supported_resolutions"]]
                )

                print(f"设备 {i}: {device_name}")
                print(f"  - 默认分辨率: {width}x{height}")
                print(f"  - 支持分辨率: {resolutions_str}")
                print(f"  - 帧率: {capabilities['fps']}")
                print(f"  - 后端: {capabilities['backend']}")
                
                # 标记当前配置使用的摄像头
                current_index = current_camera_config.get('camera_index')
                if current_index == i:
                    print(f"  - 📹 当前配置使用的摄像头")
                
                print("")

                # 添加到设备列表
                camera_devices.append(
                    {"index": i, "name": device_name, "capabilities": capabilities}
                )

                # 测试摄像头功能
                print(f"正在测试设备 {i} 的摄像头功能...")
                try:
                    # 快速测试 - 读取几帧
                    test_frames = 0
                    start_time = time.time()
                    
                    while test_frames < 10 and time.time() - start_time < 2:
                        ret, frame = cap.read()
                        if ret:
                            test_frames += 1
                        else:
                            break
                    
                    if test_frames >= 5:
                        print(f"  ✓ 摄像头功能正常 (测试读取 {test_frames} 帧)")
                    else:
                        print(f"  ⚠ 摄像头功能可能异常 (仅读取 {test_frames} 帧)")
                        
                except Exception as e:
                    print(f"  ✗ 摄像头功能测试失败: {e}")

                # 询问是否显示预览
                print(f"是否显示设备 {i} 的预览画面？(y/n，默认n): ", end="")
                show_preview = input().strip().lower()
                
                if show_preview == 'y':
                    print(f"正在显示设备 {i} 的预览画面，按 'q' 键或等待3秒继续...")
                    preview_start = time.time()

                    while time.time() - preview_start < 3:
                        ret, frame = cap.read()
                        if ret:
                            cv2.imshow(f"Camera {i} Preview", frame)
                            if cv2.waitKey(1) & 0xFF == ord("q"):
                                break

                    cv2.destroyAllWindows()
                
                cap.release()

            else:
                # 如果连续两个索引无法打开摄像头，则认为没有更多摄像头了
                consecutive_failures = 0
                for j in range(i, i + 2):
                    temp_cap = cv2.VideoCapture(j)
                    if not temp_cap.isOpened():
                        consecutive_failures += 1
                    temp_cap.release()

                if consecutive_failures >= 2 and i > 0:
                    break

        except Exception as e:
            print(f"检测设备 {i} 时出错: {e}")

    # 总结找到的设备
    print("\n===== 设备总结 =====\n")

    if not camera_devices:
        print("未找到可用的摄像头设备！")
        return None

    print(f"找到 {len(camera_devices)} 个摄像头设备:")
    for device in camera_devices:
        width, height = device["capabilities"]["default_resolution"]
        print(f"  - 设备 {device['index']}: {device['name']}")
        print(f"    分辨率: {width}x{height}")

    # 推荐最佳设备
    print("\n===== 推荐设备 =====\n")

    # 首选高清摄像头，其次是分辨率最高的
    recommended_camera = None
    highest_resolution = 0

    for device in camera_devices:
        width, height = device["capabilities"]["default_resolution"]
        resolution = width * height

        # 如果是HD或以上分辨率
        if width >= 1280 and height >= 720:
            if resolution > highest_resolution:
                highest_resolution = resolution
                recommended_camera = device
        elif recommended_camera is None or resolution > highest_resolution:
            highest_resolution = resolution
            recommended_camera = device

    # 打印推荐设备
    if recommended_camera:
        r_width, r_height = recommended_camera["capabilities"]["default_resolution"]
        print(
            f"推荐摄像头: 设备 {recommended_camera['index']} "
            f"({recommended_camera['name']})"
        )
        print(f"  - 分辨率: {r_width}x{r_height}")
        print(f"  - 帧率: {recommended_camera['capabilities']['fps']}")

    # 从现有配置中获取VL API信息
    vl_url = current_camera_config.get(
        "Loacl_VL_url", "https://open.bigmodel.cn/api/paas/v4/"
    )
    vl_api_key = current_camera_config.get("VLapi_key", "你自己的key")
    model = current_camera_config.get("models", "glm-4v-plus")

    # 生成配置文件示例
    print("\n===== 配置文件示例 =====\n")

    if recommended_camera:
        new_camera_config = {
            "camera_index": recommended_camera["index"],
            "frame_width": r_width,
            "frame_height": r_height,
            "fps": recommended_camera["capabilities"]["fps"],
            "Local_VL_url": vl_url,  # 保留原有值
            "VLapi_key": vl_api_key,  # 保留原有值
            "models": model,  # 保留原有值
        }

        print("推荐的摄像头配置:")
        print(json.dumps(new_camera_config, indent=2, ensure_ascii=False))

        # 比较配置变化
        print("\n===== 配置变化对比 =====\n")
        current_index = current_camera_config.get('camera_index')
        current_width = current_camera_config.get('frame_width')
        current_height = current_camera_config.get('frame_height')
        current_fps = current_camera_config.get('fps')
        
        changes = []
        if current_index != recommended_camera["index"]:
            changes.append(f"摄像头索引: {current_index} → {recommended_camera['index']}")
        if current_width != r_width or current_height != r_height:
            changes.append(f"分辨率: {current_width}x{current_height} → {r_width}x{r_height}")
        if current_fps != recommended_camera["capabilities"]["fps"]:
            changes.append(f"帧率: {current_fps} → {recommended_camera['capabilities']['fps']}")
        
        if changes:
            print("检测到以下配置变化:")
            for change in changes:
                print(f"  - {change}")
        else:
            print("推荐配置与当前配置相同，无需更新")

        # 询问是否更新配置文件
        if changes:
            print("\n是否要更新配置文件中的摄像头配置？(y/n): ", end="")
            choice = input().strip().lower()

            if choice == "y":
                try:
                    # 使用ConfigManager更新配置
                    success = config_manager.update_config("CAMERA", new_camera_config)

                    if success:
                        print("\n✓ 摄像头配置已成功更新到config.json!")
                        print("\n===== 最新配置 =====\n")
                        updated_config = config_manager.get_config("CAMERA", {})
                        print(json.dumps(updated_config, indent=2, ensure_ascii=False))
                    else:
                        print("\n✗ 更新摄像头配置失败!")

                except Exception as e:
                    logger.error(f"更新配置时出错: {e}")
                    print(f"\n✗ 更新配置时出错: {e}")
            else:
                print("\n配置未更新")
    else:
        print("未找到推荐的摄像头配置")

    return camera_devices


if __name__ == "__main__":
    try:
        cameras = detect_cameras()
        if cameras:
            print(f"\n检测到 {len(cameras)} 个摄像头设备！")
        else:
            print("\n未检测到可用的摄像头设备！")
    except Exception as e:
        logger.error(f"检测过程中出错: {e}")
        print(f"检测过程中出错: {e}")
