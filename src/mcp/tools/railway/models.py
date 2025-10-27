"""
12306数据模型定义.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class StationInfo:
    """
    车站信息.
    """

    station_id: str
    station_name: str
    station_code: str  # 3位字母编码
    station_pinyin: str
    station_short: str
    city: str
    code: str


@dataclass
class SeatPrice:
    """
    座位价格信息.
    """

    seat_name: str  # 座位名称
    short: str  # 短名称
    seat_type_code: str  # 座位类型编码
    num: str  # 余票数量
    price: float  # 价格
    discount: Optional[float] = None  # 折扣


@dataclass
class TrainTicket:
    """
    火车票信息.
    """

    train_no: str  # 车次编号
    start_train_code: str  # 车次代码
    start_date: str  # 出发日期
    start_time: str  # 出发时间
    arrive_date: str  # 到达日期
    arrive_time: str  # 到达时间
    duration: str  # 历时
    from_station: str  # 出发站
    to_station: str  # 到达站
    from_station_code: str  # 出发站编码
    to_station_code: str  # 到达站编码
    prices: List[SeatPrice]  # 座位价格列表
    features: List[str]  # 特性标记（复兴号、智能动车组等）


@dataclass
class TransferTicket:
    """
    中转车票信息.
    """

    duration: str  # 总历时
    start_time: str  # 出发时间
    start_date: str  # 出发日期
    middle_date: str  # 中转日期
    arrive_date: str  # 到达日期
    arrive_time: str  # 到达时间
    from_station_code: str  # 出发站编码
    from_station_name: str  # 出发站名称
    middle_station_code: str  # 中转站编码
    middle_station_name: str  # 中转站名称
    end_station_code: str  # 到达站编码
    end_station_name: str  # 到达站名称
    start_train_code: str  # 首个车次代码
    first_train_no: str  # 第一程车次编号
    second_train_no: str  # 第二程车次编号
    train_count: int  # 车次数量
    ticket_list: List[TrainTicket]  # 车票列表
    same_station: bool  # 是否同站换乘
    same_train: bool  # 是否同车换乘
    wait_time: str  # 等待时间


@dataclass
class RouteStation:
    """
    经停站信息.
    """

    arrive_time: str  # 到达时间
    station_name: str  # 站名
    stopover_time: str  # 停车时间
    station_no: int  # 站序
