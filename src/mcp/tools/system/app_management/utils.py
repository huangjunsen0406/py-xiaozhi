"""应用程序管理通用工具.

提供统一的应用程序匹配、查找和缓存功能
"""

import platform
import re
import time
from typing import Any, Dict, List, Optional

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# 全局应用缓存
_cached_applications: Optional[List[Dict[str, Any]]] = None
_cache_timestamp: float = 0
_cache_duration = 300  # 缓存5分钟


class AppMatcher:
    """
    统一的应用程序匹配器.
    """

    # 特殊应用名称映射 - 按长度排序，避免短名称优先匹配
    SPECIAL_MAPPINGS = {
        "qq音乐": ["qqmusic", "qq音乐", "qq music"],
        "qqmusic": ["qqmusic", "qq音乐", "qq music"],
        "qq music": ["qqmusic", "qq音乐", "qq music"],
        "tencent meeting": ["tencent meeting", "腾讯会议", "voovmeeting"],
        "腾讯会议": ["tencent meeting", "腾讯会议", "voovmeeting"],
        "google chrome": ["chrome", "googlechrome", "google chrome"],
        "microsoft edge": ["msedge", "edge", "microsoft edge"],
        "microsoft office": [
            "microsoft office",
            "office",
            "word",
            "excel",
            "powerpoint",
        ],
        "microsoft word": ["microsoft word", "word"],
        "microsoft excel": ["microsoft excel", "excel"],
        "microsoft powerpoint": ["microsoft powerpoint", "powerpoint"],
        "visual studio code": ["code", "vscode", "visual studio code"],
        "wps office": ["wps", "wps office"],
        "qq": ["qq", "qqnt", "tencentqq"],
        "wechat": ["wechat", "weixin", "微信"],
        "dingtalk": ["dingtalk", "钉钉", "ding"],
        "钉钉": ["dingtalk", "钉钉", "ding"],
        "chrome": ["chrome", "googlechrome", "google chrome"],
        "firefox": ["firefox", "mozilla"],
        "edge": ["msedge", "edge", "microsoft edge"],
        "safari": ["safari"],
        "notepad": ["notepad", "notepad++"],
        "calculator": ["calc", "calculator", "calculatorapp"],
        "calc": ["calc", "calculator", "calculatorapp"],
        "feishu": ["feishu", "飞书", "lark"],
        "vscode": ["code", "vscode", "visual studio code"],
        "pycharm": ["pycharm", "pycharm64"],
        "cursor": ["cursor"],
        "typora": ["typora"],
        "wps": ["wps", "wps office"],
        "office": ["microsoft office", "office", "word", "excel", "powerpoint"],
        "word": ["microsoft word", "word"],
        "excel": ["microsoft excel", "excel"],
        "powerpoint": ["microsoft powerpoint", "powerpoint"],
        "finder": ["finder"],
        "terminal": ["terminal", "iterm"],
        "iterm": ["iterm", "iterm2"],
    }

    # 进程分组映射（用于关闭时分组）
    PROCESS_GROUPS = {
        "chrome": "chrome",
        "googlechrome": "chrome",
        "firefox": "firefox",
        "edge": "edge",
        "msedge": "edge",
        "safari": "safari",
        "qq": "qq",
        "qqnt": "qq",
        "tencentqq": "qq",
        "qqmusic": "qqmusic",
        "QQMUSIC": "QQMUSIC",
        "QQ音乐": "QQ音乐",
        "wechat": "wechat",
        "weixin": "wechat",
        "dingtalk": "dingtalk",
        "钉钉": "dingtalk",
        "feishu": "feishu",
        "飞书": "feishu",
        "lark": "feishu",
        "vscode": "vscode",
        "code": "vscode",
        "cursor": "cursor",
        "pycharm": "pycharm",
        "pycharm64": "pycharm",
        "typora": "typora",
        "calculatorapp": "calculator",
        "calc": "calculator",
        "calculator": "calculator",
        "tencent meeting": "tencent_meeting",
        "腾讯会议": "tencent_meeting",
        "voovmeeting": "tencent_meeting",
        "wps": "wps",
        "word": "word",
        "excel": "excel",
        "powerpoint": "powerpoint",
        "finder": "finder",
        "terminal": "terminal",
        "iterm": "iterm",
        "iterm2": "iterm",
    }

    @classmethod
    def normalize_name(cls, name: str) -> str:
        """
        标准化应用程序名称.
        """
        if not name:
            return ""

        # 移除.exe后缀
        name = name.lower().replace(".exe", "")

        # 移除版本号和特殊字符
        name = re.sub(r"\s+v?\d+[\.\d]*", "", name)
        name = re.sub(r"\s*\(\d+\)", "", name)
        name = re.sub(r"\s*\[.*?\]", "", name)
        name = " ".join(name.split())

        return name.strip()

    @classmethod
    def get_process_group(cls, process_name: str) -> str:
        """
        获取进程所属的分组.
        """
        normalized = cls.normalize_name(process_name)

        # 检查直接映射
        if normalized in cls.PROCESS_GROUPS:
            return cls.PROCESS_GROUPS[normalized]

        # 检查包含关系
        for key, group in cls.PROCESS_GROUPS.items():
            if key in normalized or normalized in key:
                return group

        return normalized

    @classmethod
    def match_application(cls, target_name: str, app_info: Dict[str, Any]) -> int:
        """匹配应用程序，返回匹配度分数.

        Args:
            target_name: 目标应用名称
            app_info: 应用程序信息

        Returns:
            int: 匹配度分数 (0-100)，0表示不匹配
        """
        if not target_name or not app_info:
            return 0

        target_lower = target_name.lower()
        app_name = app_info.get("name", "").lower()
        display_name = app_info.get("display_name", "").lower()
        window_title = app_info.get("window_title", "").lower()
        exe_path = app_info.get("command", "").lower()

        # 1. 精确匹配 (100分)
        if target_lower == app_name or target_lower == display_name:
            return 100

        # 2. 特殊映射匹配 (95-98分) - 优先匹配更具体的关键词
        best_special_score = 0

        for key in cls.SPECIAL_MAPPINGS:
            if key in target_lower or target_lower == key:
                # 检查是否有匹配的别名
                for alias in cls.SPECIAL_MAPPINGS[key]:
                    if alias.lower() in app_name or alias.lower() in display_name:
                        # 计算匹配度：更具体的匹配得分更高
                        if target_lower == key:
                            score = 98  # 精确匹配特殊映射键
                        elif len(key) > len(target_lower) * 0.8:
                            score = 97  # 长度相近的匹配
                        else:
                            score = 95  # 一般特殊映射匹配

                        if score > best_special_score:
                            best_special_score = score

        if best_special_score > 0:
            return best_special_score

        # 3. 标准化名称匹配 (90分)
        normalized_target = cls.normalize_name(target_name)
        normalized_app = cls.normalize_name(app_info.get("name", ""))
        normalized_display = cls.normalize_name(app_info.get("display_name", ""))

        if (
            normalized_target == normalized_app
            or normalized_target == normalized_display
        ):
            return 90

        # 4. 包含匹配 (70-80分)
        if target_lower in app_name:
            return 80
        if target_lower in display_name:
            return 75
        if app_name and app_name in target_lower:
            # 避免短名称误匹配长名称
            if len(app_name) < len(target_lower) * 0.5:
                return 50  # 降低分数
            return 70

        # 5. 窗口标题匹配 (60分)
        if window_title and target_lower in window_title:
            return 60

        # 6. 路径匹配 (50分)
        if exe_path and target_lower in exe_path:
            return 50

        # 7. 模糊匹配 (30分)
        if cls._fuzzy_match(target_lower, app_name) or cls._fuzzy_match(
            target_lower, display_name
        ):
            return 30

        return 0

    @classmethod
    def _fuzzy_match(cls, target: str, candidate: str) -> bool:
        """
        模糊匹配.
        """
        if not target or not candidate:
            return False

        # 移除所有非字母数字字符进行比较
        target_clean = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]", "", target)
        candidate_clean = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]", "", candidate)

        return target_clean in candidate_clean or candidate_clean in target_clean


