"""
PyInstaller 钩子文件: opuslib

解决 opuslib 在打包时的依赖问题和语法警告
"""

import logging
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from pathlib import Path

from src.utils.logging_config import get_logger

# 配置日志
logger = get_logger(__name__)


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


def patch_opuslib_syntax():
    """
    修复 opuslib 中的 SyntaxWarning
    
    在Python 3.8+中，"is not 0"语法会产生警告，
    此函数将其替换为标准的"!= 0"形式
    """
    try:
        import opuslib
        # 使用 pathlib 处理路径
        decoder_path = Path(opuslib.__file__).parent / 'api' / 'decoder.py'
        
        if decoder_path.exists():
            # 读取文件内容
            with open(decoder_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查并替换语法
            if 'is not 0' in content:
                # 替换 "is not 0" 为 "!= 0"
                content = content.replace('is not 0', '!= 0')
                
                # 写回修改后的文件
                with open(decoder_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                    
                logger.info("已修复 opuslib/api/decoder.py 中的语法警告")
            else:
                logger.info("opuslib/api/decoder.py 中未发现需要修复的语法")
        else:
            logger.warning(f"未找到 decoder.py 文件: {decoder_path}")
            
    except ImportError:
        logger.warning("无法导入 opuslib 模块，跳过语法修复")
    except Exception as e:
        logger.error(f"修复 opuslib 语法时出错: {e}")
        logger.exception("详细错误信息:")


# 执行修复
patch_opuslib_syntax()


# 检查补丁后的模块可用性
def verify_opuslib():
    """验证 opuslib 模块是否可用"""
    try:
        import opuslib
        from opuslib.api import decoder, encoder
        logger.info(f"opuslib 版本: {opuslib.__version__}")
        logger.info("opuslib 模块验证成功")
        return True
    except Exception as e:
        logger.error(f"opuslib 模块验证失败: {e}")
        return False


# 执行验证
verify_opuslib() 