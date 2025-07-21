"""
八字婚姻分析扩展模块 专门用于婚姻时机、配偶信息等分析.
"""

from typing import Any, Dict, List

from .professional_data import TAOHUA_XING, WUXING, get_ten_gods_relation


class MarriageAnalyzer:
    """
    婚姻分析器.
    """

    def __init__(self):
        self.marriage_gods = {
            "male": ["正财", "偏财"],  # 男命妻星
            "female": ["正官", "七杀"],  # 女命夫星
        }

    def analyze_marriage_timing(
        self, eight_char_data: Dict[str, Any], gender: int
    ) -> Dict[str, Any]:
        """
        分析婚姻时机.
        """
        result = {
            "marriage_star_analysis": self._analyze_marriage_star(
                eight_char_data, gender
            ),
            "marriage_age_range": self._predict_marriage_age(eight_char_data, gender),
            "favorable_years": self._get_favorable_marriage_years(
                eight_char_data, gender
            ),
            "marriage_obstacles": self._analyze_marriage_obstacles(eight_char_data),
            "spouse_characteristics": self._analyze_spouse_features(
                eight_char_data, gender
            ),
            "marriage_quality": self._evaluate_marriage_quality(
                eight_char_data, gender
            ),
        }
        return result

    def _analyze_marriage_star(
        self, eight_char_data: Dict[str, Any], gender: int
    ) -> Dict[str, Any]:
        """
        分析夫妻星.
        """
        from .professional_data import ZHI_CANG_GAN, get_changsheng_state

        gender_key = "male" if gender == 1 else "female"
        target_gods = self.marriage_gods[gender_key]

        # 统一获取天干数据格式
        year_gan = self._extract_gan_from_pillar(eight_char_data.get("year", {}))
        month_gan = self._extract_gan_from_pillar(eight_char_data.get("month", {}))
        day_gan = self._extract_gan_from_pillar(eight_char_data.get("day", {}))
        hour_gan = self._extract_gan_from_pillar(eight_char_data.get("hour", {}))

        marriage_stars = []

        # 检查天干夫妻星
        for position, gan in [
            ("年干", year_gan),
            ("月干", month_gan),
            ("时干", hour_gan),
        ]:
            if gan and gan != day_gan:
                ten_god = get_ten_gods_relation(day_gan, gan)
                if ten_god in target_gods:
                    # 获取更详细的分析
                    star_info = {
                        "position": position,
                        "star": ten_god,
                        "strength": self._evaluate_star_strength(position),
                        "element": self._get_gan_element(gan),
                        "quality": self._evaluate_star_quality(position, ten_god),
                        "seasonal_strength": self._get_seasonal_strength(
                            gan, month_gan
                        ),
                    }
                    marriage_stars.append(star_info)

        # 分析地支藏干中的夫妻星
        for position, pillar in [
            ("年支", eight_char_data.get("year", {})),
            ("月支", eight_char_data.get("month", {})),
            ("时支", eight_char_data.get("hour", {})),
        ]:
            zhi_name = self._extract_zhi_from_pillar(pillar)
            if zhi_name and zhi_name in ZHI_CANG_GAN:
                cang_gan_data = ZHI_CANG_GAN[zhi_name]

                for hidden_gan, strength in cang_gan_data.items():
                    if hidden_gan != day_gan:
                        ten_god = get_ten_gods_relation(day_gan, hidden_gan)
                        if ten_god in target_gods:
                            # 根据藏干强度判断类型
                            gan_type = self._determine_canggan_type(strength)

                            star_info = {
                                "position": position,
                                "star": ten_god,
                                "strength": self._get_hidden_strength(gan_type),
                                "element": self._get_gan_element(hidden_gan),
                                "type": f"藏干{gan_type}",
                                "quality": self._evaluate_hidden_star_quality(
                                    zhi_name, hidden_gan, strength
                                ),
                                "changsheng_state": get_changsheng_state(
                                    day_gan, zhi_name
                                ),
                            }
                            marriage_stars.append(star_info)

        # 分析夫妻星的综合情况
        star_analysis = self._comprehensive_star_analysis(
            marriage_stars, day_gan, gender
        )

        return {
            "has_marriage_star": len(marriage_stars) > 0,
            "marriage_stars": marriage_stars,
            "star_count": len(marriage_stars),
            "star_strength": star_analysis["strength"],
            "star_quality": star_analysis["quality"],
            "star_distribution": star_analysis["distribution"],
            "marriage_potential": star_analysis["potential"],
            "improvement_suggestions": star_analysis["suggestions"],
        }

    def _predict_marriage_age(
        self, eight_char_data: Dict[str, Any], gender: int
    ) -> Dict[str, Any]:
        """
        预测结婚年龄段.
        """
        from .professional_data import (
            CHANGSHENG_TWELVE,
            GAN_WUXING,
            HUAGAI_XING,
            TIANYI_GUIREN,
            WUXING_RELATIONS,
            ZHI_WUXING,
        )

        day_gan = self._extract_gan_from_pillar(eight_char_data.get("day", {}))
        day_zhi = self._extract_zhi_from_pillar(eight_char_data.get("day", {}))
        self._extract_gan_from_pillar(eight_char_data.get("month", {}))
        month_zhi = self._extract_zhi_from_pillar(eight_char_data.get("month", {}))
        year_zhi = self._extract_zhi_from_pillar(eight_char_data.get("year", {}))
        hour_zhi = self._extract_zhi_from_pillar(eight_char_data.get("hour", {}))

        # 专业分析因子
        factors = {
            "early_signs": [],
            "late_signs": [],
            "score": 50,  # 基础分数
            "detailed_analysis": [],
        }

        # 1. 日支分析（最重要）
        if day_zhi in "子午卯酉":
            factors["early_signs"].append("日支桃花星")
            factors["score"] -= 12
            factors["detailed_analysis"].append("日支桃花星利于早期感情发展")

        if day_zhi in "寅申巳亥":
            factors["early_signs"].append("日支驿马星")
            factors["score"] -= 8
            factors["detailed_analysis"].append("日支驿马星主变动，感情来得快")

        if day_zhi in "辰戌丑未":
            factors["late_signs"].append("日支四库")
            factors["score"] += 15
            factors["detailed_analysis"].append("日支四库主稳重，感情发展较慢")

        # 2. 夫妻星分析
        marriage_star_analysis = self._analyze_marriage_star(eight_char_data, gender)
        star_strength = marriage_star_analysis.get("star_strength", "弱")
        marriage_star_analysis.get("star_count", 0)

        if star_strength == "很强":
            factors["score"] -= 8
            factors["early_signs"].append("夫妻星很强")
            factors["detailed_analysis"].append("夫妻星很强，感情运势佳")
        elif star_strength == "强":
            factors["score"] -= 5
            factors["early_signs"].append("夫妻星强")
        elif star_strength == "弱" or star_strength == "无星":
            factors["score"] += 10
            factors["late_signs"].append("夫妻星弱")
            factors["detailed_analysis"].append("夫妻星偏弱，需要耐心等待")

        # 3. 长生十二宫分析
        if day_gan in CHANGSHENG_TWELVE:
            changsheng_state = CHANGSHENG_TWELVE[day_gan].get(day_zhi, "")
            if changsheng_state in ["长生", "帝旺", "建禄"]:
                factors["score"] -= 6
                factors["early_signs"].append(f"日主在日支{changsheng_state}")
                factors["detailed_analysis"].append(
                    f"日主{changsheng_state}，自信有魅力"
                )
            elif changsheng_state in ["墓", "死", "绝"]:
                factors["score"] += 8
                factors["late_signs"].append(f"日主在日支{changsheng_state}")
                factors["detailed_analysis"].append(
                    f"日主{changsheng_state}，需要时间积累"
                )

        # 4. 神煞分析
        all_zhi = [year_zhi, month_zhi, day_zhi, hour_zhi]

        # 天乙贵人
        tianyi_zhi = TIANYI_GUIREN.get(day_gan, "")
        if tianyi_zhi and any(zhi in tianyi_zhi for zhi in all_zhi):
            factors["score"] -= 5
            factors["early_signs"].append("有天乙贵人")
            factors["detailed_analysis"].append("天乙贵人助力，贵人相助觅良缘")

        # 华盖星
        huagai_zhi = HUAGAI_XING.get(day_zhi, "")
        if huagai_zhi and any(zhi == huagai_zhi for zhi in all_zhi):
            factors["score"] += 12
            factors["late_signs"].append("有华盖星")
            factors["detailed_analysis"].append("华盖星主孤独，感情发展较慢")

        # 5. 五行平衡分析
        day_element = GAN_WUXING.get(day_gan, "")
        month_element = ZHI_WUXING.get(month_zhi, "")

        if day_element and month_element:
            relation = WUXING_RELATIONS.get((month_element, day_element), "")
            if relation == "↓":  # 月令生我
                factors["score"] -= 6
                factors["early_signs"].append("月令生日主")
                factors["detailed_analysis"].append("月令生日主，得时得势利感情")
            elif relation == "←":  # 月令克我
                factors["score"] += 8
                factors["late_signs"].append("月令克日主")
                factors["detailed_analysis"].append("月令克日主，需要时间建立自信")

        # 6. 配偶宫分析
        spouse_palace_analysis = self._analyze_spouse_palace(day_zhi, month_zhi)
        factors["score"] += spouse_palace_analysis["age_adjustment"]
        factors["detailed_analysis"].extend(spouse_palace_analysis["analysis"])

        # 7. 性别差异分析
        if gender == 1:  # 男性
            factors["score"] -= 3  # 男性通常结婚稍晚
            factors["detailed_analysis"].append("男性统计上结婚年龄稍晚")
        else:  # 女性
            factors["score"] += 2
            factors["detailed_analysis"].append("女性感情发展相对较早")

        # 8. 综合评估
        final_score = max(20, min(80, factors["score"]))

        # 根据分数预测年龄段
        if final_score <= 30:
            age_prediction = "很早"
            age_range = "18-24岁"
            tendency = "感情运势极佳，早期即可遇到良缘"
        elif final_score <= 40:
            age_prediction = "较早"
            age_range = "22-27岁"
            tendency = "感情发展顺利，适合早婚"
        elif final_score <= 60:
            age_prediction = "适中"
            age_range = "25-30岁"
            tendency = "感情发展正常，适合适龄结婚"
        elif final_score <= 70:
            age_prediction = "较晚"
            age_range = "28-35岁"
            tendency = "感情发展较慢，需要耐心等待"
        else:
            age_prediction = "很晚"
            age_range = "30-40岁"
            tendency = "感情发展困难，需要主动创造机会"

        return {
            "prediction": age_prediction,
            "age_range": age_range,
            "tendency": tendency,
            "score": final_score,
            "early_factors": factors["early_signs"],
            "late_factors": factors["late_signs"],
            "detailed_analysis": factors["detailed_analysis"],
            "analysis_basis": f"基于日柱{day_gan}{day_zhi}的专业分析",
            "confidence": self._calculate_prediction_confidence(factors),
        }

    def _get_favorable_marriage_years(
        self, eight_char_data: Dict[str, Any], gender: int
    ) -> List[str]:
        """
        获取有利的结婚年份 - 使用完整的地支关系分析.
        """
        from .professional_data import YIMA_XING, ZHI_RELATIONS, ZHI_SAN_HE, ZHI_SAN_HUI

        day_zhi = eight_char_data.get("day", {}).get("earth_branch", {}).get("name", "")
        month_zhi = (
            eight_char_data.get("month", {}).get("earth_branch", {}).get("name", "")
        )
        year_zhi = (
            eight_char_data.get("year", {}).get("earth_branch", {}).get("name", "")
        )

        favorable_branches = []

        # 1. 六合关系 - 最有利
        if day_zhi in ZHI_RELATIONS:
            liuhe_zhi = ZHI_RELATIONS[day_zhi].get("六", "")
            if liuhe_zhi:
                favorable_branches.append(
                    {"zhi": liuhe_zhi, "reason": "日支六合", "priority": "高"}
                )

        # 2. 三合关系 - 非常有利
        for sanhe_combo, element in ZHI_SAN_HE.items():
            if day_zhi in sanhe_combo:
                # 找到三合中的其他地支
                for zhi in sanhe_combo:
                    if zhi != day_zhi:
                        favorable_branches.append(
                            {"zhi": zhi, "reason": f"三合{element}局", "priority": "高"}
                        )

        # 3. 三会方 - 有利
        for sanhui_combo, element in ZHI_SAN_HUI.items():
            if day_zhi in sanhui_combo:
                for zhi in sanhui_combo:
                    if zhi != day_zhi:
                        favorable_branches.append(
                            {"zhi": zhi, "reason": f"三会{element}方", "priority": "中"}
                        )

        # 4. 桃花星 - 感情运佳
        taohua_zhi = TAOHUA_XING.get(day_zhi, "")
        if taohua_zhi:
            favorable_branches.append(
                {"zhi": taohua_zhi, "reason": "桃花星", "priority": "中"}
            )

        # 5. 驿马星 - 变动之年，适合结婚
        yima_zhi = YIMA_XING.get(day_zhi, "")
        if yima_zhi:
            favorable_branches.append(
                {"zhi": yima_zhi, "reason": "驿马星", "priority": "中"}
            )

        # 6. 月支相关的有利年份
        if month_zhi in ZHI_RELATIONS:
            month_liuhe = ZHI_RELATIONS[month_zhi].get("六", "")
            if month_liuhe:
                favorable_branches.append(
                    {"zhi": month_liuhe, "reason": "月支六合", "priority": "中"}
                )

        # 7. 年支相关的有利年份
        if year_zhi in ZHI_RELATIONS:
            year_liuhe = ZHI_RELATIONS[year_zhi].get("六", "")
            if year_liuhe:
                favorable_branches.append(
                    {"zhi": year_liuhe, "reason": "年支六合", "priority": "低"}
                )

        # 去重并按优先级排序
        unique_branches = {}
        for branch in favorable_branches:
            zhi = branch["zhi"]
            if zhi not in unique_branches or branch["priority"] == "高":
                unique_branches[zhi] = branch

        # 按优先级排序
        priority_order = {"高": 1, "中": 2, "低": 3}
        sorted_branches = sorted(
            unique_branches.values(), key=lambda x: priority_order[x["priority"]]
        )

        return [f"{branch['zhi']}年({branch['reason']})" for branch in sorted_branches]

    def _analyze_spouse_palace(self, day_zhi: str, month_zhi: str) -> Dict[str, Any]:
        """
        分析配偶宫（日支）对婚姻时机的影响.
        """
        from .professional_data import WUXING_RELATIONS, ZHI_WUXING

        palace_analysis = {"age_adjustment": 0, "analysis": []}

        # 日支五行分析
        day_element = ZHI_WUXING.get(day_zhi, "")
        month_element = ZHI_WUXING.get(month_zhi, "")

        if day_element and month_element:
            relation = WUXING_RELATIONS.get((month_element, day_element), "")
            if relation == "↓":  # 月令生配偶宫
                palace_analysis["age_adjustment"] -= 4
                palace_analysis["analysis"].append("月令生配偶宫，配偶宫得力")
            elif relation == "←":  # 月令克配偶宫
                palace_analysis["age_adjustment"] += 6
                palace_analysis["analysis"].append("月令克配偶宫，配偶宫受制")

        # 配偶宫特性分析
        palace_characteristics = {
            "子": {"adjustment": -2, "desc": "子水配偶宫灵活，感情发展较快"},
            "丑": {"adjustment": 4, "desc": "丑土配偶宫稳重，感情发展较慢"},
            "寅": {"adjustment": -3, "desc": "寅木配偶宫积极，感情发展较快"},
            "卯": {"adjustment": 0, "desc": "卯木配偶宫温和，感情发展正常"},
            "辰": {"adjustment": 5, "desc": "辰土配偶宫保守，感情发展较慢"},
            "巳": {"adjustment": -1, "desc": "巳火配偶宫智慧，感情发展适中"},
            "午": {"adjustment": -4, "desc": "午火配偶宫热情，感情发展较快"},
            "未": {"adjustment": 3, "desc": "未土配偶宫温和，感情发展稍慢"},
            "申": {"adjustment": -2, "desc": "申金配偶宫变通，感情发展较快"},
            "酉": {"adjustment": 1, "desc": "酉金配偶宫完美，感情发展适中"},
            "戌": {"adjustment": 6, "desc": "戌土配偶宫忠诚，感情发展较慢"},
            "亥": {"adjustment": -1, "desc": "亥水配偶宫包容，感情发展适中"},
        }

        if day_zhi in palace_characteristics:
            char = palace_characteristics[day_zhi]
            palace_analysis["age_adjustment"] += char["adjustment"]
            palace_analysis["analysis"].append(char["desc"])

        return palace_analysis

    def _calculate_prediction_confidence(self, factors: Dict[str, Any]) -> str:
        """
        计算预测可信度.
        """
        early_count = len(factors["early_signs"])
        late_count = len(factors["late_signs"])
        analysis_count = len(factors["detailed_analysis"])

        # 计算因子一致性
        if early_count >= 4 and late_count <= 1:
            consistency = "高"
        elif late_count >= 4 and early_count <= 1:
            consistency = "高"
        elif abs(early_count - late_count) <= 1:
            consistency = "中"
        else:
            consistency = "低"

        # 计算分析深度
        if analysis_count >= 8:
            depth = "深入"
        elif analysis_count >= 5:
            depth = "充分"
        else:
            depth = "一般"

        # 综合评估
        if consistency == "高" and depth == "深入":
            return "很高"
        elif consistency == "高" or depth == "深入":
            return "高"
        elif consistency == "中" and depth == "充分":
            return "较高"
        elif consistency == "中" or depth == "充分":
            return "中等"
        else:
            return "较低"

    def _analyze_marriage_obstacles(self, eight_char_data: Dict[str, Any]) -> List[str]:
        """
        分析婚姻阻碍.
        """
        from .professional_data import HUAGAI_XING, analyze_zhi_combinations

        obstacles = []

        # 提取四柱地支
        zhi_list = [
            eight_char_data.get("year", {}).get("earth_branch", {}).get("name", ""),
            eight_char_data.get("month", {}).get("earth_branch", {}).get("name", ""),
            eight_char_data.get("day", {}).get("earth_branch", {}).get("name", ""),
            eight_char_data.get("hour", {}).get("earth_branch", {}).get("name", ""),
        ]

        # 获取日支（配偶宫）
        day_zhi = zhi_list[2] if len(zhi_list) > 2 else ""

        # 使用专业函数分析地支组合
        zhi_relations = analyze_zhi_combinations(zhi_list)

        # 1. 分析相冲 - 最严重的阻碍
        if zhi_relations.get("chong"):
            for chong_desc in zhi_relations["chong"]:
                if day_zhi in chong_desc:
                    obstacles.append(f"配偶宫{chong_desc}，严重影响婚姻稳定")
                else:
                    obstacles.append(f"{chong_desc}，影响婚姻和谐")

        # 2. 分析相刑 - 第二严重
        if zhi_relations.get("xing"):
            for xing_desc in zhi_relations["xing"]:
                if day_zhi in xing_desc:
                    obstacles.append(f"配偶宫{xing_desc}，夫妻关系紧张")
                else:
                    obstacles.append(f"{xing_desc}，家庭关系复杂")

        # 3. 分析相害 - 第三严重
        if zhi_relations.get("hai"):
            for hai_desc in zhi_relations["hai"]:
                if day_zhi in hai_desc:
                    obstacles.append(f"配偶宫{hai_desc}，感情易受伤害")
                else:
                    obstacles.append(f"{hai_desc}，感情发展有阻碍")

        # 4. 华盖星分析 - 孤独倾向
        day_gan = self._extract_gan_from_pillar(eight_char_data.get("day", {}))
        if day_gan:
            huagai_zhi = HUAGAI_XING.get(day_gan, "")
            if huagai_zhi and huagai_zhi in zhi_list:
                obstacles.append("命带华盖星，性格孤独，不易接近")

        # 5. 配偶宫特殊情况分析
        if day_zhi:
            spouse_palace_obstacles = self._analyze_spouse_palace_obstacles(
                day_zhi, zhi_list
            )
            obstacles.extend(spouse_palace_obstacles)

        # 6. 夫妻星受克分析
        marriage_star_analysis = self._analyze_marriage_star(
            eight_char_data, 1
        )  # 先用男性分析
        if marriage_star_analysis.get("star_count", 0) == 0:
            obstacles.append("八字无明显夫妻星，感情发展困难")
        elif marriage_star_analysis.get("star_strength") in ["弱", "无星"]:
            obstacles.append("夫妻星偏弱，感情运势不佳")

        # 7. 五行失衡分析
        wuxing_obstacles = self._analyze_wuxing_marriage_obstacles(eight_char_data)
        obstacles.extend(wuxing_obstacles)

        # 去重并限制数量
        unique_obstacles = list(set(obstacles))
        return unique_obstacles[:8]  # 最多返回8个主要阻碍

    def _analyze_spouse_palace_obstacles(
        self, day_zhi: str, zhi_list: List[str]
    ) -> List[str]:
        """
        分析配偶宫的特殊阻碍.
        """
        obstacles = []

        # 配偶宫特殊情况
        palace_issues = {
            "辰": "辰土配偶宫保守，感情发展缓慢",
            "戌": "戌土配偶宫固执，容易感情争执",
            "丑": "丑土配偶宫内向，不善表达感情",
            "未": "未土配偶宫敏感，容易情绪波动",
        }

        if day_zhi in palace_issues:
            obstacles.append(palace_issues[day_zhi])

        # 配偶宫重复出现
        if zhi_list.count(day_zhi) > 1:
            obstacles.append(f"配偶宫{day_zhi}重复出现，感情模式固化")

        return obstacles

    def _analyze_wuxing_marriage_obstacles(
        self, eight_char_data: Dict[str, Any]
    ) -> List[str]:
        """
        分析五行失衡对婚姻的影响.
        """
        from .professional_data import GAN_WUXING, ZHI_WUXING

        obstacles = []

        # 收集所有五行
        wuxing_count = {element: 0 for element in WUXING}

        # 天干五行
        for pillar_key in ["year", "month", "day", "hour"]:
            gan = self._extract_gan_from_pillar(eight_char_data.get(pillar_key, {}))
            if gan:
                element = GAN_WUXING.get(gan, "")
                if element in wuxing_count:
                    wuxing_count[element] += 1

        # 地支五行
        for pillar_key in ["year", "month", "day", "hour"]:
            zhi = self._extract_zhi_from_pillar(eight_char_data.get(pillar_key, {}))
            if zhi:
                element = ZHI_WUXING.get(zhi, "")
                if element in wuxing_count:
                    wuxing_count[element] += 1

        # 分析五行失衡
        total_count = sum(wuxing_count.values())
        if total_count > 0:
            # 检查过旺或过弱的五行
            for element, count in wuxing_count.items():
                ratio = count / total_count
                if ratio >= 0.5:  # 超过50%
                    obstacles.append(f"{element}行过旺，性格偏执影响感情")
                elif ratio == 0:  # 完全缺失
                    element_effects = {
                        "金": "缺金，不够果断，错失良机",
                        "木": "缺木，不够主动，感情被动",
                        "水": "缺水，不够灵活，感情僵化",
                        "火": "缺火，不够热情，感情冷淡",
                        "土": "缺土，不够稳重，感情多变",
                    }
                    if element in element_effects:
                        obstacles.append(element_effects[element])

        return obstacles

    def _analyze_spouse_features(
        self, eight_char_data: Dict[str, Any], gender: int
    ) -> Dict[str, str]:
        """
        分析配偶特征 - 使用五行生克分析.
        """

        day_zhi = eight_char_data.get("day", {}).get("earth_branch", {}).get("name", "")
        day_gan = self._extract_gan_from_pillar(eight_char_data.get("day", {}))
        month_zhi = self._extract_zhi_from_pillar(eight_char_data.get("month", {}))

        # 基础配偶特征
        basic_features = self._get_basic_spouse_features(day_zhi)

        # 五行生克影响
        wuxing_influence = self._analyze_wuxing_spouse_influence(day_zhi, month_zhi)

        # 藏干影响
        canggan_influence = self._analyze_canggan_spouse_influence(day_zhi, day_gan)

        # 夫妻星影响
        star_influence = self._analyze_marriage_star_spouse_influence(
            eight_char_data, gender
        )

        # 综合分析
        return {
            "personality": self._synthesize_personality(
                basic_features["personality"],
                wuxing_influence["personality"],
                star_influence["personality"],
            ),
            "appearance": self._synthesize_appearance(
                basic_features["appearance"],
                wuxing_influence["appearance"],
                canggan_influence["appearance"],
            ),
            "career_tendency": self._synthesize_career(
                basic_features["career"],
                wuxing_influence["career"],
                star_influence["career"],
            ),
            "relationship_mode": star_influence["relationship_mode"],
            "compatibility": self._evaluate_compatibility(day_gan, day_zhi, month_zhi),
            "improvement_suggestions": self._generate_spouse_improvement_suggestions(
                day_zhi, wuxing_influence, star_influence
            ),
        }

    def _get_basic_spouse_features(self, day_zhi: str) -> Dict[str, str]:
        """
        获取基础配偶特征.
        """
        spouse_features = {
            "子": {
                "personality": "聪明机智，善于理财，性格活泼，适应能力强",
                "appearance": "中等身材，面容清秀，眼神灵动",
                "career": "技术、金融、贸易、IT行业",
            },
            "丑": {
                "personality": "踏实稳重，任劳任怨，略显内向，责任心强",
                "appearance": "身材厚实，面相朴实，气质沉稳",
                "career": "农业、建筑、制造、服务业",
            },
            "寅": {
                "personality": "热情开朗，有领导能力，略急躁，正义感强",
                "appearance": "身材高大，面容方正，气质阳刚",
                "career": "管理、政府、教育、体育行业",
            },
            "卯": {
                "personality": "温和善良，有艺术气质，追求完美，敏感细腻",
                "appearance": "身材修长，面容秀美，气质优雅",
                "career": "文艺、设计、美容、文化行业",
            },
            "辰": {
                "personality": "成熟稳重，有责任心，较为保守，城府较深",
                "appearance": "身材中等，面相敦厚，气质稳重",
                "career": "土木、房地产、仓储、物流业",
            },
            "巳": {
                "personality": "聪明睿智，善于交际，有神秘感，思维敏捷",
                "appearance": "身材适中，面容精致，气质神秘",
                "career": "文化、咨询、通信、心理行业",
            },
            "午": {
                "personality": "热情奔放，积极进取，略显急躁，表现欲强",
                "appearance": "身材匀称，面色红润，气质热情",
                "career": "能源、体育、娱乐、销售业",
            },
            "未": {
                "personality": "温柔体贴，心思细腻，有包容心，略显敏感",
                "appearance": "身材中等，面容温和，气质柔美",
                "career": "服务、餐饮、园艺、护理业",
            },
            "申": {
                "personality": "机智灵活，善于变通，略显多变，创新能力强",
                "appearance": "身材灵活，面容机敏，气质活泼",
                "career": "制造、交通、科技、创新业",
            },
            "酉": {
                "personality": "端庄优雅，注重形象，有洁癖倾向，完美主义",
                "appearance": "身材小巧，面容端正，气质精致",
                "career": "金融、珠宝、服装、美容业",
            },
            "戌": {
                "personality": "忠诚可靠，有正义感，略显固执，保护欲强",
                "appearance": "身材结实，面相方正，气质正直",
                "career": "军警、保安、建筑、法律业",
            },
            "亥": {
                "personality": "善良纯朴，富有同情心，较为感性，包容性强",
                "appearance": "身材丰满，面容和善，气质温和",
                "career": "水利、渔业、慈善、医疗业",
            },
        }

        return spouse_features.get(
            day_zhi,
            {
                "personality": "性格温和，为人正直",
                "appearance": "相貌端正，气质良好",
                "career": "各行各业均有可能",
            },
        )

    def _analyze_wuxing_spouse_influence(
        self, day_zhi: str, month_zhi: str
    ) -> Dict[str, str]:
        """
        分析五行对配偶特征的影响.
        """
        from .professional_data import WUXING_RELATIONS, ZHI_WUXING

        day_element = ZHI_WUXING.get(day_zhi, "")
        month_element = ZHI_WUXING.get(month_zhi, "")

        influence = {"personality": "", "appearance": "", "career": ""}

        if day_element and month_element:
            relation = WUXING_RELATIONS.get((month_element, day_element), "")

            if relation == "↓":  # 月令生配偶宫
                influence["personality"] = "得月令生助，性格积极乐观"
                influence["appearance"] = "气色良好，精神饱满"
                influence["career"] = "事业运势不错，发展顺利"
            elif relation == "←":  # 月令克配偶宫
                influence["personality"] = "受月令制约，性格较为内敛"
                influence["appearance"] = "略显疲惫，需要休息"
                influence["career"] = "事业发展有阻碍，需要努力"
            elif relation == "=":  # 同类五行
                influence["personality"] = "性格稳定，不易变化"
                influence["appearance"] = "外表协调，气质稳定"
                influence["career"] = "事业发展稳步前进"

        return influence

    def _analyze_canggan_spouse_influence(
        self, day_zhi: str, day_gan: str
    ) -> Dict[str, str]:
        """
        分析藏干对配偶特征的影响.
        """
        from .professional_data import GAN_WUXING, ZHI_CANG_GAN

        influence = {"appearance": ""}

        if day_zhi in ZHI_CANG_GAN:
            canggan_data = ZHI_CANG_GAN[day_zhi]

            # 分析主气影响
            main_gans = [gan for gan, strength in canggan_data.items() if strength >= 5]
            if main_gans:
                main_gan = main_gans[0]
                main_element = GAN_WUXING.get(main_gan, "")

                element_appearance = {
                    "金": "面容清秀，皮肤白皙，骨骼匀称",
                    "木": "身材修长，面容清秀，气质文雅",
                    "水": "面容圆润，皮肤光滑，眼神温和",
                    "火": "面色红润，精神饱满，气质热情",
                    "土": "面相敦厚，身材结实，气质稳重",
                }

                if main_element in element_appearance:
                    influence["appearance"] = element_appearance[main_element]

        return influence

    def _analyze_marriage_star_spouse_influence(
        self, eight_char_data: Dict[str, Any], gender: int
    ) -> Dict[str, str]:
        """
        分析夫妻星对配偶特征的影响.
        """
        star_analysis = self._analyze_marriage_star(eight_char_data, gender)

        influence = {"personality": "", "career": "", "relationship_mode": ""}

        if star_analysis["has_marriage_star"]:
            star_strength = star_analysis["star_strength"]
            star_analysis["star_quality"]

            # 根据夫妻星强度影响
            if star_strength in ["很强", "强"]:
                influence["personality"] = "性格鲜明，个性突出"
                influence["career"] = "事业能力强，有发展潜力"
                influence["relationship_mode"] = "感情浓烈，关系稳定"
            elif star_strength == "中":
                influence["personality"] = "性格平和，个性适中"
                influence["career"] = "事业发展平稳"
                influence["relationship_mode"] = "感情平和，关系和谐"
            else:
                influence["personality"] = "性格内敛，个性不够鲜明"
                influence["career"] = "事业发展需要时间"
                influence["relationship_mode"] = "感情发展较慢，需要培养"
        else:
            influence["personality"] = "性格难以捉摸，个性多变"
            influence["career"] = "事业方向不明确"
            influence["relationship_mode"] = "感情发展困难，需要耐心"

        return influence

    def _synthesize_personality(self, basic: str, wuxing: str, star: str) -> str:
        """
        综合分析性格特征.
        """
        result = basic
        if wuxing:
            result += f"，{wuxing}"
        if star:
            result += f"，{star}"
        return result

    def _synthesize_appearance(self, basic: str, wuxing: str, canggan: str) -> str:
        """
        综合分析外貌特征.
        """
        result = basic
        if canggan:
            result = canggan  # 藏干影响更直接
        if wuxing:
            result += f"，{wuxing}"
        return result

    def _synthesize_career(self, basic: str, wuxing: str, star: str) -> str:
        """
        综合分析职业倾向.
        """
        result = basic
        if star:
            result = f"{basic}，{star}"
        if wuxing:
            result += f"，{wuxing}"
        return result

    def _evaluate_compatibility(
        self, day_gan: str, day_zhi: str, month_zhi: str
    ) -> str:
        """
        评估配偶兼容性.
        """
        from .professional_data import ZHI_RELATIONS

        compatibility_score = 70  # 基础分数

        # 检查地支关系
        if day_zhi in ZHI_RELATIONS:
            relations = ZHI_RELATIONS[day_zhi]
            if month_zhi == relations.get("六", ""):
                compatibility_score += 20
                return "配偶兼容性极佳，天生一对"
            elif month_zhi in relations.get("合", ()):
                compatibility_score += 15
                return "配偶兼容性很好，相处和谐"
            elif month_zhi == relations.get("冲", ""):
                compatibility_score -= 30
                return "配偶兼容性较差，需要磨合"

        if compatibility_score >= 85:
            return "配偶兼容性优秀"
        elif compatibility_score >= 70:
            return "配偶兼容性良好"
        elif compatibility_score >= 50:
            return "配偶兼容性一般"
        else:
            return "配偶兼容性较差"

    def _generate_spouse_improvement_suggestions(
        self,
        day_zhi: str,
        wuxing_influence: Dict[str, str],
        star_influence: Dict[str, str],
    ) -> List[str]:
        """
        生成配偶关系改善建议.
        """
        suggestions = []

        # 根据配偶宫特性给建议
        zhi_suggestions = {
            "子": ["多沟通交流，避免误解", "给予足够的自由空间"],
            "丑": ["耐心等待，不要急于求成", "多给予关怀和理解"],
            "寅": ["避免争强好胜，学会妥协", "给予足够的发展空间"],
            "卯": ["创造浪漫氛围，增进感情", "尊重对方的审美和追求"],
            "辰": ["建立信任，避免猜疑", "给予安全感和稳定感"],
            "巳": ["保持神秘感，不要过于直接", "多进行智力交流"],
            "午": ["保持激情，避免感情冷淡", "给予充分的关注和赞美"],
            "未": ["多体贴关怀，温柔对待", "避免过于严厉的批评"],
            "申": ["保持新鲜感，避免单调", "给予变化和刺激"],
            "酉": ["注重形象，保持整洁", "避免粗糙和随意"],
            "戌": ["建立信任，保持忠诚", "给予安全感和归属感"],
            "亥": ["多给予关爱，避免伤害", "保持包容和理解"],
        }

        if day_zhi in zhi_suggestions:
            suggestions.extend(zhi_suggestions[day_zhi])

        # 根据五行影响给建议
        if "内敛" in wuxing_influence.get("personality", ""):
            suggestions.append("多鼓励对方表达，建立开放的沟通环境")

        # 根据夫妻星影响给建议
        if "发展较慢" in star_influence.get("relationship_mode", ""):
            suggestions.append("保持耐心，逐步培养感情")

        return suggestions[:4]  # 返回最多4个建议

    def _get_spouse_appearance(self, day_zhi: str) -> str:
        """
        根据日支推测配偶外貌.
        """
        appearance_map = {
            "子": "中等身材，面容清秀",
            "丑": "身材厚实，面相朴实",
            "寅": "身材高大，面容方正",
            "卯": "身材修长，面容秀美",
            "辰": "身材中等，面相敦厚",
            "巳": "身材适中，面容精致",
            "午": "身材匀称，面色红润",
            "未": "身材中等，面容温和",
            "申": "身材灵活，面容机敏",
            "酉": "身材小巧，面容端正",
            "戌": "身材结实，面相方正",
            "亥": "身材丰满，面容和善",
        }
        return appearance_map.get(day_zhi, "相貌端正")

    def _get_spouse_career(self, day_zhi: str) -> str:
        """
        根据日支推测配偶职业倾向.
        """
        career_map = {
            "子": "技术、金融、贸易相关",
            "丑": "农业、建筑、服务业",
            "寅": "管理、政府、教育行业",
            "卯": "文艺、设计、美容行业",
            "辰": "土木、房地产、仓储业",
            "巳": "文化、咨询、通信业",
            "午": "能源、体育、娱乐业",
            "未": "服务、餐饮、园艺业",
            "申": "制造、交通、科技业",
            "酉": "金融、珠宝、服装业",
            "戌": "军警、保安、建筑业",
            "亥": "水利、渔业、慈善业",
        }
        return career_map.get(day_zhi, "各行各业均有可能")

    def _evaluate_marriage_quality(
        self, eight_char_data: Dict[str, Any], gender: int
    ) -> Dict[str, Any]:
        """
        评估婚姻质量.
        """
        day_gan = eight_char_data.get("day", {}).get("heaven_stem", {}).get("name", "")
        day_zhi = eight_char_data.get("day", {}).get("earth_branch", {}).get("name", "")

        # 日柱组合分析婚姻质量
        good_combinations = [
            "甲子",
            "乙丑",
            "丙寅",
            "丁卯",
            "戊辰",
            "己巳",
            "庚午",
            "辛未",
            "壬申",
            "癸酉",
        ]

        day_pillar = day_gan + day_zhi
        quality_score = 75  # 基础分数

        if day_pillar in good_combinations:
            quality_score += 10

        return {
            "score": quality_score,
            "level": (
                "优秀"
                if quality_score >= 85
                else "良好" if quality_score >= 75 else "一般"
            ),
            "advice": self._get_marriage_advice(quality_score),
        }

    def _get_marriage_advice(self, score: int) -> str:
        """
        获取婚姻建议.
        """
        if score >= 85:
            return "婚姻运势良好，注重沟通交流，关系可长久稳定"
        elif score >= 75:
            return "婚姻基础稳固，需要双方共同努力维护感情"
        else:
            return "婚姻需要更多包容和理解，建议多沟通化解矛盾"

    def _evaluate_star_strength(self, position: str) -> str:
        """
        评估星神力量.
        """
        strength_map = {
            "年干": "强",
            "月干": "最强",
            "时干": "中",
            "年支": "中强",
            "月支": "强",
            "时支": "中",
        }
        return strength_map.get(position, "弱")

    def _extract_gan_from_pillar(self, pillar: Dict[str, Any]) -> str:
        """
        从柱中提取天干.
        """
        if "天干" in pillar:
            return pillar["天干"].get("天干", "")
        elif "heaven_stem" in pillar:
            return pillar["heaven_stem"].get("name", "")
        return ""

    def _extract_zhi_from_pillar(self, pillar: Dict[str, Any]) -> str:
        """
        从柱中提取地支.
        """
        if "地支" in pillar:
            return pillar["地支"].get("地支", "")
        elif "earth_branch" in pillar:
            return pillar["earth_branch"].get("name", "")
        return ""

    def _get_gan_element(self, gan: str) -> str:
        """
        获取天干五行.
        """
        from .professional_data import GAN_WUXING

        return GAN_WUXING.get(gan, "")

    def _analyze_hidden_marriage_stars(
        self, pillar: Dict[str, Any], day_gan: str, target_gods: List[str]
    ) -> List[Dict[str, Any]]:
        """
        分析地支藏干中的夫妻星.
        """
        hidden_stars = []

        if "地支" in pillar and "藏干" in pillar["地支"]:
            canggan = pillar["地支"]["藏干"]
            for gan_type, gan_info in canggan.items():
                if gan_info and "天干" in gan_info:
                    hidden_gan = gan_info["天干"]
                    ten_god = get_ten_gods_relation(day_gan, hidden_gan)
                    if ten_god in target_gods:
                        hidden_stars.append(
                            {
                                "star": ten_god,
                                "strength": self._get_hidden_strength(gan_type),
                                "element": self._get_gan_element(hidden_gan),
                                "type": f"藏干{gan_type}",
                            }
                        )

        return hidden_stars

    def _get_hidden_strength(self, gan_type: str) -> str:
        """
        获取藏干强度.
        """
        strength_map = {"主气": "强", "中气": "中", "余气": "弱"}
        return strength_map.get(gan_type, "弱")

    def _evaluate_marriage_star_quality(
        self, marriage_stars: List[Dict[str, Any]]
    ) -> str:
        """
        评估夫妻星质量.
        """
        if not marriage_stars:
            return "无星"

        strong_stars = sum(
            1 for star in marriage_stars if star["strength"] in ["最强", "强"]
        )
        total_stars = len(marriage_stars)

        if strong_stars >= 2:
            return "优秀"
        elif strong_stars == 1 and total_stars >= 2:
            return "良好"
        elif total_stars >= 1:
            return "一般"
        else:
            return "较弱"

    def _evaluate_star_quality(self, position: str, ten_god: str) -> str:
        """
        评估夫妻星质量.
        """
        # 根据位置和十神类型评估质量
        if position == "月干":
            return "优秀"  # 月干夫妻星最佳
        elif position == "年干":
            return "良好"  # 年干夫妻星次佳
        elif position == "时干":
            return "一般"  # 时干夫妻星一般
        else:
            return "可以"

    def _get_seasonal_strength(self, gan: str, month_gan: str) -> str:
        """
        获取季节性力量.
        """
        from .professional_data import GAN_WUXING, WUXING_RELATIONS

        gan_element = GAN_WUXING.get(gan, "")
        month_element = GAN_WUXING.get(month_gan, "")

        if not gan_element or not month_element:
            return "中等"

        # 检查五行关系
        relation = WUXING_RELATIONS.get((month_element, gan_element), "")
        if relation == "↓":  # 月令生我
            return "旺相"
        elif relation == "=":  # 同类
            return "得令"
        elif relation == "←":  # 月令克我
            return "失时"
        elif relation == "→":  # 我克月令
            return "耗泄"
        else:
            return "中等"

    def _determine_canggan_type(self, strength: int) -> str:
        """
        根据藏干强度确定类型.
        """
        if strength >= 5:
            return "主气"
        elif strength >= 2:
            return "中气"
        else:
            return "余气"

    def _evaluate_hidden_star_quality(
        self, zhi_name: str, hidden_gan: str, strength: int
    ) -> str:
        """
        评估藏干夫妻星质量.
        """
        if strength >= 5:
            return "优秀"
        elif strength >= 3:
            return "良好"
        elif strength >= 1:
            return "一般"
        else:
            return "较弱"

    def _comprehensive_star_analysis(
        self, marriage_stars: List[Dict[str, Any]], day_gan: str, gender: int
    ) -> Dict[str, Any]:
        """
        综合分析夫妻星情况.
        """
        if not marriage_stars:
            return {
                "strength": "无星",
                "quality": "无星",
                "distribution": "无夫妻星",
                "potential": "较弱",
                "suggestions": ["可通过大运流年补充夫妻星", "关注感情发展的时机"],
            }

        # 分析星的分布
        positions = [star["position"] for star in marriage_stars]
        star_types = [star["star"] for star in marriage_stars]

        # 计算综合强度
        strength_score = 0
        for star in marriage_stars:
            if star["strength"] == "最强":
                strength_score += 5
            elif star["strength"] == "强":
                strength_score += 3
            elif star["strength"] == "中":
                strength_score += 2
            else:
                strength_score += 1

        # 判断强度等级
        if strength_score >= 8:
            strength_level = "很强"
        elif strength_score >= 5:
            strength_level = "强"
        elif strength_score >= 3:
            strength_level = "中"
        else:
            strength_level = "弱"

        # 分析质量
        quality_scores = []
        for star in marriage_stars:
            quality = star.get("quality", "一般")
            if quality == "优秀":
                quality_scores.append(4)
            elif quality == "良好":
                quality_scores.append(3)
            elif quality == "一般":
                quality_scores.append(2)
            else:
                quality_scores.append(1)

        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 1
        if avg_quality >= 3.5:
            quality_level = "优秀"
        elif avg_quality >= 2.5:
            quality_level = "良好"
        elif avg_quality >= 1.5:
            quality_level = "一般"
        else:
            quality_level = "较差"

        # 分析分布情况
        distribution_desc = (
            f"共{len(marriage_stars)}个夫妻星，分布在{len(set(positions))}个位置"
        )

        # 婚姻潜力评估
        if strength_score >= 6 and avg_quality >= 3:
            potential = "很好"
        elif strength_score >= 4 and avg_quality >= 2:
            potential = "良好"
        elif strength_score >= 2:
            potential = "一般"
        else:
            potential = "较弱"

        # 改进建议
        suggestions = []
        if strength_score < 3:
            suggestions.append("夫妻星偏弱，可通过大运流年补充")
        if avg_quality < 2:
            suggestions.append("夫妻星质量不高，需要耐心等待合适时机")
        if "月干" not in positions and "月支" not in positions:
            suggestions.append("月柱无夫妻星，感情发展可能较慢")
        if len(set(star_types)) == 1:
            suggestions.append("夫妻星类型单一，感情模式相对固定")

        return {
            "strength": strength_level,
            "quality": quality_level,
            "distribution": distribution_desc,
            "potential": potential,
            "suggestions": (
                suggestions if suggestions else ["夫妻星配置良好，感情发展顺利"]
            ),
        }


# 全局分析器实例
_marriage_analyzer = None


def get_marriage_analyzer():
    """
    获取婚姻分析器单例.
    """
    global _marriage_analyzer
    if _marriage_analyzer is None:
        _marriage_analyzer = MarriageAnalyzer()
    return _marriage_analyzer
