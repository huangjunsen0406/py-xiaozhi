#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pyaudio


def detect_audio_devices():
    """检测并列出所有音频设备."""
    p = pyaudio.PyAudio()

    print("\n===== 音频设备检测 =====\n")

    # 存储找到的设备
    input_devices = []
    output_devices = []

    # 列出所有设备
    for i in range(p.get_device_count()):
        dev_info = p.get_device_info_by_index(i)

        # 打印设备信息
        print(f"设备 {i}: {dev_info['name']}")
        print(f"  - 输入通道: {dev_info['maxInputChannels']}")
        print(f"  - 输出通道: {dev_info['maxOutputChannels']}")
        print(f"  - 默认采样率: {dev_info['defaultSampleRate']}")

        # 识别输入设备（麦克风）
        if dev_info["maxInputChannels"] > 0:
            input_devices.append((i, dev_info["name"]))
            if "USB" in dev_info["name"]:
                print("  - 可能是USB麦克风 ?")

        # 识别输出设备（扬声器）
        if dev_info["maxOutputChannels"] > 0:
            output_devices.append((i, dev_info["name"]))
            if "bcm2835 Headphones" in dev_info["name"]:
                print("  - 可能是内置耳机输出 ?")
            elif "USB" in dev_info["name"] and dev_info["maxOutputChannels"] > 0:
                print("  - 可能是USB扬声器 ?")

        print("")

    # 总结找到的设备
    print("\n===== 设备总结 =====\n")

    print("找到的输入设备（麦克风）:")
    for idx, name in input_devices:
        print(f"  - 设备 {idx}: {name}")

    print("\n找到的输出设备（扬声器）:")
    for idx, name in output_devices:
        print(f"  - 设备 {idx}: {name}")

    # 推荐设备
    print("\n推荐设备配置:")

    # 推荐麦克风
    recommended_mic = None
    for idx, name in input_devices:
        if "USB" in name:
            recommended_mic = (idx, name)
            break
    if recommended_mic is None and input_devices:
        recommended_mic = input_devices[0]

    # 推荐扬声器
    recommended_speaker = None
    for idx, name in output_devices:
        if "bcm2835 Headphones" in name:
            recommended_speaker = (idx, name)
            break
    if recommended_speaker is None and output_devices:
        recommended_speaker = output_devices[0]

    if recommended_mic:
        print(f"  - 麦克风: 设备 {recommended_mic[0]} ({recommended_mic[1]})")
    else:
        print("  - 未找到可用麦克风")

    if recommended_speaker:
        print(f"  - 扬声器: 设备 {recommended_speaker[0]} ({recommended_speaker[1]})")
    else:
        print("  - 未找到可用扬声器")

    print("\n===== PyAudio配置示例 =====\n")

    if recommended_mic:
        print("# 麦克风初始化代码")
        print(f"input_device_index = {recommended_mic[0]}  # {recommended_mic[1]}")
        print("input_stream = p.open(")
        print("    format=pyaudio.paInt16,")
        print("    channels=1,")
        print("    rate=16000,")
        print("    input=True,")
        print("    frames_per_buffer=1024,")
        print("    input_device_index={recommended_mic[0]})")

    if recommended_speaker:
        print("\n# 扬声器初始化代码")
        print(
            f"output_device_index = {recommended_speaker[0]}  # "
            f"{recommended_speaker[1]}"
        )
        print("output_stream = p.open(")
        print("    format=pyaudio.paInt16,")
        print("    channels=1,")
        print("    rate=44100,")
        print("    output=True,")
        print("    frames_per_buffer=1024,")
        print(f"    output_device_index={recommended_speaker[0]})")

    p.terminate()

    return recommended_mic, recommended_speaker


if __name__ == "__main__":
    try:
        mic, speaker = detect_audio_devices()
        print("\n检测完成！")
    except Exception as e:
        print(f"检测过程中出错: {e}")
