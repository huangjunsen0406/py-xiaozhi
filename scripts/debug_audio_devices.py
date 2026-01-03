#!/usr/bin/env python3
"""诊断 Ubuntu/Linux 上的音频设备问题.

在 Ubuntu 上运行此脚本来查看 sounddevice 如何报告音频设备。
用法: python scripts/debug_audio_devices.py
"""
import sounddevice as sd

print("=" * 60)
print("sounddevice 版本:", sd.__version__)
print("=" * 60)

# 默认设备信息
print("\n默认设备:")
print(f"  sd.default.device = {sd.default.device}")
print(f"  类型: {type(sd.default.device)}")

# 获取所有设备
devices = sd.query_devices()
print(f"\n共找到 {len(devices)} 个设备:\n")

input_devices = []
output_devices = []

for i, d in enumerate(devices):
    name = d.get("name", "Unknown")
    in_ch = d.get("max_input_channels", 0)
    out_ch = d.get("max_output_channels", 0)
    sr = d.get("default_samplerate", 0)
    hostapi = d.get("hostapi", -1)

    print(f"[{i}] {name}")
    print(f"    输入通道: {in_ch}, 输出通道: {out_ch}")
    print(f"    采样率: {sr}, hostapi: {hostapi}")

    if in_ch > 0:
        input_devices.append((i, name, in_ch))
    if out_ch > 0:
        output_devices.append((i, name, out_ch))
    print()

print("=" * 60)
print(f"输入设备列表 ({len(input_devices)} 个):")
for idx, name, ch in input_devices:
    print(f"  [{idx}] {name} ({ch}ch)")

print(f"\n输出设备列表 ({len(output_devices)} 个):")
for idx, name, ch in output_devices:
    print(f"  [{idx}] {name} ({ch}ch)")

# Host APIs
print("\n" + "=" * 60)
print("Host APIs:")
for i, api in enumerate(sd.query_hostapis()):
    print(f"  [{i}] {api['name']}")
    print(f"      默认输入: {api['default_input_device']}")
    print(f"      默认输出: {api['default_output_device']}")
    print(f"      设备数: {api['device_count']}")
