import os
import sys

# 在程序启动时执行
def runtime_init():
    # 如果是 PyInstaller 打包环境
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # 尝试添加额外的 DLL 搜索路径
        vosk_dir = os.path.join(sys._MEIPASS, 'vosk')
        if os.path.exists(vosk_dir):
            try:
                os.add_dll_directory(vosk_dir)
                print(f"已添加 Vosk DLL 目录: {vosk_dir}")
            except Exception as e:
                print(f"添加 Vosk DLL 目录失败: {e}")
        else:
            print(f"Vosk 目录不存在: {vosk_dir}")

# 执行初始化
runtime_init() 