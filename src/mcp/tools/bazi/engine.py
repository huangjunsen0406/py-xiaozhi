"""
八字计算核心引擎.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

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
from .professional_data import (
    GAN,
    GAN_WUXING,
    GAN_YINYANG,
    SHENG_XIAO,
    ZHI,
    ZHI_CANG_GAN,
    ZHI_WUXING,
    ZHI_YINYANG,
)


class BaziEngine:
    """
    八字计算引擎.
    """

    # 动态构建天干映射 - 基于 professional_data.py 的数据
    HEAVEN_STEMS = {}
    for gan in GAN:
        HEAVEN_STEMS[gan] = HeavenStem(
            name=gan, element=GAN_WUXING[gan], yin_yang=GAN_YINYANG[gan]
        )

    # 动态构建地支映射 - 基于 professional_data.py 的数据
    EARTH_BRANCHES = {}
    for i, zhi in enumerate(ZHI):
        # 获取地支的藏干
        cang_gan = ZHI_CANG_GAN.get(zhi, {})
        cang_gan_list = list(cang_gan.keys())

        # 构建 EarthBranch 对象
        EARTH_BRANCHES[zhi] = EarthBranch(
            name=zhi,
            element=ZHI_WUXING[zhi],
            yin_yang=ZHI_YINYANG[zhi],
            zodiac=SHENG_XIAO[i],
            hide_heaven_main=cang_gan_list[0] if len(cang_gan_list) > 0 else None,
            hide_heaven_middle=cang_gan_list[1] if len(cang_gan_list) > 1 else None,
            hide_heaven_residual=cang_gan_list[2] if len(cang_gan_list) > 2 else None,
        )

    def __init__(self):
        """
        初始化.
        """

    def parse_solar_time(self, iso_date: str) -> SolarTime:
        """
        解析公历时间字符串（支持多种格式）- 使用pendulum优化，增强时区处理.
        """
        try:
            # 使用pendulum解析时间，支持更多格式
            dt = pendulum.parse(iso_date)

            # 智能时区处理
            if dt.timezone_name == "UTC":
                # 如果pendulum解析为UTC（说明原始输入没有时区），将其当作北京时间处理
                dt = dt.replace(tzinfo=pendulum.timezone("Asia/Shanghai"))
            elif dt.timezone_name is None:
                # 如果没有时区信息，将其设置为北京时间
                dt = dt.replace(tzinfo=pendulum.timezone("Asia/Shanghai"))
            elif dt.timezone_name != "Asia/Shanghai":
                # 转换为北京时间
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
                "%Y-%m-%dT%H:%M:%S+0800",
                "%Y-%m-%dT%H:%M:%S.%f+08:00",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M+08:00",
                "%Y-%m-%dT%H:%M",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d %H:%M",
                "%Y/%m/%d",
                "%Y年%m月%d日 %H时%M分%S秒",
                "%Y年%m月%d日 %H时%M分",
                "%Y年%m月%d日",
            ]

            dt = None
            for fmt in formats:
                try:
                    dt = datetime.strptime(iso_date, fmt)
                    break
                except ValueError:
                    continue

            if dt is None:
                raise ValueError(
                    f"无法解析时间格式: {iso_date}，支持的格式包括ISO8601、中文格式等"
                )

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
        公历转农历 - 增强闰月处理.
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

            # 判断是否为闰月
            is_leap = lunar.isLeap() if hasattr(lunar, "isLeap") else False

            # 如果lunar-python没有isLeap方法，使用其他方式判断
            if not hasattr(lunar, "isLeap"):
                # 通过月份字符串判断（如果包含"闰"字）
                month_str = lunar.getMonthInChinese()
                is_leap = "闰" in month_str

            return LunarTime(
                year=lunar.getYear(),
                month=lunar.getMonth(),
                day=lunar.getDay(),
                hour=lunar.getHour(),
                minute=lunar.getMinute(),
                second=lunar.getSecond(),
                is_leap=is_leap,
            )
        except Exception as e:
            raise ValueError(f"公历转农历失败: {e}")

    def lunar_to_solar(self, lunar_time: LunarTime) -> SolarTime:
        """
        农历转公历 - 增强闰月处理.
        """
        try:
            # 处理闰月
            if lunar_time.is_leap:
                # 如果是闰月，使用特殊方法创建农历对象
                lunar = Lunar.fromYmdHms(
                    lunar_time.year,
                    -lunar_time.month,  # 闰月用负数表示
                    lunar_time.day,
                    lunar_time.hour,
                    lunar_time.minute,
                    lunar_time.second,
                )
            else:
                # 普通月份
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

        # 计算纳音
        try:
            # 使用纳音数据
            sound = self._get_nayin(gan_name, zhi_name)
        except Exception as e:
            # 记录具体错误，但不影响整体功能
            print(f"纳音计算失败: {gan_name}{zhi_name} - {e}")
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
        """
        获取纳音.
        """
        from .professional_data import get_nayin

        return get_nayin(gan, zhi)

    def _get_ten(self, gan: str, zhi: str) -> str:
        """获取旬 - 使用六十甲子旬空算法"""
        from .professional_data import GAN, ZHI

        try:
            # 使用标准的六十甲子计算方法
            gan_idx = GAN.index(gan)
            zhi_idx = ZHI.index(zhi)

            # 计算在六十甲子中的序号（从1开始）
            jiazi_number = (gan_idx * 6 + zhi_idx * 5) % 60
            if jiazi_number == 0:
                jiazi_number = 60

            # 六旬的旬首
            xun_starts = ["甲子", "甲戌", "甲申", "甲午", "甲辰", "甲寅"]

            # 确定所在旬（每10个为一旬）
            xun_index = (jiazi_number - 1) // 10

            if 0 <= xun_index < len(xun_starts):
                return xun_starts[xun_index]
            else:
                # 使用更精确的计算方法
                return self._calculate_xun_by_position(jiazi_number)
        except (ValueError, IndexError) as e:
            print(f"旬计算失败: {gan}{zhi} - {e}")
            return "甲子"

    def _get_kong_wang(self, gan: str, zhi: str) -> List[str]:
        """获取空亡 - 使用传统旬空算法"""
        from .professional_data import GAN, ZHI

        try:
            gan_idx = GAN.index(gan)
            zhi_idx = ZHI.index(zhi)

            # 计算在六十甲子中的序号
            jiazi_number = (gan_idx * 6 + zhi_idx * 5) % 60
            if jiazi_number == 0:
                jiazi_number = 60

            # 确定所在旬
            xun_index = (jiazi_number - 1) // 10

            # 六旬的空亡地支
            kong_wang_table = [
                ["戌", "亥"],  # 甲子旬
                ["申", "酉"],  # 甲戌旬
                ["午", "未"],  # 甲申旬
                ["辰", "巳"],  # 甲午旬
                ["寅", "卯"],  # 甲辰旬
                ["子", "丑"],  # 甲寅旬
            ]

            if 0 <= xun_index < len(kong_wang_table):
                return kong_wang_table[xun_index]
            else:
                # 备用计算方法
                return self._calculate_kong_wang_by_position(jiazi_number)
        except (ValueError, IndexError) as e:
            print(f"空亡计算失败: {gan}{zhi} - {e}")
            return ["戌", "亥"]  # 默认返回甲子旬空亡

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

    def _calculate_xun_by_position(self, jiazi_number: int) -> str:
        """
        根据六十甲子序号计算旬.
        """
        # 从 professional_data.py 使用 GANZHI_60
        # 每旬的旬首
        xun_starts = ["甲子", "甲戌", "甲申", "甲午", "甲辰", "甲寅"]

        xun_index = (jiazi_number - 1) // 10
        if 0 <= xun_index < len(xun_starts):
            return xun_starts[xun_index]
        else:
            return "甲子"

    def _calculate_kong_wang_by_position(self, jiazi_number: int) -> List[str]:
        """
        根据六十甲子序号计算空亡.
        """
        # 六旬的空亡地支
        kong_wang_table = [
            ["戌", "亥"],  # 甲子旬
            ["申", "酉"],  # 甲戌旬
            ["午", "未"],  # 甲申旬
            ["辰", "巳"],  # 甲午旬
            ["寅", "卯"],  # 甲辰旬
            ["子", "丑"],  # 甲寅旬
        ]

        xun_index = (jiazi_number - 1) // 10
        if 0 <= xun_index < len(kong_wang_table):
            return kong_wang_table[xun_index]
        else:
            return ["戌", "亥"]

    def get_detailed_lunar_info(self, solar_time: SolarTime) -> Dict[str, Any]:
        """
        获取详细的农历信息.
        """
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

            # 获取节气信息
            current_jieqi = lunar.getJieQi()
            next_jieqi = lunar.getNextJieQi()
            prev_jieqi = lunar.getPrevJieQi()

            # 获取更多传统信息
            return {
                "current_jieqi": current_jieqi,
                "next_jieqi": next_jieqi.toString() if next_jieqi else None,
                "prev_jieqi": prev_jieqi.toString() if prev_jieqi else None,
                "lunar_festivals": lunar.getFestivals(),
                "solar_festivals": solar.getFestivals(),
                "twenty_eight_star": lunar.getXiu(),
                "day_position": {
                    "xi": lunar.getPositionXi(),
                    "yang_gui": lunar.getPositionYangGui(),
                    "yin_gui": lunar.getPositionYinGui(),
                    "fu": lunar.getPositionFu(),
                    "cai": lunar.getPositionCai(),
                },
                "pengzu_taboo": {
                    "gan": lunar.getPengZuGan(),
                    "zhi": lunar.getPengZuZhi(),
                },
                "day_suitable": lunar.getDayYi(),
                "day_avoid": lunar.getDayJi(),
                "day_clash": lunar.getDayChongDesc(),
            }
        except Exception as e:
            print(f"获取详细农历信息失败: {e}")
            return {}


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
