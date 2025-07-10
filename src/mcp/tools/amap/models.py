"""
高德地图 MCP 工具数据模型.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Location:
    """
    位置坐标.
    """

    longitude: float
    latitude: float

    def to_string(self) -> str:
        """
        转换为高德地图API格式的字符串.
        """
        return f"{self.longitude},{self.latitude}"


@dataclass
class AddressComponent:
    """
    地址组件.
    """

    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    street: Optional[str] = None
    number: Optional[str] = None
    country: Optional[str] = None
    citycode: Optional[str] = None
    adcode: Optional[str] = None


@dataclass
class GeocodeResult:
    """
    地理编码结果.
    """

    location: Location
    address_component: AddressComponent
    level: Optional[str] = None


@dataclass
class POI:
    """
    兴趣点.
    """

    id: str
    name: str
    address: str
    location: Location
    type_code: Optional[str] = None
    business_area: Optional[str] = None
    city: Optional[str] = None
    alias: Optional[str] = None
    biz_ext: Optional[Dict[str, Any]] = None


@dataclass
class RouteStep:
    """
    路线步骤.
    """

    instruction: str
    road: str
    distance: int
    orientation: str
    duration: int
    action: Optional[str] = None
    assistant_action: Optional[str] = None


@dataclass
class RoutePath:
    """路径"""

    distance: int
    duration: int
    steps: List[RouteStep]


@dataclass
class RouteResult:
    """
    路线规划结果.
    """

    origin: Location
    destination: Location
    paths: List[RoutePath]


@dataclass
class WeatherInfo:
    """
    天气信息.
    """

    city: str
    date: str
    weather: str
    temperature: str
    wind_direction: str
    wind_power: str
    humidity: str


@dataclass
class WeatherForecast:
    """
    天气预报.
    """

    city: str
    forecasts: List[WeatherInfo]


@dataclass
class DistanceResult:
    """
    距离测量结果.
    """

    origin_id: str
    dest_id: str
    distance: int
    duration: int


@dataclass
class IPLocationResult:
    """
    IP定位结果.
    """

    province: str
    city: str
    adcode: str
    rectangle: str
    location: Optional[Location] = None  # 添加经纬度坐标


@dataclass
class BusLine:
    """
    公交线路.
    """

    name: str
    departure_stop: Dict[str, str]
    arrival_stop: Dict[str, str]
    distance: int
    duration: int
    via_stops: List[Dict[str, str]]


@dataclass
class TransitSegment:
    """
    公交换乘段.
    """

    walking: Optional[RoutePath] = None
    bus: Optional[Dict[str, List[BusLine]]] = None
    entrance: Optional[Dict[str, str]] = None
    exit: Optional[Dict[str, str]] = None
    railway: Optional[Dict[str, Any]] = None


@dataclass
class TransitRoute:
    """
    公交路线.
    """

    duration: int
    walking_distance: int
    segments: List[TransitSegment]


@dataclass
class TransitResult:
    """
    公交路线规划结果.
    """

    origin: Location
    destination: Location
    distance: int
    transits: List[TransitRoute]


@dataclass
class SearchSuggestion:
    """
    搜索建议.
    """

    keywords: List[str]
    cities: List[Dict[str, str]]


@dataclass
class SearchResult:
    """
    搜索结果.
    """

    suggestion: SearchSuggestion
    pois: List[POI]
