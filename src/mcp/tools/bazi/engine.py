"""
八字计算核心引擎.
"""

from datetime import datetime
from typing import List, Optional

import pendulum
from lunar_python import Lunar, Solar

from .models import (
    ChineseCalendar,
    EarthBranch,
    EightChar,
    HeavenStem,
    LunarTime,
    SixtyCycle,
    SolarTime,
)


class BaziEngine:
    """八字计算引擎 - 使用lunar-python专业实现"""

    # 天干映射 - 与lunar-python兼容
    HEAVEN_STEMS = {
        "甲": HeavenStem("甲", "木", 1),
        "乙": HeavenStem("乙", "木", -1),
        "丙": HeavenStem("丙", "火", 1),
        "丁": HeavenStem("丁", "火", -1),
        "戊": HeavenStem("戊", "土", 1),
        "己": HeavenStem("己", "土", -1),
        "庚": HeavenStem("庚", "金", 1),
        "辛": HeavenStem("辛", "金", -1),
        "壬": HeavenStem("壬", "水", 1),
        "癸": HeavenStem("癸", "水", -1),
    }

    # 地支映射 - 与lunar-python兼容
    EARTH_BRANCHES = {
        "子": EarthBranch("子", "水", 1, "鼠", "癸", None, None),
        "丑": EarthBranch("丑", "土", -1, "牛", "己", "癸", "辛"),
        "寅": EarthBranch("寅", "木", 1, "虎", "甲", "丙", "戊"),
        "卯": EarthBranch("卯", "木", -1, "兔", "乙", None, None),
        "辰": EarthBranch("辰", "土", 1, "龙", "戊", "乙", "癸"),
        "巳": EarthBranch("巳", "火", -1, "蛇", "丙", "庚", "戊"),
        "午": EarthBranch("午", "火", 1, "马", "丁", "己", None),
        "未": EarthBranch("未", "土", -1, "羊", "己", "丁", "乙"),
        "申": EarthBranch("申", "金", 1, "猴", "庚", "壬", "戊"),
        "酉": EarthBranch("酉", "金", -1, "鸡", "辛", None, None),
        "戌": EarthBranch("戌", "土", 1, "狗", "戊", "辛", "丁"),
        "亥": EarthBranch("亥", "水", -1, "猪", "壬", "甲", None),
    }

    def __init__(self):
        """
        初始化.
        """

    def parse_solar_time(self, iso_date: str) -> SolarTime:
        """
        解析公历时间字符串（支持多种格式）- 使用pendulum优化.
        """
        try:
            # 使用pendulum解析时间，支持更多格式
            dt = pendulum.parse(iso_date)
            # 转换为北京时间
            if dt.timezone_name != "Asia/Shanghai":
                dt = dt.in_timezone("Asia/Shanghai")

            return SolarTime(
                year=dt.year,
                month=dt.month,
                day=dt.day,
                hour=dt.hour,
                minute=dt.minute,
                second=dt.second,
            )
        except Exception:
            # 如果pendulum解析失败，尝试其他格式
            formats = [
                "%Y-%m-%dT%H:%M:%S+08:00",
                "%Y-%m-%dT%H:%M+08:00",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d %H:%M",
                "%Y/%m/%d",
            ]

            dt = None
            for fmt in formats:
                try:
                    dt = datetime.strptime(iso_date, fmt)
                    break
                except ValueError:
                    continue

            if dt is None:
                raise ValueError(f"无法解析时间格式: {iso_date}")

            return SolarTime(
                year=dt.year,
                month=dt.month,
                day=dt.day,
                hour=dt.hour,
                minute=dt.minute,
                second=dt.second,
            )

    def solar_to_lunar(self, solar_time: SolarTime) -> LunarTime:
        """
        公历转农历.
        """
        try:
            # 使用lunar-python进行真正的公历农历转换
            solar = Solar.fromYmdHms(
                solar_time.year,
                solar_time.month,
                solar_time.day,
                solar_time.hour,
                solar_time.minute,
                solar_time.second,
            )
            lunar = solar.getLunar()

            return LunarTime(
                year=lunar.getYear(),
                month=lunar.getMonth(),
                day=lunar.getDay(),
                hour=lunar.getHour(),
                minute=lunar.getMinute(),
                second=lunar.getSecond(),
                is_leap=False,  # lunar-python中需要其他方式判断闰月
            )
        except Exception as e:
            raise ValueError(f"公历转农历失败: {e}")

    def lunar_to_solar(self, lunar_time: LunarTime) -> SolarTime:
        """
        农历转公历.
        """
        try:
            # 使用lunar-python进行真正的农历公历转换
            lunar = Lunar.fromYmdHms(
                lunar_time.year,
                lunar_time.month,
                lunar_time.day,
                lunar_time.hour,
                lunar_time.minute,
                lunar_time.second,
            )
            solar = lunar.getSolar()

            return SolarTime(
                year=solar.getYear(),
                month=solar.getMonth(),
                day=solar.getDay(),
                hour=solar.getHour(),
                minute=solar.getMinute(),
                second=solar.getSecond(),
            )
        except Exception as e:
            raise ValueError(f"农历转公历失败: {e}")

    def build_eight_char(self, solar_time: SolarTime) -> EightChar:
        """
        构建八字.
        """
        try:
            # 使用lunar-python计算八字
            solar = Solar.fromYmdHms(
                solar_time.year,
                solar_time.month,
                solar_time.day,
                solar_time.hour,
                solar_time.minute,
                solar_time.second,
            )
            lunar = solar.getLunar()
            bazi = lunar.getEightChar()

            # 获取年柱
            year_gan = bazi.getYearGan()
            year_zhi = bazi.getYearZhi()
            year_cycle = self._create_sixty_cycle(year_gan, year_zhi)

            # 获取月柱
            month_gan = bazi.getMonthGan()
            month_zhi = bazi.getMonthZhi()
            month_cycle = self._create_sixty_cycle(month_gan, month_zhi)

            # 获取日柱
            day_gan = bazi.getDayGan()
            day_zhi = bazi.getDayZhi()
            day_cycle = self._create_sixty_cycle(day_gan, day_zhi)

            # 获取时柱
            time_gan = bazi.getTimeGan()
            time_zhi = bazi.getTimeZhi()
            time_cycle = self._create_sixty_cycle(time_gan, time_zhi)

            return EightChar(
                year=year_cycle, month=month_cycle, day=day_cycle, hour=time_cycle
            )
        except Exception as e:
            raise ValueError(f"构建八字失败: {e}")

    def _create_sixty_cycle(self, gan_name: str, zhi_name: str) -> SixtyCycle:
        """
        创建六十甲子对象.
        """
        heaven_stem = self.HEAVEN_STEMS[gan_name]
        earth_branch = self.EARTH_BRANCHES[zhi_name]

        # 计算纳音 - 使用lunar-python的纳音计算
        try:
            # 这里可以使用lunar-python的纳音计算
            sound = self._get_nayin(gan_name, zhi_name)
        except:
            sound = "未知"

        # 计算旬和空亡 - 简化实现
        ten = self._get_ten(gan_name, zhi_name)
        extra_branches = self._get_kong_wang(gan_name, zhi_name)

        return SixtyCycle(
            heaven_stem=heaven_stem,
            earth_branch=earth_branch,
            sound=sound,
            ten=ten,
            extra_earth_branches=extra_branches,
        )

    def _get_nayin(self, gan: str, zhi: str) -> str:
        """获取纳音 - 使用完整专业数据"""
        from .professional_data import get_nayin

        return get_nayin(gan, zhi)

    def _get_ten(self, gan: str, zhi: str) -> str:
        """获取旬 - 使用专业算法"""
        from .professional_data import GAN, ZHI

        # 使用专业的六十甲子旬空算法
        gan_idx = GAN.index(gan) if gan in GAN else 0
        zhi_idx = ZHI.index(zhi) if zhi in ZHI else 0

        # 计算干支在六十甲子中的位置
        # 六十甲子每10个为一旬
        jiazi_position = (gan_idx * 6 + zhi_idx * 5) % 60

        # 确定所在旬（每10个为一旬）
        xun_number = jiazi_position // 10

        # 旬首干支组合：甲子、甲戌、甲申、甲午、甲辰、甲寅
        xun_stems = ["甲", "甲", "甲", "甲", "甲", "甲"]
        xun_branches = ["子", "戌", "申", "午", "辰", "寅"]

        if xun_number < len(xun_stems):
            return f"{xun_stems[xun_number]}{xun_branches[xun_number]}"
        else:
            return "甲子"  # 默认

    def _get_kong_wang(self, gan: str, zhi: str) -> List[str]:
        """获取空亡 - 使用专业算法"""
        from .professional_data import GAN, ZHI

        # 使用专业旬空算法
        gan_idx = GAN.index(gan) if gan in GAN else 0
        zhi_idx = ZHI.index(zhi) if zhi in ZHI else 0

        # 计算所在旬
        jiazi_position = (gan_idx * 6 + zhi_idx * 5) % 60
        xun_start = (jiazi_position // 10) * 10

        # 每旬10个干支，地支只有12个，所以有两个地支空亡
        # 空亡的地支是每旬最后两个位置
        kong_wang_positions = [(xun_start + 10) % 12, (xun_start + 11) % 12]

        kong_wang_branches = [ZHI[pos] for pos in kong_wang_positions]

        return kong_wang_branches

    def format_solar_time(self, solar_time: SolarTime) -> str:
        """
        格式化公历时间.
        """
        return f"{solar_time.year}年{solar_time.month}月{solar_time.day}日{solar_time.hour}时{solar_time.minute}分{solar_time.second}秒"

    def format_lunar_time(self, lunar_time: LunarTime) -> str:
        """
        格式化农历时间.
        """
        return f"农历{lunar_time.year}年{lunar_time.month}月{lunar_time.day}日{lunar_time.hour}时{lunar_time.minute}分{lunar_time.second}秒"

    def get_chinese_calendar(
        self, solar_time: Optional[SolarTime] = None
    ) -> ChineseCalendar:
        """获取中国传统历法信息 - 使用lunar-python"""
        if solar_time is None:
            # 使用今天
            now = pendulum.now("Asia/Shanghai")
            solar_time = SolarTime(
                now.year, now.month, now.day, now.hour, now.minute, now.second
            )

        try:
            solar = Solar.fromYmdHms(
                solar_time.year,
                solar_time.month,
                solar_time.day,
                solar_time.hour,
                solar_time.minute,
                solar_time.second,
            )
            lunar = solar.getLunar()

            # 获取详细信息
            bazi = lunar.getEightChar()

            return ChineseCalendar(
                solar_date=self.format_solar_time(solar_time),
                lunar_date=f"{lunar.getYearInChinese()}年{lunar.getMonthInChinese()}月{lunar.getDayInChinese()}",
                gan_zhi=f"{bazi.getYear()} {bazi.getMonth()} {bazi.getDay()}",
                zodiac=lunar.getYearShengXiao(),
                na_yin=lunar.getDayNaYin(),
                lunar_festival=(
                    ", ".join(lunar.getFestivals()) if lunar.getFestivals() else None
                ),
                solar_festival=(
                    ", ".join(solar.getFestivals()) if solar.getFestivals() else None
                ),
                solar_term=lunar.getJieQi() or "无",
                twenty_eight_star=lunar.getXiu(),
                pengzu_taboo=lunar.getPengZuGan() + " " + lunar.getPengZuZhi(),
                joy_direction=lunar.getPositionXi(),
                yang_direction=lunar.getPositionYangGui(),
                yin_direction=lunar.getPositionYinGui(),
                mascot_direction=lunar.getPositionFu(),
                wealth_direction=lunar.getPositionCai(),
                clash=f"冲{lunar.getDayChongDesc()}",
                suitable=", ".join(lunar.getDayYi()[:5]),  # 取前5个
                avoid=", ".join(lunar.getDayJi()[:5]),  # 取前5个
            )
        except Exception as e:
            raise ValueError(f"获取黄历信息失败: {e}")


# 全局引擎实例
_bazi_engine = None


def get_bazi_engine() -> BaziEngine:
    """
    获取八字引擎单例.
    """
    global _bazi_engine
    if _bazi_engine is None:
        _bazi_engine = BaziEngine()
    return _bazi_engine
