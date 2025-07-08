"""
八字婚姻分析扩展模块 专门用于婚姻时机、配偶信息等分析.
"""

from typing import Any, Dict, List

from .professional_data import TAOHUA_XING, get_ten_gods_relation


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
        """分析夫妻星 - 使用专业数据"""
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
                    marriage_stars.append(
                        {
                            "position": position,
                            "star": ten_god,
                            "strength": self._evaluate_star_strength(position),
                            "element": self._get_gan_element(gan),
                        }
                    )

        # 分析地支藏干中的夫妻星
        for position, pillar in [
            ("年支", eight_char_data.get("year", {})),
            ("月支", eight_char_data.get("month", {})),
            ("时支", eight_char_data.get("hour", {})),
        ]:
            hidden_stars = self._analyze_hidden_marriage_stars(
                pillar, day_gan, target_gods
            )
            if hidden_stars:
                marriage_stars.extend(
                    [{**star, "position": position} for star in hidden_stars]
                )

        return {
            "has_marriage_star": len(marriage_stars) > 0,
            "marriage_stars": marriage_stars,
            "star_strength": (
                "强"
                if len(marriage_stars) >= 2
                else "中" if len(marriage_stars) == 1 else "弱"
            ),
            "star_quality": self._evaluate_marriage_star_quality(marriage_stars),
        }

    def _predict_marriage_age(
        self, eight_char_data: Dict[str, Any], gender: int
    ) -> Dict[str, Any]:
        """预测结婚年龄段 - 使用专业算法"""
        day_gan = self._extract_gan_from_pillar(eight_char_data.get("day", {}))
        day_zhi = self._extract_zhi_from_pillar(eight_char_data.get("day", {}))

        # 专业分析因子
        factors = {"early_signs": [], "late_signs": [], "score": 50}  # 基础分数

        # 桃花星早婚倾向
        if day_zhi in "子午卯酉":
            factors["early_signs"].append("日支桃花星")
            factors["score"] -= 10

        # 驿马星早婚倾向
        if day_zhi in "寅申巳亥":
            factors["early_signs"].append("日支驿马星")
            factors["score"] -= 8

        # 四库晚婚倾向
        if day_zhi in "辰戌丑未":
            factors["late_signs"].append("日支四库")
            factors["score"] += 12

        # 分析夫妻星强弱
        marriage_star_analysis = self._analyze_marriage_star(eight_char_data, gender)
        if marriage_star_analysis["star_strength"] == "强":
            factors["score"] -= 5
        elif marriage_star_analysis["star_strength"] == "弱":
            factors["score"] += 8

        # 根据分数预测年龄段
        if factors["score"] < 35:
            age_prediction = "较早"
            age_range = "20-26岁"
        elif factors["score"] > 65:
            age_prediction = "较晚"
            age_range = "28-35岁"
        else:
            age_prediction = "中等"
            age_range = "25-30岁"

        return {
            "prediction": age_prediction,
            "age_range": age_range,
            "score": factors["score"],
            "early_factors": factors["early_signs"],
            "late_factors": factors["late_signs"],
            "analysis_basis": f"基于日柱{day_gan}{day_zhi}的专业分析",
        }

    def _get_favorable_marriage_years(
        self, eight_char_data: Dict[str, Any], gender: int
    ) -> List[str]:
        """
        获取有利的结婚年份.
        """
        # 简化版本 - 基于地支三合六合
        day_zhi = eight_char_data.get("day", {}).get("earth_branch", {}).get("name", "")

        # 六合地支对应的有利年份
        liuhe_map = {
            "子": "丑",
            "丑": "子",
            "寅": "亥",
            "亥": "寅",
            "卯": "戌",
            "戌": "卯",
            "辰": "酉",
            "酉": "辰",
            "巳": "申",
            "申": "巳",
            "午": "未",
            "未": "午",
        }

        favorable_branches = []
        if day_zhi in liuhe_map:
            favorable_branches.append(liuhe_map[day_zhi])

        # 桃花年
        taohua_zhi = TAOHUA_XING.get(day_zhi, "")
        if taohua_zhi:
            favorable_branches.append(taohua_zhi)

        return [f"{zhi}年" for zhi in favorable_branches]

    def _analyze_marriage_obstacles(self, eight_char_data: Dict[str, Any]) -> List[str]:
        """
        分析婚姻阻碍.
        """
        obstacles = []

        # 检查地支相冲
        zhi_list = [
            eight_char_data.get("year", {}).get("earth_branch", {}).get("name", ""),
            eight_char_data.get("month", {}).get("earth_branch", {}).get("name", ""),
            eight_char_data.get("day", {}).get("earth_branch", {}).get("name", ""),
            eight_char_data.get("hour", {}).get("earth_branch", {}).get("name", ""),
        ]

        # 检查冲克
        chong_pairs = [
            ("子", "午"),
            ("丑", "未"),
            ("寅", "申"),
            ("卯", "酉"),
            ("辰", "戌"),
            ("巳", "亥"),
        ]
        for i, zhi1 in enumerate(zhi_list):
            for j, zhi2 in enumerate(zhi_list[i + 1 :], i + 1):
                if (zhi1, zhi2) in chong_pairs or (zhi2, zhi1) in chong_pairs:
                    obstacles.append(f"地支相冲({zhi1}冲{zhi2})影响婚姻稳定")

        return obstacles

    def _analyze_spouse_features(
        self, eight_char_data: Dict[str, Any], gender: int
    ) -> Dict[str, str]:
        """
        分析配偶特征.
        """
        day_zhi = eight_char_data.get("day", {}).get("earth_branch", {}).get("name", "")

        # 配偶宫（日支）分析
        spouse_features = {
            "子": "聪明机智，善于理财，性格活泼",
            "丑": "踏实稳重，任劳任怨，略显内向",
            "寅": "热情开朗，有领导能力，略急躁",
            "卯": "温和善良，有艺术气质，追求完美",
            "辰": "成熟稳重，有责任心，较为保守",
            "巳": "聪明睿智，善于交际，有神秘感",
            "午": "热情奔放，积极进取，略显急躁",
            "未": "温柔体贴，心思细腻，有包容心",
            "申": "机智灵活，善于变通，略显多变",
            "酉": "端庄优雅，注重形象，有洁癖倾向",
            "戌": "忠诚可靠，有正义感，略显固执",
            "亥": "善良纯朴，富有同情心，较为感性",
        }

        return {
            "personality": spouse_features.get(day_zhi, "性格温和"),
            "appearance": self._get_spouse_appearance(day_zhi),
            "career_tendency": self._get_spouse_career(day_zhi),
        }

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
        """评估星神力量 - 专业版"""
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
