from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

# 收集 vosk 库的所有动态链接库
binaries = collect_dynamic_libs('vosk')

# 收集 vosk 库的所有数据文件
datas = collect_data_files('vosk') 