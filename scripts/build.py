#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
import shutil
import platform
import subprocess
from pathlib import Path

def print_step(message):
    """打印带有明显分隔符的步骤信息"""
    print("\n" + "=" * 80)
    print(f">>> {message}")
    print("=" * 80)

def get_project_root():
    """获取项目根目录"""
    return Path(__file__).parent.parent

def read_config():
    """读取配置文件"""
    config_path = get_project_root() / "config" / "config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"读取配置文件时出错: {e}")
        return {}

def get_platform_info():
    """获取当前平台信息"""
    system = platform.system().lower()
    
    # 平台类型
    if system == 'darwin':
        platform_type = 'macos'
    elif system == 'linux':
        platform_type = 'linux'
    else:
        platform_type = 'windows'
    
    # 架构
    machine = platform.machine().lower()
    if machine in ('x86_64', 'amd64'):
        arch = 'x64'
    elif machine in ('i386', 'i686', 'x86'):
        arch = 'x86'
    elif machine in ('arm64', 'aarch64'):
        arch = 'arm64'
    elif machine.startswith('arm'):
        arch = 'arm'
    else:
        arch = machine
    
    return {
        'system': system,
        'platform': platform_type,
        'arch': arch,
        'is_windows': system == 'windows',
        'is_macos': system == 'darwin',
        'is_linux': system == 'linux'
    }

