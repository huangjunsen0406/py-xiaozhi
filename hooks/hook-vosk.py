from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os
import json
from pathlib import Path

# 收集 vosk 的所有子模块
hiddenimports = collect_submodules('vosk')

# 收集 vosk 的所有数据文件
datas = collect_data_files('vosk')

# 确保 vosk_cffi 被包含
hiddenimports += ['vosk_cffi', '_cffi_backend']

# 读取配置文件获取模型路径
def get_model_path_from_config():
    try:
        # 尝试从多个可能的位置加载配置文件
        config_paths = [
            Path("config/config.json"),
            Path(__file__).parent.parent / "config/config.json",
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 获取配置的模型路径
                    return config.get("WAKE_WORD_MODEL_PATH", "models/vosk-model-small-cn-0.22")
        
        # 如果找不到配置文件，返回默认值
        return "models/vosk-model-small-cn-0.22"
    except Exception as e:
        print(f"读取配置文件获取模型路径时出错: {e}")
        return "models/vosk-model-small-cn-0.22"

# 获取模型路径
model_path = get_model_path_from_config()
model_dir = os.path.join(*model_path.split('/'))

# 如果存在模型目录，添加到 datas
if os.path.exists(model_dir):
    print(f"找到模型目录: {model_dir}，添加到打包资源")
    datas += [(model_dir, model_path)]
else:
    print(f"警告：模型目录不存在: {model_dir}") 