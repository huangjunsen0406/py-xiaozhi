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


def get_required_packages():
    """获取项目依赖的包"""
    project_root = get_project_root()
    platform_info = get_platform_info()
    
    # 根据平台选择正确的requirements文件
    if platform_info['is_macos']:
        req_file = project_root / "requirements_mac.txt"
    else:
        req_file = project_root / "requirements.txt"
    
    if not req_file.exists():
        print(f"未找到依赖文件: {req_file}")
        return []
    
    # 确保PyQt相关包被包含
    essential_packages = [
        'PyQt5', 
        'pyqt5-tools', 
        'PyQtWebEngine',
        'PyQt5-Qt5', 
        'PyQt5-sip'
    ]
    
    try:
        with open(req_file, 'r', encoding='utf-8') as f:
            packages = []
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # 去除版本信息，只保留包名
                    package = line.split('==')[0].split('>=')[0]
                    package = package.split('<=')[0].strip()
                    if package:
                        packages.append(package)
            
            # 添加必要的PyQt包（如果不在requirements中）
            for pkg in essential_packages:
                if pkg not in packages:
                    packages.append(pkg)
                    print(f"添加必要依赖: {pkg}")
                    
            return packages
    except Exception as e:
        print(f"读取依赖文件时出错: {e}")
        return essential_packages  # 至少返回必要的包


def collect_data_files():
    """收集需要打包的数据文件"""
    project_root = get_project_root()
    data_files = []

    # 精简版目录列表，排除docs、cache等不必要的目录
    dirs_to_include = [
        # "config" 已移除，让程序自动生成配置文件
        "models",         # 需要保留模型文件
        "src",            # 源代码必须保留
        "hooks"           # 钩子脚本必须保留
    ]

    # 收集目录
    for dirname in dirs_to_include:
        dirpath = project_root / dirname
        if dirpath.exists() and dirpath.is_dir():
            # 保持相对路径结构: (source, dest)
            # 对于src目录，我们只需要包含.py和.ui文件
            if dirname == "src":
                for root, dirs, files in os.walk(dirpath):
                    # 排除__pycache__目录
                    dirs[:] = [d for d in dirs if d != "__pycache__"]
                    
                    # 创建和原目录结构对应的相对路径
                    rel_path = os.path.relpath(root, project_root)
                    
                    # 收集.py和.ui文件
                    for file in files:
                        if file.endswith(('.py', '.ui')):
                            source_file = os.path.join(rel_path, file)
                            data_files.append((source_file, rel_path))
                            print(f"添加文件: {source_file}")
            else:
                data_files.append((str(dirname), str(dirname)))
                print(f"添加目录: {dirname}")

    # 确保包含UI文件
    src_dir = project_root / "src"
    if src_dir.exists():
        for root, dirs, files in os.walk(src_dir):
            for file in files:
                if file.endswith('.ui'):
                    # 获取相对于项目根目录的路径
                    rel_dir = os.path.relpath(root, project_root)
                    source = os.path.join(rel_dir, file)
                    # 检查是否已经添加了这个文件
                    if not any(src == source for src, _ in data_files):
                        data_files.append((source, rel_dir))
                        print(f"添加UI文件: {source}")

    # 根据不同平台添加特定库文件
    platform_info = get_platform_info()
    if platform_info['is_windows']:
        lib_dir = project_root / 'libs' / 'windows'
        if lib_dir.exists():
            data_files.append((str(lib_dir), 'libs/windows'))
            print("添加 Windows 库文件")
    elif platform_info['is_macos']:
        lib_dir = project_root / 'libs' / 'macos'
        if lib_dir.exists():
            data_files.append((str(lib_dir), 'libs/macos'))
            print("添加 macOS 库文件")
    elif platform_info['is_linux']:
        lib_dir = project_root / 'libs' / 'linux'
        if lib_dir.exists():
            data_files.append((str(lib_dir), 'libs/linux'))
            print("添加 Linux 库文件")

    return data_files


def create_simplified_spec_file(platform_info):
    """创建简化版 spec 文件"""
    print_step("创建简化版打包配置文件")
    
    project_root = get_project_root()
    spec_path = project_root / "xiaozhi.spec"
    
    # 获取平台相关信息
    if platform_info['is_windows']:
        exe_name = "小智"
    elif platform_info['is_macos']:
        exe_name = "小智_mac"
    else:
        exe_name = "小智_linux"
    
    # 获取所有依赖包
    packages = get_required_packages()
    hidden_imports = ",\n        ".join([f"'{pkg}'" for pkg in packages])
    
    # 收集数据文件
    data_files = collect_data_files()
    datas_str = ""
    for src, dest in data_files:
        datas_str += f"        (r'{src}', r'{dest}'),\n"
    
    # 创建 spec 文件内容
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

block_cipher = None

# 收集数据文件
datas = [
{datas_str}]

# PyQt5特殊处理
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
pyqt5_data = collect_data_files('PyQt5')
for src, dest in pyqt5_data:
    datas.append((src, dest))
