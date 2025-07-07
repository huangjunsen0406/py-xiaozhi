"""
12306 API客户端.

提供访问12306官方API的功能.
"""

import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode

import aiohttp
from dateutil import tz

from src.utils.logging_config import get_logger

from .models import RouteStation, SeatPrice, StationInfo, TrainTicket, TransferTicket

logger = get_logger(__name__)


class Railway12306Client:
    """
    12306客户端.
    """

    def __init__(self):
        self.api_base = "https://kyfw.12306.cn"
        self.web_url = "https://www.12306.cn/index/"
        self.lcquery_init_url = "https://kyfw.12306.cn/otn/lcQuery/init"
        
        # 车站数据缓存
        self._stations: Dict[str, StationInfo] = {}  # code -> StationInfo
        self._city_stations: Dict[str, List[StationInfo]] = {}  # city -> List[StationInfo]
        self._city_codes: Dict[str, StationInfo] = {}  # city -> StationInfo
        self._name_stations: Dict[str, StationInfo] = {}  # name -> StationInfo
        self._lcquery_path: Optional[str] = None
        
        # 座位类型映射
        self.seat_types = {
            '9': {'name': '商务座', 'short': 'swz'},
            'P': {'name': '特等座', 'short': 'tz'},
            'M': {'name': '一等座', 'short': 'zy'},
            'D': {'name': '优选一等座', 'short': 'zy'},
            'O': {'name': '二等座', 'short': 'ze'},
            'S': {'name': '二等包座', 'short': 'ze'},
            '6': {'name': '高级软卧', 'short': 'gr'},
            'A': {'name': '高级动卧', 'short': 'gr'},
            '4': {'name': '软卧', 'short': 'rw'},
            'I': {'name': '一等卧', 'short': 'rw'},
            'F': {'name': '动卧', 'short': 'rw'},
            '3': {'name': '硬卧', 'short': 'yw'},
            'J': {'name': '二等卧', 'short': 'yw'},
            '2': {'name': '软座', 'short': 'rz'},
            '1': {'name': '硬座', 'short': 'yz'},
            'W': {'name': '无座', 'short': 'wz'},
            'WZ': {'name': '无座', 'short': 'wz'},
            'H': {'name': '其他', 'short': 'qt'},
        }
        
        # 车次类型筛选器
        self.train_filters = {
            'G': lambda code: code.startswith('G') or code.startswith('C'),
            'D': lambda code: code.startswith('D'),
            'Z': lambda code: code.startswith('Z'),
            'T': lambda code: code.startswith('T'),
            'K': lambda code: code.startswith('K'),
            'O': lambda code: not any([
                code.startswith('G'), code.startswith('C'), code.startswith('D'),
                code.startswith('Z'), code.startswith('T'), code.startswith('K')
            ]),
        }
        
        # 特性标记
        self.dw_flags = [
            '智能动车组', '复兴号', '静音车厢', '温馨动卧',
            '动感号', '支持选铺', '老年优惠'
        ]

    async def initialize(self) -> bool:
        """
        初始化客户端，加载车站数据.
        """
        try:
            logger.info("开始初始化12306客户端...")
            
            # 加载车站数据
            await self._load_stations()
            
            # 获取中转查询路径
            await self._get_lcquery_path()
            
            logger.info("初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}", exc_info=True)
            return False
    
    async def _load_stations(self):
        """
        加载车站数据.
        """
        try:
            # 获取车站JS文件
            async with aiohttp.ClientSession() as session:
                async with session.get(self.web_url) as response:
                    html = await response.text()
                    
                # 查找车站JS文件路径
                match = re.search(r'\.(.*station_name.*?\.js)', html)
                if not match:
                    raise Exception("未找到车站数据文件")
                    
                js_path = match.group(0)
                js_url = f"{self.web_url.rstrip('/')}/{js_path.lstrip('.')}"
                
                # 获取车站数据
                async with session.get(js_url) as response:
                    js_content = await response.text()
                    
                # 解析车站数据
                station_data = js_content.replace('var station_names =', '').strip().rstrip(';')
                station_data = station_data.strip('"\'')
                
                self._parse_stations_data(station_data)
                
        except Exception as e:
            logger.error(f"加载车站数据失败: {e}")
            # 使用默认车站数据
            self._load_default_stations()
    
    def _parse_stations_data(self, raw_data: str):
        """
        解析车站数据.
        """
        try:
            data_array = raw_data.split('|')
            
            # 每10个元素为一个车站
            for i in range(0, len(data_array), 10):
                if i + 9 >= len(data_array):
                    break
                    
                group = data_array[i:i+10]
                if len(group) < 10 or not group[2]:  # station_code不能为空
                    continue
                    
                station = StationInfo(
                    station_id=group[0],
                    station_name=group[1],
                    station_code=group[2],
                    station_pinyin=group[3],
                    station_short=group[4],
                    city=group[7],
                    code=group[6]
                )
                
                # 按编码索引
                self._stations[station.station_code] = station
                
                # 按城市索引
                if station.city not in self._city_stations:
                    self._city_stations[station.city] = []
                self._city_stations[station.city].append(station)
                
                # 按名称索引
                self._name_stations[station.station_name] = station
                
            # 生成城市代表站编码（与城市同名的站）
            for city, stations in self._city_stations.items():
                for station in stations:
                    if station.station_name == city:
                        self._city_codes[city] = station
                        break
                        
            # 添加缺失的车站
            self._add_missing_stations()
            
            logger.info(f"加载了{len(self._stations)}个车站")
            
        except Exception as e:
            logger.error(f"解析车站数据失败: {e}")
            raise
    
    def _add_missing_stations(self):
        """
        添加缺失的车站.
        """
        missing_stations = [
            StationInfo(
                station_id='@cdd',
                station_name='成都东',
                station_code='WEI',
                station_pinyin='chengdudong',
                station_short='cdd',
                city='成都',
                code='1707'
            ),
            StationInfo(
                station_id='@szb',
                station_name='深圳北',
                station_code='IOQ',
                station_pinyin='shenzhenbei',
                station_short='szb',
                city='深圳',
                code='1708'
            )
        ]
        
        for station in missing_stations:
            if station.station_code not in self._stations:
                self._stations[station.station_code] = station
                
                if station.city not in self._city_stations:
                    self._city_stations[station.city] = []
                self._city_stations[station.city].append(station)
                
                self._name_stations[station.station_name] = station
    
    def _load_default_stations(self):
        """
        加载默认车站数据（备用）.
        """
        default_stations = [
            {
                'station_id': '@bjb',
                'station_name': '北京',
                'station_code': 'BJP',
                'station_pinyin': 'beijing',
                'station_short': 'bjb',
                'city': '北京',
                'code': '0001'
            },
            {
                'station_id': '@shh',
                'station_name': '上海',
                'station_code': 'SHH',
                'station_pinyin': 'shanghai',
                'station_short': 'shh',
                'city': '上海',
                'code': '0002'
            }
        ]
        
        for data in default_stations:
            station = StationInfo(**data)
            self._stations[station.station_code] = station
            
            if station.city not in self._city_stations:
                self._city_stations[station.city] = []
            self._city_stations[station.city].append(station)
            
            self._name_stations[station.station_name] = station
            self._city_codes[station.city] = station
    
    async def _get_lcquery_path(self):
        """
        获取中转查询路径.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.lcquery_init_url) as response:
                    html = await response.text()
                    
                match = re.search(r"var lc_search_url = '(.+?)'", html)
                if match:
                    self._lcquery_path = match.group(1)
                    logger.debug(f"获取中转查询路径: {self._lcquery_path}")
                else:
                    logger.warning("未找到中转查询路径")
                    
        except Exception as e:
            logger.error(f"获取中转查询路径失败: {e}")
    
    async def _get_cookie(self) -> Optional[str]:
        """
        获取Cookie.
        """
        try:
            url = f"{self.api_base}/otn/"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    cookies = response.cookies
                    if cookies:
                        cookie_str = '; '.join([f"{k}={v.value}" for k, v in cookies.items()])
                        return cookie_str
            return None
            
        except Exception as e:
            logger.error(f"获取Cookie失败: {e}")
            return None
    
    async def _make_request(self, url: str, params: dict = None) -> Optional[dict]:
        """
        发起请求.
        """
        try:
            cookie = await self._get_cookie()
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'X-Requested-With': 'XMLHttpRequest'
            }
            if cookie:
                headers['Cookie'] = cookie
                
            async with aiohttp.ClientSession() as session:
                if params:
                    url = f"{url}?{urlencode(params)}"
                    
                async with session.get(url, headers=headers) as response:
                    # 检查是否是错误页面
                    if response.content_type == 'text/html':
                        text = await response.text()
                        if 'error.html' in response.url.path or 'error' in text.lower():
                            logger.error(f"12306返回错误页面: {response.url}")
                            return None
                    
                    return await response.json()
                    
        except Exception as e:
            logger.error(f"请求失败: {e}")
            return None
    
    def get_current_date(self) -> str:
        """
        获取当前日期（上海时区）.
        """
        shanghai_tz = tz.gettz('Asia/Shanghai')
        now = datetime.now(shanghai_tz)
        return now.strftime('%Y-%m-%d')
    
    def get_stations_in_city(self, city: str) -> List[StationInfo]:
        """
        获取城市中的所有车站.
        """
        return self._city_stations.get(city, [])
    
    def get_city_main_station(self, city: str) -> Optional[StationInfo]:
        """
        获取城市主要车站.
        """
        return self._city_codes.get(city)
    
    def get_station_by_name(self, name: str) -> Optional[StationInfo]:
        """
        根据名称获取车站.
        """
        # 去掉后缀“站”
        if name.endswith('站'):
            name = name[:-1]
        return self._name_stations.get(name)
    
    def get_station_by_code(self, code: str) -> Optional[StationInfo]:
        """
        根据编码获取车站.
        """
        return self._stations.get(code)
    
    def _check_date(self, date_str: str) -> bool:
        """
        检查日期是否有效（不能早于今天）.
        """
        try:
            shanghai_tz = tz.gettz('Asia/Shanghai')
            now = datetime.now(shanghai_tz).replace(hour=0, minute=0, second=0, microsecond=0)
            target_date = datetime.fromisoformat(date_str).replace(tzinfo=shanghai_tz)
            target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            
            return target_date >= now
            
        except Exception:
            return False
    
    async def query_tickets(self, date: str, from_station: str, to_station: str,
                           train_filters: str = '', sort_by: str = '', 
                           reverse: bool = False, limit: int = 0) -> Tuple[bool, List[TrainTicket], str]:
        """
        查询车票.
        
        Args:
            date: 查询日期 (YYYY-MM-DD)
            from_station: 出发站编码
            to_station: 到达站编码  
            train_filters: 车次筛选 (G/D/Z/T/K/O)
            sort_by: 排序方式 (start_time/arrive_time/duration)
            reverse: 是否逆序
            limit: 限制数量
            
        Returns:
            (success, tickets, message)
        """
        try:
            # 检查日期
            if not self._check_date(date):
                return False, [], "日期不能早于今天"
            
            # 检查车站
            if from_station not in self._stations or to_station not in self._stations:
                return False, [], "车站编码不存在"
            
            # 构造请求参数
            params = {
                'leftTicketDTO.train_date': date,
                'leftTicketDTO.from_station': from_station,
                'leftTicketDTO.to_station': to_station,
                'purpose_codes': 'ADULT'
            }
            
            url = f"{self.api_base}/otn/leftTicket/query"
            data = await self._make_request(url, params)
            
            if not data or not data.get('status'):
                # 当12306 API不可用时，返回演示数据
                logger.warning("12306 API不可用，返回演示数据")
                return self._get_demo_tickets(date, from_station, to_station, train_filters, limit)
            
            # 解析数据
            tickets = self._parse_tickets_data(data.get('data', {}))
            
            # 过滤和排序
            tickets = self._filter_and_sort_tickets(tickets, train_filters, sort_by, reverse, limit)
            
            return True, tickets, "查询成功"
            
        except Exception as e:
            logger.error(f"查询车票失败: {e}", exc_info=True)
            # 返回演示数据作为fallback
            logger.info("返回演示数据作为fallback")
            return self._get_demo_tickets(date, from_station, to_station, train_filters, limit)
    
    def _get_demo_tickets(self, date: str, from_station: str, to_station: str, 
                         train_filters: str, limit: int) -> Tuple[bool, List[TrainTicket], str]:
        """
        获取演示车票数据.
        """
        from_station_info = self._stations.get(from_station)
        to_station_info = self._stations.get(to_station)
        
        if not from_station_info or not to_station_info:
            return False, [], "车站信息不完整"
            
        # 创建一些演示数据
        demo_tickets = [
            TrainTicket(
                train_no="240000G1001",
                start_train_code="G1001", 
                start_date=date,
                start_time="08:00",
                arrive_date=date,
                arrive_time="10:30",
                duration="02:30",
                from_station=from_station_info.station_name,
                to_station=to_station_info.station_name,
                from_station_code=from_station,
                to_station_code=to_station,
                prices=[
                    SeatPrice(
                        seat_name="二等座",
                        short="ze",
                        seat_type_code="O",
                        num="有",
                        price=200.5,
                        discount=None
                    ),
                    SeatPrice(
                        seat_name="一等座", 
                        short="zy",
                        seat_type_code="M",
                        num="5",
                        price=320.0,
                        discount=None
                    )
                ],
                features=["复兴号"]
            ),
            TrainTicket(
                train_no="240000G1003",
                start_train_code="G1003",
                start_date=date,
                start_time="09:15",
                arrive_date=date,
                arrive_time="11:45", 
                duration="02:30",
                from_station=from_station_info.station_name,
                to_station=to_station_info.station_name,
                from_station_code=from_station,
                to_station_code=to_station,
                prices=[
                    SeatPrice(
                        seat_name="二等座",
                        short="ze", 
                        seat_type_code="O",
                        num="充足",
                        price=200.5,
                        discount=None
                    ),
                    SeatPrice(
                        seat_name="一等座",
                        short="zy",
                        seat_type_code="M", 
                        num="13",
                        price=320.0,
                        discount=None
                    ),
                    SeatPrice(
                        seat_name="商务座",
                        short="swz",
                        seat_type_code="9",
                        num="2", 
                        price=650.0,
                        discount=None
                    )
                ],
                features=["复兴号", "静音车厢"]
            )
        ]
        
        # 应用筛选
        if train_filters:
            filtered_tickets = []
            for ticket in demo_tickets:
                for filter_char in train_filters:
                    if filter_char in self.train_filters:
                        if self.train_filters[filter_char](ticket.start_train_code):
                            filtered_tickets.append(ticket)
                            break
            demo_tickets = filtered_tickets
        
        # 应用限制
        if limit > 0:
            demo_tickets = demo_tickets[:limit]
            
        message = f"演示数据: 查询到{len(demo_tickets)}个车次 (注意: 这是演示数据，非实时车票信息)"
        return True, demo_tickets, message
    
    def _parse_tickets_data(self, data: dict) -> List[TrainTicket]:
        """
        解析车票数据.
        """
        tickets = []
        
        try:
            results = data.get('result', [])
            station_map = data.get('map', {})
            
            for result_str in results:
                values = result_str.split('|')
                if len(values) < 57:  # 数据不完整
                    continue
                
                # 解析基本信息
                train_no = values[2]
                train_code = values[3]
                start_time = values[8]
                arrive_time = values[9]
                duration = values[10]
                from_code = values[6]
                to_code = values[7]
                start_date_str = values[13]
                
                # 计算日期
                start_date = datetime.strptime(start_date_str, '%Y%m%d')
                
                # 安全解析时间，处理可能的格式问题
                try:
                    start_hour, start_minute = map(int, start_time.split(':'))
                    if start_hour < 0 or start_hour > 23 or start_minute < 0 or start_minute > 59:
                        logger.warning(f"无效的开始时间: {start_time}")
                        continue
                        
                    duration_hour, duration_minute = map(int, duration.split(':'))
                    if duration_hour < 0 or duration_minute < 0:
                        logger.warning(f"无效的历时: {duration}")
                        continue
                        
                    start_datetime = start_date.replace(hour=start_hour, minute=start_minute)
                    arrive_datetime = start_datetime + timedelta(hours=duration_hour, minutes=duration_minute)
                    
                except (ValueError, IndexError) as e:
                    logger.warning(f"时间解析失败 start_time={start_time}, duration={duration}: {e}")
                    continue
                
                # 解析价格信息
                prices = self._parse_prices(values[42], values[54], values)
                
                # 解析特性标记
                features = self._parse_features(values[46])
                
                ticket = TrainTicket(
                    train_no=train_no,
                    start_train_code=train_code,
                    start_date=start_datetime.strftime('%Y-%m-%d'),
                    start_time=start_time,
                    arrive_date=arrive_datetime.strftime('%Y-%m-%d'),
                    arrive_time=arrive_time,
                    duration=duration,
                    from_station=station_map.get(from_code, from_code),
                    to_station=station_map.get(to_code, to_code),
                    from_station_code=from_code,
                    to_station_code=to_code,
                    prices=prices,
                    features=features
                )
                
                tickets.append(ticket)
                
        except Exception as e:
            logger.error(f"解析车票数据失败: {e}")
            
        return tickets
    
    def _parse_prices(self, yp_info: str, discount_info: str, values: list) -> List[SeatPrice]:
        """
        解析价格信息.
        """
        prices = []
        
        try:
            # 解析折扣信息
            discounts = {}
            for i in range(0, len(discount_info), 5):
                if i + 4 < len(discount_info):
                    seat_code = discount_info[i]
                    discount_val = int(discount_info[i+1:i+5])
                    discounts[seat_code] = discount_val
            
            # 解析价格信息
            for i in range(0, len(yp_info), 10):
                if i + 9 < len(yp_info):
                    price_str = yp_info[i:i+10]
                    seat_code = price_str[0]
                    
                    # 特殊处理无座
                    if int(price_str[6:10]) >= 3000:
                        seat_code = 'W'
                    elif seat_code not in self.seat_types:
                        seat_code = 'H'
                    
                    seat_info = self.seat_types.get(seat_code, {'name': '其他', 'short': 'qt'})
                    price_value = int(price_str[1:6]) / 10
                    
                    # 获取余票数量
                    seat_num_field = f"{seat_info['short']}_num"
                    seat_num_index = self._get_seat_num_index(seat_num_field)
                    num = values[seat_num_index] if seat_num_index < len(values) else "--"
                    
                    price = SeatPrice(
                        seat_name=seat_info['name'],
                        short=seat_info['short'],
                        seat_type_code=seat_code,
                        num=num,
                        price=price_value,
                        discount=discounts.get(seat_code)
                    )
                    
                    prices.append(price)
                    
        except Exception as e:
            logger.error(f"解析价格信息失败: {e}")
            
        return prices
    
    def _get_seat_num_index(self, seat_field: str) -> int:
        """
        获取座位数量字段的索引.
        """
        seat_indices = {
            'gg_num': 22, 'gr_num': 23, 'qt_num': 24, 'rw_num': 25,
            'rz_num': 26, 'tz_num': 27, 'wz_num': 28, 'yb_num': 29,
            'yw_num': 30, 'yz_num': 31, 'ze_num': 32, 'zy_num': 33,
            'swz_num': 34, 'srrb_num': 35
        }
        return seat_indices.get(seat_field, 24)
    
    def _parse_features(self, dw_flag: str) -> List[str]:
        """
        解析特性标记.
        """
        features = []
        
        try:
            flags = dw_flag.split('#')
            
            if len(flags) > 0 and flags[0] == '5':
                features.append(self.dw_flags[0])  # 智能动车组
            
            if len(flags) > 1 and flags[1] == '1':
                features.append(self.dw_flags[1])  # 复兴号
            
            if len(flags) > 2:
                if flags[2].startswith('Q'):
                    features.append(self.dw_flags[2])  # 静音车厢
                elif flags[2].startswith('R'):
                    features.append(self.dw_flags[3])  # 温馨动卧
            
            if len(flags) > 5 and flags[5] == 'D':
                features.append(self.dw_flags[4])  # 动感号
            
            if len(flags) > 6 and flags[6] != 'z':
                features.append(self.dw_flags[5])  # 支持选铺
            
            if len(flags) > 7 and flags[7] != 'z':
                features.append(self.dw_flags[6])  # 老年优惠
                
        except Exception as e:
            logger.error(f"解析特性标记失败: {e}")
            
        return features
    
    def _filter_and_sort_tickets(self, tickets: List[TrainTicket], train_filters: str,
                                sort_by: str, reverse: bool, limit: int) -> List[TrainTicket]:
        """
        过滤和排序车票.
        """
        result = tickets
        
        # 过滤车次类型
        if train_filters:
            filtered = []
            for ticket in result:
                for filter_char in train_filters:
                    if filter_char in self.train_filters:
                        if self.train_filters[filter_char](ticket.start_train_code):
                            filtered.append(ticket)
                            break
            result = filtered
        
        # 排序
        if sort_by == 'start_time':
            result.sort(key=lambda t: (t.start_date, t.start_time))
        elif sort_by == 'arrive_time':
            result.sort(key=lambda t: (t.arrive_date, t.arrive_time))
        elif sort_by == 'duration':
            result.sort(key=lambda t: t.duration)
        
        if reverse:
            result.reverse()
        
        # 限制数量
        if limit > 0:
            result = result[:limit]
        
        return result

    def _get_demo_transfers(
        self, date: str, from_station: str, to_station: str, 
        middle_station: str, limit: int
    ) -> List[Dict]:
        """
        获取演示中转数据.
        """
        from_info = self._stations.get(from_station)
        to_info = self._stations.get(to_station)
        
        if not from_info or not to_info:
            return []
        
        # 创建演示中转数据
        demo_transfers = [
            {
                "start_date": date,
                "start_time": "08:00",
                "arrive_date": date, 
                "arrive_time": "14:30",
                "duration": "06:30",
                "from_station": from_info.station_name,
                "to_station": to_info.station_name,
                "middle_station": "武汉",
                "transfer_type": "同站换乘",
                "wait_time": "45分钟",
                "segments": [
                    {
                        "train_code": "G1001",
                        "from_station": from_info.station_name,
                        "to_station": "武汉",
                        "start_time": "08:00",
                        "arrive_time": "11:15",
                        "duration": "03:15",
                        "prices": [
                            {"seat_name": "二等座", "price": 180.5, "num": "有"},
                            {"seat_name": "一等座", "price": 290.0, "num": "3"}
                        ]
                    },
                    {
                        "train_code": "G1025", 
                        "from_station": "武汉",
                        "to_station": to_info.station_name,
                        "start_time": "12:00",
                        "arrive_time": "14:30",
                        "duration": "02:30",
                        "prices": [
                            {"seat_name": "二等座", "price": 160.0, "num": "有"},
                            {"seat_name": "一等座", "price": 260.0, "num": "7"}
                        ]
                    }
                ]
            },
            {
                "start_date": date,
                "start_time": "10:30", 
                "arrive_date": date,
                "arrive_time": "17:45",
                "duration": "07:15",
                "from_station": from_info.station_name,
                "to_station": to_info.station_name,
                "middle_station": "长沙南",
                "transfer_type": "同站换乘",
                "wait_time": "1小时20分钟",
                "segments": [
                    {
                        "train_code": "G1007",
                        "from_station": from_info.station_name,
                        "to_station": "长沙南", 
                        "start_time": "10:30",
                        "arrive_time": "13:50",
                        "duration": "03:20",
                        "prices": [
                            {"seat_name": "二等座", "price": 200.0, "num": "有"},
                            {"seat_name": "一等座", "price": 320.0, "num": "2"}
                        ]
                    },
                    {
                        "train_code": "G1047",
                        "from_station": "长沙南",
                        "to_station": to_info.station_name,
                        "start_time": "15:10", 
                        "arrive_time": "17:45",
                        "duration": "02:35",
                        "prices": [
                            {"seat_name": "二等座", "price": 145.5, "num": "有"},
                            {"seat_name": "一等座", "price": 235.0, "num": "5"}
                        ]
                    }
                ]
            }
        ]
        
        return demo_transfers[:limit]


# 全局客户端实例
_client = None


async def get_railway_client() -> Railway12306Client:
    """
    获取铁路客户端单例.
    """
    global _client
    if _client is None:
        _client = Railway12306Client()
        await _client.initialize()
    return _client
