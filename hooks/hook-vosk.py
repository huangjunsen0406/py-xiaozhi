from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os
import json
from pathlib import Path
import site
import sys

# 收集 vosk 的所有子模块
hiddenimports = collect_submodules('vosk')

# 收集 vosk 的所有数据文件
datas = collect_data_files('vosk')

# 确保 vosk_cffi 被包含
hiddenimports += ['vosk_cffi', '_cffi_backend']

# 手动添加 vosk 目录到二进制文件中
# 查找 vosk 库的实际位置
def find_vosk_dir():
    try:
        import vosk
        # 使用 pathlib 获取目录
        vosk_dir = Path(vosk.__file__).parent
        print(f"找到 Vosk 目录: {vosk_dir}")
        return str(vosk_dir)  # 返回字符串以兼容现有代码
    except ImportError:
        print("无法导入 vosk 模块")
        return None

vosk_dir = find_vosk_dir()
if vosk_dir:
    datas.append((vosk_dir, 'vosk'))
    # 如果有特定的 DLL 目录，也添加它
    dll_dir = Path(vosk_dir) / 'dll'
    if dll_dir.exists():
        datas.append((str(dll_dir), 'vosk/dll'))

# 读取配置文件获取模型配置信息
def get_model_config():
    try:
        # 尝试从多个可能的位置加载配置文件
        config_paths = [
            Path("config") / "config.json",
            Path(__file__).parent.parent / "config" / "config.json",
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 获取是否使用唤醒词和模型路径
                    use_wake_word = config.get("USE_WAKE_WORD", True)
                    model_path = config.get("WAKE_WORD_MODEL_PATH", "models/vosk-model-small-cn-0.22")
                    return use_wake_word, model_path
        
        # 如果找不到配置文件，返回默认值
        return True, "models/vosk-model-small-cn-0.22"
    except Exception as e:
        print(f"读取配置文件获取模型配置时出错: {e}")
        return True, "models/vosk-model-small-cn-0.22"

# 获取模型配置
use_wake_word, model_path = get_model_config()

# 只有在需要使用唤醒词时才添加模型
if use_wake_word:
    # 使用 pathlib 处理路径
    model_dir = str(Path(model_path))
    
    # 如果存在模型目录，添加到 datas
    if Path(model_dir).exists():
        print(f"找到模型目录: {model_dir}，添加到打包资源")
        datas += [(model_dir, model_path)]
    else:
        print(f"警告：模型目录不存在: {model_dir}")
else:
    print("用户配置不使用唤醒词，跳过添加语音模型") 