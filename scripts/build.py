#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
import tempfile
import re

def print_step(message):
    """打印带有明显分隔符的步骤信息"""
    print("\n" + "=" * 80)
    print(f">>> {message}")
    print("=" * 80)

def get_project_root():
    """获取项目根目录"""
    # 假设本脚本位于 scripts 目录下
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

def fix_opuslib_syntax():
    """修复 opuslib 中的语法警告"""
    print_step("修复 opuslib 中的语法警告")
    
    try:
        import opuslib
        decoder_path = Path(opuslib.__file__).parent / "api" / "decoder.py"
        
        # 检查文件内容
        with open(decoder_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 创建备份
        backup_path = decoder_path.with_suffix('.py.bak')
        shutil.copy2(decoder_path, backup_path)
        print(f"已创建备份: {backup_path}")
        
        # 修改文件内容
        if 'is not 0' in content:
            content = content.replace('is not 0', '!= 0')
            
            with open(decoder_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            print("已修复 'is not 0' 为 '!= 0'")
        else:
            print("未发现需要修复的语法问题")
            
        return backup_path
    except ImportError:
        print("未找到 opuslib 模块，跳过修复")
        return None
    except Exception as e:
        print(f"修复时出错: {e}")
        return None

def restore_opuslib(backup_path):
    """恢复 opuslib 原始文件"""
    if backup_path and backup_path.exists():
        try:
            import opuslib
            decoder_path = Path(opuslib.__file__).parent / "api" / "decoder.py"
            
            shutil.copy2(backup_path, decoder_path)
            backup_path.unlink()  # 删除备份
            print(f"已恢复 opuslib 原始文件并删除备份")
        except Exception as e:
            print(f"恢复 opuslib 时出错: {e}")

def update_spec_file(config):
    """直接修改现有的 spec 文件"""
    print_step("更新打包配置文件")
    
    project_root = get_project_root()
    spec_path = project_root / "xiaozhi.spec"
    
    if not spec_path.exists():
        print(f"错误: 找不到 spec 文件 {spec_path}")
        return None
    
    # 读取原始 spec 文件
    with open(spec_path, 'r', encoding='utf-8') as f:
        spec_content = f.read()
    
    # 备份原始 spec 文件
    backup_path = spec_path.with_suffix('.spec.bak')
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    print(f"已创建 spec 文件备份: {backup_path}")
    
    # 获取唤醒词配置
    use_wake_word = config.get("USE_WAKE_WORD", True)
    model_path = config.get("WAKE_WORD_MODEL_PATH", "models/vosk-model-small-cn-0.22")
    
    print(f"打包配置: USE_WAKE_WORD={use_wake_word}, MODEL_PATH={model_path}")
    
    # 创建带条件判断的 datas 部分
    datas_code = """# 准备要添加的数据文件
datas = [
    ('libs/windows/opus.dll', 'libs/windows'),
    ('config', 'config'),  # 添加配置文件目录
]

# 如果使用唤醒词，添加模型到打包资源
if {use_wake_word}:
    model_dir = "{model_path}"  # 例如 "models/vosk-model-small-cn-0.22"
    if os.path.exists(model_dir):
        print(f"spec: 添加唤醒词模型目录到打包资源: {{model_dir}}")
        datas.append((model_dir, model_dir))
    else:
        print(f"spec: 警告 - 唤醒词模型目录不存在: {{model_dir}}")
else:
    print("spec: 配置为不使用唤醒词，跳过添加模型目录")
""".format(use_wake_word=str(use_wake_word), model_path=model_path)
    
    # 替换原始 datas 部分
    # 匹配 datas = [...] 部分
    datas_pattern = r"datas\s*=\s*\[\s*\(.*?\)\s*,(?:\s*\(.*?\)\s*,)*\s*\]"
    if re.search(datas_pattern, spec_content, re.DOTALL):
        new_spec_content = re.sub(datas_pattern, datas_code, spec_content, flags=re.DOTALL)
    else:
        # 如果找不到匹配的模式，在 a = Analysis 之前插入代码
        analysis_pattern = r"a\s*=\s*Analysis\s*\("
        new_spec_content = re.sub(analysis_pattern, datas_code + "\n\na = Analysis(", spec_content)
    
    # 更新 spec 文件中的 datas 引用
    new_spec_content = re.sub(r"datas=\[.*?\]", "datas=datas", new_spec_content, flags=re.DOTALL)
    
    # 写入修改后的 spec 文件
    with open(spec_path, 'w', encoding='utf-8') as f:
        f.write(new_spec_content)
    
    print(f"已更新 spec 文件: {spec_path}")
    return spec_path, backup_path

def restore_spec_file(backup_path):
    """恢复原始 spec 文件"""
    if backup_path and backup_path.exists():
        try:
            project_root = get_project_root()
            spec_path = project_root / "xiaozhi.spec"
            
            shutil.copy2(backup_path, spec_path)
            backup_path.unlink()  # 删除备份
            print(f"已恢复原始 spec 文件并删除备份")
        except Exception as e:
            print(f"恢复 spec 文件时出错: {e}")

def build_executable():
    """使用 PyInstaller 构建可执行文件"""
    print_step("开始构建可执行文件")
    
    project_root = get_project_root()
    os.chdir(project_root)  # 切换到项目根目录
    
    cmd = [
        sys.executable, 
        "-m", "PyInstaller",
        "--clean",  # 清除临时文件
        "xiaozhi.spec"
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

def main():
    """主函数"""
    print_step("开始构建小智应用")
    
    # 读取配置
    config = read_config()
    
    # 修复 opuslib
    opuslib_backup = fix_opuslib_syntax()
    
    # 更新 spec 文件
    spec_result = update_spec_file(config)
    
    if spec_result:
        spec_path, spec_backup = spec_result
        try:
            # 构建可执行文件
            success = build_executable()
            
            if success:
                dist_path = get_project_root() / "dist" / "小智.exe"
                if dist_path.exists():
                    print(f"\n构建完成! 可执行文件位于: {dist_path}")
                else:
                    print("\n构建似乎成功，但未找到输出文件")
        finally:
            # 恢复原始 spec 文件
            restore_spec_file(spec_backup)
    
    # 恢复 opuslib 原始文件
    restore_opuslib(opuslib_backup)
    
    print_step("构建过程结束")

if __name__ == "__main__":
    main() 