"""
八字命理分析核心算法.
"""

from typing import Any, Dict, List, Optional

from .engine import get_bazi_engine
from .models import BaziAnalysis, EightChar, LunarTime, SolarTime
from .professional_analyzer import get_professional_analyzer


class BaziCalculator:
    """
    八字分析计算器.
    """

    def __init__(self):
        self.engine = get_bazi_engine()
        self.professional_analyzer = get_professional_analyzer()

    def build_hide_heaven_object(
        self, heaven_stem: Optional[str], day_master: str
    ) -> Optional[Dict[str, str]]:
        """
        构建藏干对象.
        """
        if not heaven_stem:
            return None

        return {
            "天干": heaven_stem,
            "十神": self._get_ten_star(day_master, heaven_stem),
        }

    def _get_ten_star(self, day_master: str, other_stem: str) -> str:
        """
        计算十神关系.
        """
        return self.professional_analyzer.get_ten_gods_analysis(day_master, other_stem)

    def build_sixty_cycle_object(
        self, sixty_cycle, day_master: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        构建干支对象.
        """
        heaven_stem = sixty_cycle.get_heaven_stem()
        earth_branch = sixty_cycle.get_earth_branch()

        if not day_master:
            day_master = heaven_stem.name

        return {
            "天干": {
                "天干": heaven_stem.name,
                "五行": heaven_stem.element,
                "阴阳": "阳" if heaven_stem.yin_yang == 1 else "阴",
                "十神": (
                    None
                    if day_master == heaven_stem.name
                    else self._get_ten_star(day_master, heaven_stem.name)
                ),
            },
            "地支": {
                "地支": earth_branch.name,
                "五行": earth_branch.element,
                "阴阳": "阳" if earth_branch.yin_yang == 1 else "阴",
                "藏干": {
                    "主气": self.build_hide_heaven_object(
                        earth_branch.hide_heaven_main, day_master
                    ),
                    "中气": self.build_hide_heaven_object(
                        earth_branch.hide_heaven_middle, day_master
                    ),
                    "余气": self.build_hide_heaven_object(
                        earth_branch.hide_heaven_residual, day_master
                    ),
                },
            },
            "纳音": sixty_cycle.sound,
            "旬": sixty_cycle.ten,
            "空亡": "".join(sixty_cycle.extra_earth_branches),
            "星运": self._get_terrain(day_master, earth_branch.name),
            "自坐": self._get_terrain(heaven_stem.name, earth_branch.name),
        }

    def _get_terrain(self, stem: str, branch: str) -> str:
        """
        计算十二长生.
        """
        from .professional_data import get_changsheng_state

        return get_changsheng_state(stem, branch)

    def build_gods_object(
        self, eight_char: EightChar, gender: int
    ) -> Dict[str, List[str]]:
        """
        构建神煞对象.
        """
        from .professional_data import get_shensha

        # 获取八字干支
        eight_char.year.heaven_stem.name
        eight_char.month.heaven_stem.name
        day_gan = eight_char.day.heaven_stem.name
        eight_char.hour.heaven_stem.name

        year_zhi = eight_char.year.earth_branch.name
        month_zhi = eight_char.month.earth_branch.name
        day_zhi = eight_char.day.earth_branch.name
        hour_zhi = eight_char.hour.earth_branch.name

        # 各柱神煞
        result = {"年柱": [], "月柱": [], "日柱": [], "时柱": []}

        # 天乙贵人（以日干为主）
        tianyi = get_shensha(day_gan, "tianyi")
        if tianyi:
            for zhi in [year_zhi, month_zhi, day_zhi, hour_zhi]:
                if zhi in tianyi:
                    if zhi == year_zhi:
                        result["年柱"].append("天乙贵人")
                    if zhi == month_zhi:
                        result["月柱"].append("天乙贵人")
                    if zhi == day_zhi:
                        result["日柱"].append("天乙贵人")
                    if zhi == hour_zhi:
                        result["时柱"].append("天乙贵人")

        # 文昌贵人（以日干为主）
        wenchang = get_shensha(day_gan, "wenchang")
        if wenchang:
            for zhi in [year_zhi, month_zhi, day_zhi, hour_zhi]:
                if zhi == wenchang:
                    if zhi == year_zhi:
                        result["年柱"].append("文昌贵人")
                    if zhi == month_zhi:
                        result["月柱"].append("文昌贵人")
                    if zhi == day_zhi:
                        result["日柱"].append("文昌贵人")
                    if zhi == hour_zhi:
                        result["时柱"].append("文昌贵人")

        # 驿马星（以日支为主）
        yima = get_shensha(day_zhi, "yima")
        if yima:
            for zhi in [year_zhi, month_zhi, day_zhi, hour_zhi]:
                if zhi == yima:
                    if zhi == year_zhi:
                        result["年柱"].append("驿马星")
                    if zhi == month_zhi:
                        result["月柱"].append("驿马星")
                    if zhi == day_zhi:
                        result["日柱"].append("驿马星")
                    if zhi == hour_zhi:
                        result["时柱"].append("驿马星")

        # 桃花星（以日支为主）
        taohua = get_shensha(day_zhi, "taohua")
        if taohua:
            for zhi in [year_zhi, month_zhi, day_zhi, hour_zhi]:
                if zhi == taohua:
                    if zhi == year_zhi:
                        result["年柱"].append("桃花星")
                    if zhi == month_zhi:
                        result["月柱"].append("桃花星")
                    if zhi == day_zhi:
                        result["日柱"].append("桃花星")
                    if zhi == hour_zhi:
                        result["时柱"].append("桃花星")

        # 华盖星（以日支为主）
        huagai = get_shensha(day_zhi, "huagai")
        if huagai:
            for zhi in [year_zhi, month_zhi, day_zhi, hour_zhi]:
                if zhi == huagai:
                    if zhi == year_zhi:
                        result["年柱"].append("华盖星")
                    if zhi == month_zhi:
                        result["月柱"].append("华盖星")
                    if zhi == day_zhi:
                        result["日柱"].append("华盖星")
                    if zhi == hour_zhi:
                        result["时柱"].append("华盖星")

        return result

    def build_decade_fortune_object(
        self, solar_time: SolarTime, eight_char: EightChar, gender: int, day_master: str
    ) -> Dict[str, Any]:
        """
        构建大运对象.
        """
        # 获取年柱阴阳性
        year_yin_yang = eight_char.year.heaven_stem.yin_yang
        month_gan = eight_char.month.heaven_stem.name
        month_zhi = eight_char.month.earth_branch.name

        fortune_list = []

        # 使用专业起运年龄计算
        start_age = self._calculate_start_age(solar_time, eight_char, gender)

        for i in range(10):  # 计算10步大运
            age_start = start_age + i * 10
            age_end = age_start + 9
            year_start = solar_time.year + age_start
            year_end = solar_time.year + age_end

            # 使用专业算法计算大运干支
            fortune_gz = self._calculate_fortune_ganzhi(
                month_gan, month_zhi, i + 1, gender, year_yin_yang
            )

            # 分离大运天干和地支
            fortune_gan = fortune_gz[0]
            fortune_zhi = fortune_gz[1]

            # 计算地支藏干的十神关系
            from .professional_data import ZHI_CANG_GAN

            zhi_ten_gods = []
            zhi_canggan = []

            if fortune_zhi in ZHI_CANG_GAN:
                canggan_data = ZHI_CANG_GAN[fortune_zhi]
                for hidden_gan, strength in canggan_data.items():
                    ten_god = self._get_ten_star(day_master, hidden_gan)
                    zhi_ten_gods.append(f"{ten_god}({hidden_gan})")
                    zhi_canggan.append(f"{hidden_gan}({strength})")

            fortune_list.append(
                {
                    "干支": fortune_gz,
                    "开始年份": year_start,
                    "结束": year_end,
                    "天干十神": self._get_ten_star(day_master, fortune_gan),
                    "地支十神": (
                        zhi_ten_gods if zhi_ten_gods else [f"地支{fortune_zhi}"]
                    ),
                    "地支藏干": zhi_canggan if zhi_canggan else [fortune_zhi],
                    "开始年龄": age_start,
                    "结束年龄": age_end,
                }
            )

        return {
            "起运日期": f"{solar_time.year + start_age}-{solar_time.month}-{solar_time.day}",
            "起运年龄": start_age,
            "大运": fortune_list,
        }

    def _calculate_fortune_ganzhi(
        self, month_gan: str, month_zhi: str, step: int, gender: int, year_yin_yang: int
    ) -> str:
        """
        计算大运干支.
        """
        from .professional_data import GAN, ZHI

        # 确定大运方向：阳男阴女顺行，阴男阳女逆行
        if (gender == 1 and year_yin_yang == 1) or (
            gender == 0 and year_yin_yang == -1
        ):
            # 顺行
            direction = 1
        else:
            # 逆行
            direction = -1

        # 从月柱开始计算大运
        month_gan_idx = GAN.index(month_gan)
        month_zhi_idx = ZHI.index(month_zhi)

        # 计算当前大运的干支索引
        fortune_gan_idx = (month_gan_idx + step * direction) % 10
        fortune_zhi_idx = (month_zhi_idx + step * direction) % 12

        return GAN[fortune_gan_idx] + ZHI[fortune_zhi_idx]

    def build_bazi(
        self,
        solar_datetime: Optional[str] = None,
        lunar_datetime: Optional[str] = None,
        gender: int = 1,
        eight_char_provider_sect: int = 2,
    ) -> BaziAnalysis:
        """
        构建八字分析.
        """

        if not solar_datetime and not lunar_datetime:
            raise ValueError("solarDatetime和lunarDatetime必须传且只传其中一个")

        if solar_datetime:
            solar_time = self.engine.parse_solar_time(solar_datetime)
            lunar_time = self.engine.solar_to_lunar(solar_time)
        else:
            # 处理农历时间
            lunar_dt = self._parse_lunar_datetime(lunar_datetime)
            lunar_time = lunar_dt
            solar_time = self._lunar_to_solar(lunar_dt)

        # 构建八字
        eight_char = self.engine.build_eight_char(solar_time)
        day_master = eight_char.day.heaven_stem.name

        # 生肖应该使用农历年份计算，而不是八字年柱（因为立春和春节时间不同）
        zodiac = self._get_zodiac_by_lunar_year(solar_time)

        # 构建分析结果
        analysis = BaziAnalysis(
            gender=["女", "男"][gender],
            solar_time=self.engine.format_solar_time(solar_time),
            lunar_time=str(lunar_time),
            bazi=str(eight_char),
            zodiac=zodiac,
            day_master=day_master,
            year_pillar=self.build_sixty_cycle_object(eight_char.year, day_master),
            month_pillar=self.build_sixty_cycle_object(eight_char.month, day_master),
            day_pillar=self.build_sixty_cycle_object(eight_char.day),
            hour_pillar=self.build_sixty_cycle_object(eight_char.hour, day_master),
            fetal_origin=self._calculate_fetal_origin(eight_char),
            fetal_breath=self._calculate_fetal_breath(eight_char),
            own_sign=self._calculate_own_sign(eight_char),
            body_sign=self._calculate_body_sign(eight_char),
            gods=self.build_gods_object(eight_char, gender),
            fortune=self.build_decade_fortune_object(
                solar_time, eight_char, gender, day_master
            ),
            relations=self._build_relations_object(eight_char),
        )

        # 使用专业分析器增强结果
        try:
            # 直接使用八字数据进行专业分析
            eight_char_dict = eight_char.to_dict()
            detailed_analysis = self.professional_analyzer.analyze_eight_char_structure(
                eight_char_dict
            )
            detailed_text = self.professional_analyzer.get_detailed_fortune_analysis(
                eight_char_dict
            )

            # 将专业分析结果添加到返回对象
            analysis._professional_analysis = detailed_analysis
            analysis._detailed_fortune_text = detailed_text
        except Exception as e:
            # 如果专业分析失败，记录错误但不影响基础功能
            analysis._professional_analysis = {"error": f"专业分析失败: {e}"}
            analysis._detailed_fortune_text = f"专业分析模块暂时不可用: {e}"

        return analysis

    def _parse_lunar_datetime(self, lunar_datetime: str) -> LunarTime:
        """
        解析农历时间字符串 - 支持多种格式.
        """
        import re
        from datetime import datetime

        # 支持中文农历格式：农历2024年三月初八 [时间]
        chinese_match = re.match(
            r"农历(\d{4})年(\S+)月(\S+)(?:\s+(.+))?", lunar_datetime
        )
        if chinese_match:
            year = int(chinese_match.group(1))
            month_str = chinese_match.group(2)
            day_str = chinese_match.group(3)
            time_str = chinese_match.group(4)  # 可能的时间部分

            # 转换中文月份和日期
            month = self._chinese_month_to_number(month_str)
            day = self._chinese_day_to_number(day_str)

            # 解析时间部分
            hour, minute, second = self._parse_time_part(time_str)

            return LunarTime(
                year=year,
                month=month,
                day=day,
                hour=hour,
                minute=minute,
                second=second,
            )

        # 支持标准格式
        try:
            # 尝试ISO格式
            dt = datetime.fromisoformat(lunar_datetime)
        except ValueError:
            # 尝试其他常见格式
            formats = [
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
                    dt = datetime.strptime(lunar_datetime, fmt)
                    break
                except ValueError:
                    continue

            if dt is None:
                raise ValueError(f"无法解析农历时间格式: {lunar_datetime}")

        return LunarTime(
            year=dt.year,
            month=dt.month,
            day=dt.day,
            hour=dt.hour,
            minute=dt.minute,
            second=dt.second,
        )

    def _lunar_to_solar(self, lunar_time: LunarTime) -> SolarTime:
        """
        农历转公历.
        """
        try:
            # 使用lunar-python进行真正的农历公历转换
            from lunar_python import Lunar

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

    def _calculate_fetal_origin(self, eight_char: EightChar) -> str:
        """
        计算胎元.
        """
        from .professional_data import GAN, ZHI

        # 胎元 = 月柱天干进一位 + 月柱地支进三位
        month_gan = eight_char.month.heaven_stem.name
        month_zhi = eight_char.month.earth_branch.name

        # 天干进一位
        gan_idx = GAN.index(month_gan)
        fetal_gan = GAN[(gan_idx + 1) % 10]

        # 地支进三位
        zhi_idx = ZHI.index(month_zhi)
        fetal_zhi = ZHI[(zhi_idx + 3) % 12]

        return f"{fetal_gan}{fetal_zhi}"

    def _calculate_fetal_breath(self, eight_char: EightChar) -> str:
        """
        计算胎息.
        """
        from .professional_data import GAN, ZHI

        # 胎息 = 日柱干支阴阳相配
        day_gan = eight_char.day.heaven_stem.name
        day_zhi = eight_char.day.earth_branch.name

        # 取对应阴阳干支
        gan_idx = GAN.index(day_gan)
        zhi_idx = ZHI.index(day_zhi)

        # 阴阳转换（奇偶相转）
        breath_gan = GAN[(gan_idx + 1) % 10 if gan_idx % 2 == 0 else (gan_idx - 1) % 10]
        breath_zhi = ZHI[(zhi_idx + 6) % 12]  # 对冲地支

        return f"{breath_gan}{breath_zhi}"

    def _calculate_own_sign(self, eight_char: EightChar) -> str:
        """
        计算命宫.
        """
        from .professional_data import GAN, ZHI

        # 命宫计算：寅宫起正月，顺数至本生月，再从卯时起逆数本生时，所得即命宫
        month_zhi = eight_char.month.earth_branch.name
        hour_zhi = eight_char.hour.earth_branch.name

        month_idx = ZHI.index(month_zhi)
        hour_idx = ZHI.index(hour_zhi)

        # 寅宫起正月，顺数到本生月
        ming_gong_num = (month_idx - 2) % 12  # 寅=0，卯=1...

        # 从卯时起逆数本生时
        hour_offset = (hour_idx - 3) % 12  # 卯=0，辰=1...
        ming_gong_num = (ming_gong_num - hour_offset) % 12

        ming_gong_zhi = ZHI[(ming_gong_num + 2) % 12]  # 转换回实际地支

        # 配上相应天干（简化：取子年对应的天干）
        ming_gong_gan = GAN[ming_gong_num % 10]

        return f"{ming_gong_gan}{ming_gong_zhi}"

    def _calculate_body_sign(self, eight_char: EightChar) -> str:
        """
        计算身宫.
        """
        from .professional_data import GAN, ZHI

        # 身宫计算：从月支顺数到时支
        month_zhi = eight_char.month.earth_branch.name
        hour_zhi = eight_char.hour.earth_branch.name

        month_idx = ZHI.index(month_zhi)
        hour_idx = ZHI.index(hour_zhi)

        # 从月支顺数到时支的地支数
        shen_gong_idx = (month_idx + hour_idx) % 12
        shen_gong_zhi = ZHI[shen_gong_idx]

        # 配上相应天干
        shen_gong_gan = GAN[shen_gong_idx % 10]

        return f"{shen_gong_gan}{shen_gong_zhi}"

    def _build_relations_object(self, eight_char: EightChar) -> Dict[str, Any]:
        """
        构建刑冲合会关系.
        """
        from .professional_data import analyze_zhi_combinations

        # 提取四柱地支
        zhi_list = [
            eight_char.year.earth_branch.name,
            eight_char.month.earth_branch.name,
            eight_char.day.earth_branch.name,
            eight_char.hour.earth_branch.name,
        ]

        # 使用专业函数分析地支关系
        relations = analyze_zhi_combinations(zhi_list)

        return {
            "三合": relations.get("sanhe", []),
            "六合": relations.get("liuhe", []),
            "三会": relations.get("sanhui", []),
            "相冲": relations.get("chong", []),
            "相刑": relations.get("xing", []),
            "相害": relations.get("hai", []),
        }

    def get_solar_times(self, bazi: str) -> List[str]:
        """
        根据八字获取可能的公历时间.
        """
        pillars = bazi.split(" ")
        if len(pillars) != 4:
            raise ValueError("八字格式错误")

        year_pillar, month_pillar, day_pillar, hour_pillar = pillars

        # 解析八字柱
        if (
            len(year_pillar) != 2
            or len(month_pillar) != 2
            or len(day_pillar) != 2
            or len(hour_pillar) != 2
        ):
            raise ValueError("八字格式错误，每柱应为两个字符")

        year_gan, year_zhi = year_pillar[0], year_pillar[1]
        month_gan, month_zhi = month_pillar[0], month_pillar[1]
        day_gan, day_zhi = day_pillar[0], day_pillar[1]
        hour_gan, hour_zhi = hour_pillar[0], hour_pillar[1]

        result_times = []

        # 扩大搜索范围：1900-2100年，并优化搜索策略
        for year in range(1900, 2100):
            try:
                # 尝试匹配年柱
                if self._match_year_pillar(year, year_gan, year_zhi):
                    # 遍历月份
                    for month in range(1, 13):
                        if self._match_month_pillar(year, month, month_gan, month_zhi):
                            # 遍历日期，使用更精确的日期范围
                            import calendar

                            max_day = calendar.monthrange(year, month)[1]

                            for day in range(1, max_day + 1):
                                try:
                                    if self._match_day_pillar(
                                        year, month, day, day_gan, day_zhi
                                    ):
                                        # 遍历时辰，使用每个时辰的中心点
                                        for hour in [
                                            0,
                                            2,
                                            4,
                                            6,
                                            8,
                                            10,
                                            12,
                                            14,
                                            16,
                                            18,
                                            20,
                                            22,
                                        ]:  # 12个时辰的中心点
                                            if self._match_hour_pillar(
                                                hour,
                                                hour_gan,
                                                hour_zhi,
                                                year,
                                                month,
                                                day,
                                            ):
                                                solar_time = f"{year}-{month:02d}-{day:02d} {hour:02d}:00:00"
                                                result_times.append(solar_time)

                                                # 适当增加返回数量限制
                                                if len(result_times) >= 20:
                                                    return result_times
                                except ValueError:
                                    continue  # 无效日期跳过
            except Exception:
                continue

        return result_times[:20]  # 返回前20个匹配结果

    def _calculate_start_age(
        self, solar_time: SolarTime, eight_char: EightChar, gender: int
    ) -> int:
        """
        计算起运年龄.
        """
        from lunar_python import Solar

        from .professional_data import GAN_YINYANG

        # 获取年柱干支阴阳
        year_gan = eight_char.year.heaven_stem.name
        year_gan_yinyang = GAN_YINYANG.get(year_gan, 1)

        try:
            # 创建出生时间的Solar对象
            birth_solar = Solar.fromYmdHms(
                solar_time.year,
                solar_time.month,
                solar_time.day,
                solar_time.hour,
                solar_time.minute,
                solar_time.second,
            )

            # 起运规则：阳男阴女顺行，阴男阳女逆行
            if (gender == 1 and year_gan_yinyang == 1) or (
                gender == 0 and year_gan_yinyang == -1
            ):
                # 顺行：计算出生到下一个节气的天数
                lunar = birth_solar.getLunar()
                next_jieqi = lunar.getNextJieQi()

                if next_jieqi:
                    # 获取下一个节气的公历时间
                    next_jieqi_solar = next_jieqi.getSolar()

                    # 计算天数差
                    days_diff = self._calculate_days_diff(birth_solar, next_jieqi_solar)

                    # 起运年龄 = 天数差 / 3（传统算法）
                    start_age = max(1, days_diff // 3)
                else:
                    start_age = 3  # 默认值
            else:
                # 逆行：计算上一个节气到出生的天数
                lunar = birth_solar.getLunar()
                prev_jieqi = lunar.getPrevJieQi()

                if prev_jieqi:
                    # 获取上一个节气的公历时间
                    prev_jieqi_solar = prev_jieqi.getSolar()

                    # 计算天数差
                    days_diff = self._calculate_days_diff(prev_jieqi_solar, birth_solar)

                    # 起运年龄 = 天数差 / 3（传统算法）
                    start_age = max(1, days_diff // 3)
                else:
                    start_age = 5  # 默认值

            # 限制起运年龄在合理范围内
            return max(1, min(start_age, 10))

        except Exception:
            # 如果节气计算失败，使用简化算法
            if (gender == 1 and year_gan_yinyang == 1) or (
                gender == 0 and year_gan_yinyang == -1
            ):
                base_age = 3
            else:
                base_age = 5

            # 根据月份微调
            month_adjustment = {
                1: 0,
                2: 1,
                3: 0,
                4: 1,
                5: 0,
                6: 1,
                7: 0,
                8: 1,
                9: 0,
                10: 1,
                11: 0,
                12: 1,
            }

            final_age = base_age + month_adjustment.get(solar_time.month, 0)
            return max(1, min(final_age, 8))

    def _parse_time_part(self, time_str: str) -> tuple:
        """
        解析时间部分，返回(hour, minute, second)
        """
        if not time_str:
            return (0, 0, 0)

        time_str = time_str.strip()

        # 支持时辰格式：子时、丑时、寅时等
        shichen_map = {
            "子时": 0,
            "子": 0,
            "丑时": 1,
            "丑": 1,
            "寅时": 3,
            "寅": 3,
            "卯时": 5,
            "卯": 5,
            "辰时": 7,
            "辰": 7,
            "巳时": 9,
            "巳": 9,
            "午时": 11,
            "午": 11,
            "未时": 13,
            "未": 13,
            "申时": 15,
            "申": 15,
            "酉时": 17,
            "酉": 17,
            "戌时": 19,
            "戌": 19,
            "亥时": 21,
            "亥": 21,
        }

        if time_str in shichen_map:
            return (shichen_map[time_str], 0, 0)

        # 支持数字时间格式：10时、10:30等
        import re

        # 匹配 "10时30分20秒" 格式
        chinese_time_match = re.match(r"(\d+)时(?:(\d+)分)?(?:(\d+)秒)?", time_str)
        if chinese_time_match:
            hour = int(chinese_time_match.group(1))
            minute = int(chinese_time_match.group(2) or 0)
            second = int(chinese_time_match.group(3) or 0)
            return (hour, minute, second)

        # 匹配 "10:30:20" 或 "10:30" 格式
        colon_time_match = re.match(r"(\d+):(\d+)(?::(\d+))?", time_str)
        if colon_time_match:
            hour = int(colon_time_match.group(1))
            minute = int(colon_time_match.group(2))
            second = int(colon_time_match.group(3) or 0)
            return (hour, minute, second)

        # 纯数字时间（小时）
        if time_str.isdigit():
            hour = int(time_str)
            return (hour, 0, 0)

        # 默认返回0时
        return (0, 0, 0)

    def _chinese_month_to_number(self, month_str: str) -> int:
        """
        转换中文月份为数字.
        """
        month_map = {
            "正": 1,
            "一": 1,
            "二": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
            "十": 10,
            "冬": 11,
            "腊": 12,
        }
        return month_map.get(month_str, 1)

    def _chinese_day_to_number(self, day_str: str) -> int:
        """
        转换中文日期为数字.
        """
        # 数字映射表
        chinese_numbers = {
            "一": 1,
            "二": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
            "十": 10,
            "廿": 20,
            "卅": 30,
        }

        if "初" in day_str:
            day_num = day_str.replace("初", "")
            if day_num in chinese_numbers:
                return chinese_numbers[day_num]
            else:
                return int(day_num) if day_num.isdigit() else 1
        elif "十" in day_str:
            if day_str == "十":
                return 10
            elif day_str.startswith("十"):
                remaining = day_str[1:]
                return 10 + chinese_numbers.get(
                    remaining, int(remaining) if remaining.isdigit() else 0
                )
            elif day_str.endswith("十"):
                prefix = day_str[:-1]
                return (
                    chinese_numbers.get(prefix, int(prefix) if prefix.isdigit() else 1)
                    * 10
                )
        elif "廿" in day_str:
            remaining = day_str.replace("廿", "")
            if remaining in chinese_numbers:
                return 20 + chinese_numbers[remaining]
            else:
                return 20 + (int(remaining) if remaining.isdigit() else 0)
        elif "卅" in day_str:
            return 30
        else:
            # 尝试直接转换数字
            if day_str in chinese_numbers:
                return chinese_numbers[day_str]
            try:
                return int(day_str)
            except ValueError:
                return 1

    def _calculate_days_diff(self, solar1, solar2) -> int:
        """
        计算两个Solar对象之间的天数差.
        """
        try:
            from datetime import datetime

            dt1 = datetime(solar1.getYear(), solar1.getMonth(), solar1.getDay())
            dt2 = datetime(solar2.getYear(), solar2.getMonth(), solar2.getDay())

            return abs((dt2 - dt1).days)
        except Exception:
            return 3  # 默认值

    def _match_year_pillar(self, year: int, gan: str, zhi: str) -> bool:
        """匹配年柱 - 修复版本，考虑立春节气"""
        try:
            from lunar_python import Solar

            # 年柱以立春为界，需要检查立春前后的年柱
            # 检查年初（立春前）
            solar_start = Solar.fromYmdHms(year, 1, 1, 0, 0, 0)
            lunar_start = solar_start.getLunar()
            bazi_start = lunar_start.getEightChar()

            # 检查年中（立春后）
            solar_mid = Solar.fromYmdHms(year, 6, 1, 0, 0, 0)
            lunar_mid = solar_mid.getLunar()
            bazi_mid = lunar_mid.getEightChar()

            # 检查年末
            solar_end = Solar.fromYmdHms(year, 12, 31, 23, 59, 59)
            lunar_end = solar_end.getLunar()
            bazi_end = lunar_end.getEightChar()

            # 如果年中任何一个时间点的年柱匹配，就认为匹配
            year_gans = [
                bazi_start.getYearGan(),
                bazi_mid.getYearGan(),
                bazi_end.getYearGan(),
            ]
            year_zhis = [
                bazi_start.getYearZhi(),
                bazi_mid.getYearZhi(),
                bazi_end.getYearZhi(),
            ]

            for i in range(len(year_gans)):
                if year_gans[i] == gan and year_zhis[i] == zhi:
                    return True

            return False
        except Exception:
            return False

    def _match_month_pillar(self, year: int, month: int, gan: str, zhi: str) -> bool:
        """匹配月柱 - 修复版本，考虑节气边界"""
        try:
            from lunar_python import Solar

            # 月柱以节气为界，检查月中几个时间点
            # 月初、月中、月末的月柱可能不同，需要都检查
            test_days = [1, 8, 15, 22, 28]  # 检查多个日期

            month_pillars = set()
            for day in test_days:
                try:
                    # 确保日期有效
                    import calendar

                    max_day = calendar.monthrange(year, month)[1]
                    if day > max_day:
                        day = max_day

                    solar = Solar.fromYmdHms(year, month, day, 12, 0, 0)
                    lunar = solar.getLunar()
                    bazi = lunar.getEightChar()

                    month_gan = bazi.getMonthGan()
                    month_zhi = bazi.getMonthZhi()
                    month_pillars.add(f"{month_gan}{month_zhi}")
                except Exception:
                    continue

            # 如果月中任何一天的月柱匹配，就认为匹配
            target_pillar = f"{gan}{zhi}"
            return target_pillar in month_pillars

        except Exception:
            return False

    def _match_day_pillar(
        self, year: int, month: int, day: int, gan: str, zhi: str
    ) -> bool:
        """
        匹配日柱.
        """
        try:
            from lunar_python import Solar

            solar = Solar.fromYmdHms(year, month, day, 0, 0, 0)
            lunar = solar.getLunar()
            bazi = lunar.getEightChar()

            day_gan = bazi.getDayGan()
            day_zhi = bazi.getDayZhi()

            return day_gan == gan and day_zhi == zhi
        except Exception:
            return False

    def _match_hour_pillar(
        self,
        hour: int,
        gan: str,
        zhi: str,
        year: int = None,
        month: int = None,
        day: int = None,
    ) -> bool:
        """匹配时柱 - 修复版本，使用实际日期"""
        try:
            from lunar_python import Solar

            # 使用实际日期或默认日期配合时辰
            use_year = year if year else 2024
            use_month = month if month else 1
            use_day = day if day else 1

            solar = Solar.fromYmdHms(use_year, use_month, use_day, hour, 0, 0)
            lunar = solar.getLunar()
            bazi = lunar.getEightChar()

            hour_gan = bazi.getTimeGan()
            hour_zhi = bazi.getTimeZhi()

            return hour_gan == gan and hour_zhi == zhi
        except Exception:
            return False

    def _get_zodiac_by_lunar_year(self, solar_time: SolarTime) -> str:
        """
        根据农历年份获取生肖（以春节为界，不是立春）
        """
        try:
            from lunar_python import Solar

            solar = Solar.fromYmdHms(
                solar_time.year,
                solar_time.month,
                solar_time.day,
                solar_time.hour,
                solar_time.minute,
                solar_time.second,
            )
            lunar = solar.getLunar()

            # 使用lunar-python直接获取农历生肖（以春节为界）
            return lunar.getYearShengXiao()
        except Exception as e:
            # 如果失败，使用八字年柱的生肖作为备选
            print(f"获取农历生肖失败，使用八字年柱生肖: {e}")
            eight_char = self.engine.build_eight_char(solar_time)
            return eight_char.year.earth_branch.zodiac


# 全局计算器实例
_bazi_calculator = None


def get_bazi_calculator() -> BaziCalculator:
    """
    获取八字计算器单例.
    """
    global _bazi_calculator
    if _bazi_calculator is None:
        _bazi_calculator = BaziCalculator()
    return _bazi_calculator
