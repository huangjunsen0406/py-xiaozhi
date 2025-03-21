# -*- mode: python ; coding: utf-8 -*-
import json
import os
from pathlib import Path

block_cipher = None

# 读取配置文件，决定是否包含唤醒词模型
def get_model_config():
    try:
        config_path = Path("config/config.json")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                use_wake_word = config.get("USE_WAKE_WORD", True)
                model_path = config.get("WAKE_WORD_MODEL_PATH", "models/vosk-model-small-cn-0.22")
                return use_wake_word, model_path
        return True, "models/vosk-model-small-cn-0.22"
    except Exception as e:
        print(f"读取配置文件获取模型配置时出错: {e}")
        return True, "models/vosk-model-small-cn-0.22"

# 获取模型配置
use_wake_word, model_path = get_model_config()

# 准备要添加的数据文件
datas = [
    ('libs/windows/opus.dll', 'libs/windows'),
    ('config', 'config', ['config.json']),  # 添加配置目录但排除config.json
]

# 如果使用唤醒词，添加模型到打包资源
if use_wake_word:
    model_dir = model_path  # 例如 "models/vosk-model-small-cn-0.22"
    if os.path.exists(model_dir):
        print(f"spec: 添加唤醒词模型目录到打包资源: {model_dir}")
        datas.append((model_dir, model_dir))
    else:
        print(f"spec: 警告 - 唤醒词模型目录不存在: {model_dir}")
else:
    print("spec: 配置为不使用唤醒词，跳过添加模型目录")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'engineio.async_drivers.threading',
        'opuslib',
        'pyaudiowpatch',
        'numpy',
        'tkinter',
        'queue',
        'json',
        'asyncio',
        'threading',
        'logging',
        'ctypes',
        'socketio',
        'engineio',
        'websockets',  # 添加 websockets 依赖
        'vosk',  # 添加语音识别依赖
        'vosk.vosk_cffi',  # 添加 vosk cffi 模块
    ],
    hookspath=['hooks'],  # 添加自定义钩子目录
    hooksconfig={},
    runtime_hooks=['hooks/runtime_hook.py'],  # 添加运行时钩子
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

import PyInstaller.config
PyInstaller.config.CONF['disablewindowedtraceback'] = True

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='小智',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

from src.utils.system_info import setup_opus
setup_opus()