print(f"已添加PyQt5数据文件 {{len(pyqt5_data)}} 个")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # 自动包含所有依赖
        {hidden_imports},
        # 额外确保这些关键模块被包含
        'engineio.async_drivers.threading',
        'opuslib',
        'pyaudiowpatch',
        'numpy',
        'tkinter',
        'json',
        'asyncio',
        'threading',
        'logging',
        'ctypes',
        'socketio',
        'engineio',
        'websockets',
        'vosk',
        'vosk.vosk_cffi',
        'pygame',
        # PyQt5相关
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.uic',
        'PyQt5.QtWebChannel',
        'PyQt5.QtWebEngineWidgets',
    ] + collect_submodules('PyQt5'),
    hookspath=['hooks'],
    hooksconfig={{}},
    runtime_hooks=['hooks/runtime_hook.py'],
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
"""
    
    # 备份原始 spec 文件
    if spec_path.exists():
        backup_path = spec_path.with_suffix('.spec.bak')
        shutil.copy2(spec_path, backup_path)
        print(f"已创建 spec 文件备份: {backup_path}")
    
    # 写入新的 spec 文件
    with open(spec_path, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print(f"已创建简化版 spec 文件: {spec_path}")
    return spec_path


def create_template_config():
    """创建模板配置文件用于打包，保留原始配置的结构和值，但清除身份信息"""
    print_step("跳过配置文件处理")
    
    # 由于不再打包config目录，无需处理配置文件
    print("配置文件将在程序第一次运行时自动生成")
    return None


def restore_config(backup_path):
    """恢复原始配置文件"""
    # 由于不再处理配置文件，此函数不再需要执行操作
    return


def build_executable(spec_path):
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
        str(spec_path)
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


def modify_hooks():
    """确保钩子脚本处理相对路径"""
    print_step("检查并更新钩子脚本")
    
    project_root = get_project_root()
    runtime_hook_path = project_root / "hooks" / "runtime_hook.py"
    
    if not runtime_hook_path.exists():
        print(f"未找到运行时钩子脚本: {runtime_hook_path}")
        return False
    
    try:
        # 读取运行时钩子内容
        with open(runtime_hook_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 添加路径处理代码（如果尚未存在）
        path_code = """
# 添加相对路径处理
import os
import sys

# 获取可执行文件或脚本的目录
if getattr(sys, 'frozen', False):
    # 打包后运行
    app_path = os.path.dirname(sys.executable)
else:
    # 开发环境运行
    app_path = os.path.dirname(os.path.abspath(__file__))

# 将app_path作为工作目录，确保所有相对路径都基于此
os.chdir(app_path)
sys.path.insert(0, app_path)

print(f"应用路径: {app_path}")
print(f"工作目录: {os.getcwd()}")
"""
        
        # 如果不存在路径处理代码，则添加
        if "获取可执行文件或脚本的目录" not in content:
            # 创建备份
            backup_path = runtime_hook_path.with_suffix('.py.bak')
            shutil.copy2(runtime_hook_path, backup_path)
            print(f"已创建钩子脚本备份: {backup_path}")
            
            # 在文件开头添加路径处理代码
            with open(runtime_hook_path, 'w', encoding='utf-8') as f:
                f.write(path_code + content)
            
            print("已更新运行时钩子，添加相对路径处理")
        else:
            print("运行时钩子已包含路径处理代码，无需更新")
        
        return True
    except Exception as e:
        print(f"修改钩子脚本时出错: {e}")
        return False


def create_launcher_scripts(platform_info):
    """创建启动脚本"""
    print_step("创建启动脚本")
    
    project_root = get_project_root()
    dist_dir = project_root / "dist"
    if not dist_dir.exists():
        print("输出目录不存在，跳过创建启动脚本")
        return False
    
    if platform_info['is_windows']:
        # 创建Windows批处理文件
        launcher_path = dist_dir / "启动小智.bat"
        with open(launcher_path, 'w', encoding='utf-8') as f:
            f.write('@echo off\r\n')
            f.write('echo 正在启动小智助手...\r\n')
            f.write('cd /d "%~dp0"\r\n')  # 切换到批处理文件所在目录
            f.write('start "" "小智.exe"\r\n')
            f.write('exit\r\n')
    elif platform_info['is_macos']:
        # 创建macOS shell脚本
        launcher_path = dist_dir / "启动小智.command"
        with open(launcher_path, 'w', encoding='utf-8') as f:
            f.write('#!/bin/bash\n')
            f.write('echo "正在启动小智助手..."\n')
            f.write('cd "$(dirname "$0")"\n')  # 切换到脚本所在目录
            f.write('./小智_mac\n')
        # 设置可执行权限
        os.chmod(launcher_path, 0o755)
    else:
        # 创建Linux shell脚本
        launcher_path = dist_dir / "启动小智.sh"
        with open(launcher_path, 'w', encoding='utf-8') as f:
            f.write('#!/bin/bash\n')
            f.write('echo "正在启动小智助手..."\n')
            f.write('cd "$(dirname "$0")"\n')  # 切换到脚本所在目录
            f.write('./小智_linux\n')
        # 设置可执行权限
        os.chmod(launcher_path, 0o755)
    
    print(f"创建启动脚本: {launcher_path}")
    return True


def main():
    """主函数"""
    print_step("开始构建小智应用")
    
    # 获取平台信息
    platform_info = get_platform_info()
    print(f"当前平台: {platform_info['platform']} {platform_info['arch']}")
    
    # 修改钩子脚本，确保正确处理相对路径
    modify_hooks()
    
    # 修复 opuslib
    opuslib_backup = fix_opuslib_syntax()
    
    # 不再处理配置文件，直接创建spec文件
    try:
        # 创建简化版 spec 文件
        spec_path = create_simplified_spec_file(platform_info)
        
        # 构建可执行文件
        success = build_executable(spec_path)
        
        if success:
            output_path = get_output_file_path(platform_info)
            if output_path.exists():
                print(f"\n构建完成! 可执行文件位于: {output_path}")
                # 创建启动脚本
                create_launcher_scripts(platform_info)
            else:
                print("\n构建似乎成功，但未找到输出文件")
    finally:
        # 不再需要恢复配置文件
        pass
    
    # 恢复 opuslib 原始文件
    restore_opuslib(opuslib_backup)
    
    print_step("构建过程结束")


if __name__ == "__main__":
    main() 