async def get_cached_applications(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """获取缓存的应用程序列表.

    Args:
        force_refresh: 是否强制刷新缓存

    Returns:
        应用程序列表
    """
    global _cached_applications, _cache_timestamp

    current_time = time.time()

    # 检查缓存是否有效
    if (
        not force_refresh
        and _cached_applications is not None
        and (current_time - _cache_timestamp) < _cache_duration
    ):
        logger.debug(
            f"[AppUtils] 使用缓存的应用程序列表，缓存时间: {int(current_time - _cache_timestamp)}秒前"
        )
        return _cached_applications

    # 重新扫描应用程序
    try:
        import json

        from .scanner import scan_installed_applications

        logger.info("[AppUtils] 刷新应用程序缓存")
        result_json = await scan_installed_applications(
            {"force_refresh": force_refresh}
        )
        result = json.loads(result_json)

        if result.get("success", False):
            _cached_applications = result.get("applications", [])
            _cache_timestamp = current_time
            logger.info(
                f"[AppUtils] 应用程序缓存已刷新，找到 {len(_cached_applications)} 个应用"
            )
            return _cached_applications
        else:
            logger.warning(
                f"[AppUtils] 应用程序扫描失败: {result.get('message', '未知错误')}"
            )
            return _cached_applications or []

    except Exception as e:
        logger.error(f"[AppUtils] 刷新应用程序缓存失败: {e}")
        return _cached_applications or []


async def find_best_matching_app(
    app_name: str, app_type: str = "any"
) -> Optional[Dict[str, Any]]:
    """查找最佳匹配的应用程序.

    Args:
        app_name: 应用程序名称
        app_type: 应用程序类型过滤 ("installed", "running", "any")

    Returns:
        最佳匹配的应用程序信息
    """
    try:
        if app_type == "running":
            # 获取正在运行的应用程序
            import json

            from .scanner import list_running_applications

            result_json = await list_running_applications({})
            result = json.loads(result_json)

            if not result.get("success", False):
                return None

            applications = result.get("applications", [])
        else:
            # 获取已安装的应用程序
            applications = await get_cached_applications()

        if not applications:
            return None

        # 计算所有应用的匹配度
        matches = []
        for app in applications:
            score = AppMatcher.match_application(app_name, app)
            if score > 0:
                matches.append((score, app))

        if not matches:
            return None

        # 按分数排序，返回最佳匹配
        matches.sort(key=lambda x: x[0], reverse=True)
        best_score, best_app = matches[0]

        logger.info(
            f"[AppUtils] 找到最佳匹配: {best_app.get('display_name', best_app.get('name', ''))} (分数: {best_score})"
        )
        return best_app

    except Exception as e:
        logger.error(f"[AppUtils] 查找匹配应用失败: {e}")
        return None


def clear_app_cache():
    """
    清空应用程序缓存.
    """
    global _cached_applications, _cache_timestamp

    _cached_applications = None
    _cache_timestamp = 0
    logger.info("[AppUtils] 应用程序缓存已清空")


def get_cache_info() -> Dict[str, Any]:
    """
    获取缓存信息.
    """

    current_time = time.time()
    cache_age = current_time - _cache_timestamp if _cache_timestamp > 0 else -1

    return {
        "cached": _cached_applications is not None,
        "count": len(_cached_applications) if _cached_applications else 0,
        "age_seconds": int(cache_age) if cache_age >= 0 else None,
        "valid": cache_age >= 0 and cache_age < _cache_duration,
        "cache_duration": _cache_duration,
    }


def get_system_scanner():
    """根据当前系统获取对应的扫描器模块.

    Returns:
        对应系统的扫描器模块
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        from .mac import scanner

        return scanner
    elif system == "Windows":  # Windows
        from .windows import scanner

        return scanner
    elif system == "Linux":  # Linux
        from .linux import scanner

        return scanner
    else:
        logger.warning(f"[AppUtils] 不支持的系统: {system}")
        return None
