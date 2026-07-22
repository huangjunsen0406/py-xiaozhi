"""音乐相关配置读取."""

from src.logging import get_logger

logger = get_logger()

DEFAULT_SEARCH_URL = "http://search.kuwo.cn/r.s"
DEFAULT_URL_API = "https://lxmusicapi.onrender.com"
DEFAULT_URL_API_KEY = "share-v3"
DEFAULT_LYRICS_URL = "http://m.kuwo.cn/newh5/singles/songinfoandlrc"


def _cfg_str(cm, path: str, default: str) -> str:
    # 设置页允许留空=用默认；get_config 对 "" 不会回落 default
    value = cm.get_config(path, default)
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def load_music_config() -> dict:
    from src.utils.config_manager import get_config

    cm = get_config()
    pick = _cfg_str

    return {
        "SEARCH_URL": pick(cm, "MUSIC.SEARCH_URL", DEFAULT_SEARCH_URL),
        "URL_API": pick(cm, "MUSIC.URL_API", DEFAULT_URL_API),
        "URL_API_KEY": pick(cm, "MUSIC.URL_API_KEY", DEFAULT_URL_API_KEY),
        "LYRICS_URL": pick(cm, "MUSIC.LYRICS_URL", DEFAULT_LYRICS_URL),
        "DEFAULT_SOURCE": pick(cm, "MUSIC.DEFAULT_PLATFORM", "kw") or "kw",
        "DEFAULT_BR": pick(cm, "MUSIC.DEFAULT_QUALITY", "320k") or "320k",
        "SEARCH_LIMIT": 20,
        "HEADERS": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        },
    }
