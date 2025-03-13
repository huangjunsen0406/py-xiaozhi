# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # 只包含实际存在的文件和目录
        ('libs/windows/opus.dll', 'libs/windows'),
        ('config', 'config'),  # 添加配置文件目录
        ('models', 'models'),  # 添加模型目录
    ],
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
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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