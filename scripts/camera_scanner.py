#!/usr/bin/env python3
"""检测可用摄像头（OpenCV/V4L2 + 可选 picamera2），并写回 CAMERA 配置."""

import argparse
import logging
import sys
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config_manager import initialize_config  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("CameraScanner")


def main() -> int:
    parser = argparse.ArgumentParser(description="扫描摄像头并可选写入配置")
    parser.add_argument(
        "--select",
        type=int,
        default=None,
        help="选择列表中的序号（从 0 开始）写入配置",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "opencv", "picamera2"],
        default=None,
        help="强制写入 CAMERA.backend",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="强制写入 CAMERA.device（如 /dev/video0）",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="对当前配置或 --select 结果试拍一帧",
    )
    args = parser.parse_args()

    config = initialize_config()
    from src.mcp.tools.camera.capture_backend import (
        CaptureConfig,
        apply_device_selection,
        capture_jpeg,
        list_camera_devices,
        load_capture_config,
    )

    current = load_capture_config()
    print("\n===== 当前 CAMERA 配置 =====")
    print(f"  backend={current.backend}")
    print(f"  device={current.device!r}")
    print(f"  camera_index={current.camera_index}")
    print(f"  size={current.frame_width}x{current.frame_height}")
    print(f"  warm_up_frames={current.warm_up_frames}")

    print("\n===== 扫描设备 =====\n")
    devices = list_camera_devices()
    if not devices:
        print("未发现可用摄像头。")
        print("提示:")
        print("  - USB: 确认已插入，ls /dev/video*")
        print("  - 树莓派 CSI: sudo apt install python3-picamera2")
        print("  - 用户需在 video 组: sudo usermod -aG video $USER && newgrp video")
        return 1

    for i, d in enumerate(devices):
        print(f"  [{i}] {d.name}  key={d.key}  kind={d.kind}")

    selected_key = None
    if args.device:
        selected_key = args.device
    elif args.backend == "picamera2":
        selected_key = "picamera2"
    elif args.select is not None:
        if args.select < 0 or args.select >= len(devices):
            print(f"--select 超出范围 0..{len(devices) - 1}")
            return 1
        selected_key = devices[args.select].key

    if selected_key is not None:
        updates = apply_device_selection(selected_key)
        if args.backend:
            updates["CAMERA.backend"] = args.backend
        for path, value in updates.items():
            config.update_config(path, value)
        print("\n已写入配置:")
        for path, value in updates.items():
            print(f"  {path} = {value!r}")

    if args.test or selected_key is not None:
        print("\n===== 试拍 =====")
        cfg = load_capture_config()
        if selected_key is not None:
            # 用刚写入的选择
            u = apply_device_selection(selected_key)
            if args.backend:
                u["CAMERA.backend"] = args.backend
            cfg = CaptureConfig(
                camera_index=int(u.get("CAMERA.camera_index", 0) or 0),
                device=str(u.get("CAMERA.device", "") or ""),
                backend=str(u.get("CAMERA.backend", "auto")),
                frame_width=cfg.frame_width,
                frame_height=cfg.frame_height,
                warm_up_frames=cfg.warm_up_frames,
            )
        jpeg = capture_jpeg(cfg)
        if not jpeg:
            print("试拍失败")
            return 2
        out = project_root / "camera_scan_test.jpg"
        out.write_bytes(jpeg)
        print(f"试拍成功: {out} ({len(jpeg)} bytes)")

    print("\n完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
