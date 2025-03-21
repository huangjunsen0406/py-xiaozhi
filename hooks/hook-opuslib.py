from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from pathlib import Path

# 收集 opuslib 的所有子模块
hiddenimports = collect_submodules('opuslib')

# 收集 opuslib 的所有数据文件
datas = collect_data_files('opuslib')

# 确保加载 _opuslib 原生模块
hiddenimports += ['_opuslib']

# 显式添加可能需要的模块
hiddenimports += ['ctypes']

# 收集 vosk 的所有子模块
hiddenimports += collect_submodules('vosk')

# 收集 vosk 的所有数据文件
datas += collect_data_files('vosk')

# 修复 opuslib 中的 SyntaxWarning
def patch_opuslib_syntax():
    try:
        import opuslib
        # 使用 pathlib 处理路径
        decoder_path = Path(opuslib.__file__).parent / 'api' / 'decoder.py'
        
        if decoder_path.exists():
            with open(decoder_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 替换 "is not 0" 为 "!= 0"
            if 'is not 0' in content:
                content = content.replace('is not 0', '!= 0')
                
                # 写回修改后的文件
                with open(decoder_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                    
                print("已修复 opuslib/api/decoder.py 中的语法警告")
            else:
                print("opuslib/api/decoder.py 中未发现需要修复的语法")
        else:
            print(f"未找到 decoder.py 文件: {decoder_path}")
    except Exception as e:
        print(f"修复 opuslib 语法时出错: {e}")

# 执行修复
patch_opuslib_syntax() 