def fix_opuslib_syntax():
    """修复 opuslib 中的语法警告"""
    print_step("检查 opuslib 语法")
    
    try:
        import opuslib
        decoder_path = Path(opuslib.__file__).parent / "api" / "decoder.py"
        
        # 检查文件内容
        with open(decoder_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 如果需要修复
        if 'is not 0' in content:
            # 创建备份
            backup_path = decoder_path.with_suffix('.py.bak')
            shutil.copy2(decoder_path, backup_path)
            print(f"已创建备份: {backup_path}")
            
            # 修改文件内容
            content = content.replace('is not 0', '!= 0')
            
            with open(decoder_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            print("已修复 'is not 0' 为 '!= 0'")
            return backup_path
        else:
            print("opuslib 语法检查通过，无需修复")
            return None
    except ImportError:
        print("未找到 opuslib 模块，跳过检查")
        return None
    except Exception as e:
        print(f"检查 opuslib 时出错: {e}")
        return None

def restore_opuslib(backup_path):
    """恢复 opuslib 原始文件"""
    if backup_path and backup_path.exists():
        try:
            import opuslib
            decoder_path = Path(opuslib.__file__).parent / "api" / "decoder.py"
            
            shutil.copy2(backup_path, decoder_path)
            backup_path.unlink()  # 删除备份
            print("已恢复 opuslib 原始文件并删除备份")
        except Exception as e:
            print(f"恢复 opuslib 时出错: {e}")

def create_new_spec_file(config, platform_info):
    """创建全新的 spec 文件而不是修改现有文件"""
    print_step("创建新的打包配置文件")
    
    project_root = get_project_root()
    original_spec_path = project_root / "xiaozhi.spec"
    temp_spec_path = project_root / "xiaozhi_temp.spec"
    
    # 获取唤醒词配置
    wake_word_options = config.get("WAKE_WORD_OPTIONS", {})
    use_wake_word = wake_word_options.get("USE_WAKE_WORD", False)
    default_model = "models/vosk-model-small-cn-0.22"
    model_path = wake_word_options.get("MODEL_PATH", default_model)
    
    print(f"打包配置: USE_WAKE_WORD={use_wake_word}, MODEL_PATH={model_path}")
    print(f"平台信息: {platform_info['platform']}-{platform_info['arch']}")
    
    # 根据平台设置可执行文件名称
    if platform_info['is_windows']:
        exe_name = "小智"
    elif platform_info['is_macos']:
        exe_name = "小智_mac"
    else:
        exe_name = "小智_linux"
    
    # 创建全新的 spec 文件内容
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
import json
import os
import sys
from pathlib import Path

block_cipher = None

# 准备要添加的数据文件
datas = [
    ('config', 'config'),  # 包含整个config目录，此时config.json已经是模板版本
]

# 根据不同平台添加特定库文件
if sys.platform == 'win32':
    # Windows 平台
    if Path('libs/windows/opus.dll').exists():
        datas.append(('libs/windows/opus.dll', 'libs/windows'))
        print("添加 Windows opus 库到打包资源")
elif sys.platform == 'darwin':
    # macOS 平台
    if Path('libs/macos/libopus.dylib').exists():
        datas.append(('libs/macos/libopus.dylib', 'libs/macos'))
        print("添加 macOS opus 库到打包资源")
else:
    # Linux 平台
    for lib_file in ['libopus.so', 'libopus.so.0', 'libopus.so.0.8.0']:
        lib_path = Path(f'libs/linux/{{lib_file}}')
        if lib_path.exists():
            datas.append((str(lib_path), str(lib_path.parent)))
            print(f"添加 Linux opus 库 {{lib_file}} 到打包资源")
            break

# 如果使用唤醒词，添加模型到打包资源
if {use_wake_word}:
    model_path_str = "{model_path}"
    model_dir = Path(model_path_str)
    if model_dir.exists():
        print(f"添加唤醒词模型目录到打包资源: {{model_path_str}}")
        # 注意这里的变化：直接使用字符串路径，保持目录结构
        datas.append((model_path_str, model_path_str))
    else:
        print(f"警告 - 唤醒词模型目录不存在: {{model_path_str}}")
else:
    print("配置为不使用唤醒词，跳过添加模型目录")

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
    hooksconfig={{}},
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
    name='{exe_name}',
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

# 导入并执行 setup_opus
try:
    from src.utils.system_info import setup_opus
    setup_opus()
except Exception as e:
    print(f"初始化 opus 库时出错: {{e}}")
"""
    
    # 备份原始 spec 文件
    if original_spec_path.exists():
        backup_path = original_spec_path.with_suffix('.spec.bak')
        shutil.copy2(original_spec_path, backup_path)
        print(f"已创建 spec 文件备份: {backup_path}")
    
    # 写入新的 spec 文件
    with open(temp_spec_path, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print(f"已创建新的 spec 文件: {temp_spec_path}")
    return temp_spec_path, original_spec_path

def cleanup_spec_files(temp_spec_path, original_spec_path):
    """清理临时 spec 文件并恢复原始文件"""
    try:
        # 删除临时 spec 文件
        if temp_spec_path.exists():
            temp_spec_path.unlink()
            print(f"已删除临时 spec 文件: {temp_spec_path}")
        
        # 恢复原始 spec 文件
        backup_path = original_spec_path.with_suffix('.spec.bak')
        if backup_path.exists():
            shutil.copy2(backup_path, original_spec_path)
            backup_path.unlink()
            print("已恢复原始 spec 文件并删除备份")
    except Exception as e:
        print(f"清理 spec 文件时出错: {e}")

def build_executable(temp_spec_path):
    """使用 PyInstaller 构建可执行文件"""
    print_step("开始构建可执行文件")
    
    project_root = get_project_root()
    os.chdir(project_root)  # 切换到项目根目录
    
    # 清理输出目录
    dist_dir = project_root / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
        print("已清理输出目录")
    
    # 基本命令
    cmd = [
        sys.executable, 
        "-m", "PyInstaller",
        "--clean",  # 清除临时文件
        "--noconfirm",  # 不询问确认
        str(temp_spec_path)
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        # 执行 PyInstaller 命令
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # 实时输出构建日志
        for line in process.stdout:
            print(line, end='')
            
        process.wait()
        
        if process.returncode == 0:
            print("\n构建成功!")
            return True
        else:
            print(f"\n构建失败，返回码: {process.returncode}")
            return False
    except Exception as e:
        print(f"构建过程中出错: {e}")
        return False

def get_output_file_path(platform_info):
    """获取输出文件路径"""
    project_root = get_project_root()
    
    if platform_info['is_windows']:
        return project_root / "dist" / "小智.exe"
    elif platform_info['is_macos']:
        return project_root / "dist" / "小智_mac"
    else:
        return project_root / "dist" / "小智_linux"

def create_template_config():
    """创建模板配置文件用于打包，保留原始配置的结构和值，但清除身份信息"""
    print_step("创建模板配置文件")
    
    project_root = get_project_root()
    config_path = project_root / "config" / "config.json"
    backup_path = project_root / "config" / "config.json.bak"
    
    # 如果配置文件不存在，则无需处理
    if not config_path.exists():
        print("未找到配置文件，打包将使用默认配置")
        return None
    
    # 读取当前配置
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            current_config = json.load(f)
        
        # 创建备份
        shutil.copy2(config_path, backup_path)
        print(f"已创建配置文件备份: {backup_path}")
        
        # 修改关键字段，保留其他所有配置
        modified_config = current_config.copy()
        
        # 修改系统选项中的身份信息
        if "SYSTEM_OPTIONS" in modified_config:
            modified_config["SYSTEM_OPTIONS"]["CLIENT_ID"] = None
            modified_config["SYSTEM_OPTIONS"]["DEVICE_ID"] = None
            
            # 如果存在MQTT_INFO，清除敏感信息
            system_network = modified_config["SYSTEM_OPTIONS"].get("NETWORK", {})
            if "MQTT_INFO" in system_network:
                # 设置为None，让配置管理器在初始化时自动获取
                system_network["MQTT_INFO"] = None
        
        # 写入修改后的配置
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(modified_config, f, indent=2, ensure_ascii=False)
        
        print("已创建模板配置文件用于打包")
        return backup_path
    except Exception as e:
        print(f"处理配置文件时出错: {e}")
        return None

def restore_config(backup_path):
    """恢复原始配置文件"""
    if backup_path and backup_path.exists():
        try:
            config_path = get_project_root() / "config" / "config.json"
            shutil.copy2(backup_path, config_path)
            backup_path.unlink()  # 删除备份
            print("已恢复原始配置文件并删除备份")
        except Exception as e:
            print(f"恢复配置文件时出错: {e}")

def main():
    """主函数"""
    print_step("开始构建小智应用")
    
    # 获取平台信息
    platform_info = get_platform_info()
    print(f"当前平台: {platform_info['platform']} {platform_info['arch']}")
    
    # 修复 opuslib
    opuslib_backup = fix_opuslib_syntax()
    
    # 创建模板配置文件（仅修改身份信息为None）
    config_backup = create_template_config()
    
    # 读取修改后的配置（用于获取打包需要的其他设置）
    config = read_config()
    
    # 创建新的 spec 文件
    spec_result = create_new_spec_file(config, platform_info)
    
    try:
        if spec_result:
            temp_spec_path, original_spec_path = spec_result
            
            # 构建可执行文件
            success = build_executable(temp_spec_path)
            
            if success:
                output_path = get_output_file_path(platform_info)
                if output_path.exists():
                    print(f"\n构建完成! 可执行文件位于: {output_path}")
                else:
                    print("\n构建似乎成功，但未找到输出文件")
    finally:
        # 恢复原始配置文件
        restore_config(config_backup)
        
        # 清理临时文件
        if 'spec_result' in locals() and spec_result:
            cleanup_spec_files(temp_spec_path, original_spec_path)
    
    # 恢复 opuslib 原始文件
    restore_opuslib(opuslib_backup)
    
    print_step("构建过程结束")

if __name__ == "__main__":
    main() 