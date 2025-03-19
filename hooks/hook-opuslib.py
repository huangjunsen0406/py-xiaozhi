from PyInstaller.utils.hooks import collect_data_files, collect_submodules

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