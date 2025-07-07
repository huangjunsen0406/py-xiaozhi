"""
12306铁路购票查询工具模块.

提供火车票查询、车次查询、经停站查询等功能.
"""

from .manager import get_railway_manager

__all__ = ["get_railway_manager"]
