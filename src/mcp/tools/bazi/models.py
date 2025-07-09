"""
八字命理数据模型。
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class HeavenStem:
    """天干"""

    name: str
    element: str  # 五行
    yin_yang: int  # 阴阳，1=阳，-1=阴

    def __str__(self):
        return self.name

    def get_element(self):
        return self.element

    def get_yin_yang(self):
        return self.yin_yang

    def get_ten_star(self, other_stem: "HeavenStem") -> str:
        """
        获取十神关系.
        """
        # 实现十神逻辑
        return self._calculate_ten_star(other_stem)

    def _calculate_ten_star(self, other: "HeavenStem") -> str:
        """计算十神关系 - 使用专业数据"""
        from .professional_data import get_ten_gods_relation

        return get_ten_gods_relation(self.name, other.name)


@dataclass
class EarthBranch:
    """地支"""

    name: str
    element: str  # 五行
    yin_yang: int  # 阴阳
    zodiac: str  # 生肖
    hide_heaven_main: Optional[str] = None  # 藏干主气
    hide_heaven_middle: Optional[str] = None  # 藏干中气
    hide_heaven_residual: Optional[str] = None  # 藏干余气

    def __str__(self):
        return self.name

    def get_element(self):
        return self.element

    def get_yin_yang(self):
        return self.yin_yang

    def get_zodiac(self):
        return self.zodiac

    def get_hide_heaven_stem_main(self):
        return self.hide_heaven_main

    def get_hide_heaven_stem_middle(self):
        return self.hide_heaven_middle

    def get_hide_heaven_stem_residual(self):
        return self.hide_heaven_residual


@dataclass
class SixtyCycle:
    """
    六十甲子.
    """

    heaven_stem: HeavenStem
    earth_branch: EarthBranch
    sound: str  # 纳音
    ten: str  # 旬
    extra_earth_branches: List[str]  # 空亡

    def __str__(self):
        return f"{self.heaven_stem.name}{self.earth_branch.name}"

    def get_heaven_stem(self):
        return self.heaven_stem

    def get_earth_branch(self):
        return self.earth_branch

    def get_sound(self):
        return self.sound

    def get_ten(self):
        return self.ten

    def get_extra_earth_branches(self):
        return self.extra_earth_branches


@dataclass
class EightChar:
    """八字"""

    year: SixtyCycle
    month: SixtyCycle
    day: SixtyCycle
    hour: SixtyCycle

    def __str__(self):
        return f"{self.year} {self.month} {self.day} {self.hour}"

    def get_year(self):
        return self.year

    def get_month(self):
        return self.month

    def get_day(self):
        return self.day

    def get_hour(self):
        return self.hour

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式，供专业分析使用.
        """
        return {
            "year": {
                "heaven_stem": {"name": self.year.heaven_stem.name},
                "earth_branch": {"name": self.year.earth_branch.name},
            },
            "month": {
                "heaven_stem": {"name": self.month.heaven_stem.name},
                "earth_branch": {"name": self.month.earth_branch.name},
            },
            "day": {
                "heaven_stem": {"name": self.day.heaven_stem.name},
                "earth_branch": {"name": self.day.earth_branch.name},
            },
            "hour": {
                "heaven_stem": {"name": self.hour.heaven_stem.name},
                "earth_branch": {"name": self.hour.earth_branch.name},
            },
        }


@dataclass
class LunarTime:
    """
    农历时间.
    """

    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    is_leap: bool = False  # 是否闰月

    def __str__(self):
        leap_text = "闰" if self.is_leap else ""
        return f"农历{self.year}年{leap_text}{self.month}月{self.day}日{self.hour}时{self.minute}分{self.second}秒"


@dataclass
class SolarTime:
    """
    公历时间.
    """

    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int

    def __str__(self):
        return f"{self.year}年{self.month}月{self.day}日{self.hour}时{self.minute}分{self.second}秒"

    def get_year(self):
        return self.year

    def get_month(self):
        return self.month

    def get_day(self):
        return self.day

    def get_hour(self):
        return self.hour

    def get_minute(self):
        return self.minute

    def get_second(self):
        return self.second


@dataclass
class BaziAnalysis:
    """
    八字分析结果.
    """

    gender: str  # 性别
    solar_time: str  # 阳历
    lunar_time: str  # 农历
    bazi: str  # 八字
    zodiac: str  # 生肖
    day_master: str  # 日主
    year_pillar: Dict[str, Any]  # 年柱
    month_pillar: Dict[str, Any]  # 月柱
    day_pillar: Dict[str, Any]  # 日柱
    hour_pillar: Dict[str, Any]  # 时柱
    fetal_origin: str  # 胎元
    fetal_breath: str  # 胎息
    own_sign: str  # 命宫
    body_sign: str  # 身宫
    gods: Dict[str, List[str]]  # 神煞
    fortune: Dict[str, Any]  # 大运
    relations: Dict[str, Any]  # 刑冲合会

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典.
        """
        result = {
            "性别": self.gender,
            "阳历": self.solar_time,
            "农历": self.lunar_time,
            "八字": self.bazi,
            "生肖": self.zodiac,
            "日主": self.day_master,
            "年柱": self.year_pillar,
            "月柱": self.month_pillar,
            "日柱": self.day_pillar,
            "时柱": self.hour_pillar,
            "胎元": self.fetal_origin,
            "胎息": self.fetal_breath,
            "命宫": self.own_sign,
            "身宫": self.body_sign,
            "神煞": self.gods,
            "大运": self.fortune,
            "刑冲合会": self.relations,
        }

        # 添加专业分析结果（如果存在）
        if hasattr(self, "_professional_analysis"):
            result["专业分析"] = self._professional_analysis
        if hasattr(self, "_detailed_fortune_text"):
            result["详细命理分析"] = self._detailed_fortune_text

        return result


@dataclass
class ChineseCalendar:
    """
    黄历信息.
    """

    solar_date: str  # 公历
    lunar_date: str  # 农历
    gan_zhi: str  # 干支
    zodiac: str  # 生肖
    na_yin: str  # 纳音
    lunar_festival: Optional[str]  # 农历节日
    solar_festival: Optional[str]  # 公历节日
    solar_term: str  # 节气
    twenty_eight_star: str  # 二十八宿
    pengzu_taboo: str  # 彭祖百忌
    joy_direction: str  # 喜神方位
    yang_direction: str  # 阳贵神方位
    yin_direction: str  # 阴贵神方位
    mascot_direction: str  # 福神方位
    wealth_direction: str  # 财神方位
    clash: str  # 冲煞
    suitable: str  # 宜
    avoid: str  # 忌

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典.
        """
        return {
            "公历": self.solar_date,
            "农历": self.lunar_date,
            "干支": self.gan_zhi,
            "生肖": self.zodiac,
            "纳音": self.na_yin,
            "农历节日": self.lunar_festival,
            "公历节日": self.solar_festival,
            "节气": self.solar_term,
            "二十八宿": self.twenty_eight_star,
            "彭祖百忌": self.pengzu_taboo,
            "喜神方位": self.joy_direction,
            "阳贵神方位": self.yang_direction,
            "阴贵神方位": self.yin_direction,
            "福神方位": self.mascot_direction,
            "财神方位": self.wealth_direction,
            "冲煞": self.clash,
            "宜": self.suitable,
            "忌": self.avoid,
        }
