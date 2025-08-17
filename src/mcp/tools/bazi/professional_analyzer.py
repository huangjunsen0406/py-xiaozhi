"""
八字命理专业分析器 使用内置专业数据进行准确的传统命理分析.
"""

from typing import Any, Dict, List

from .professional_data import (
    GAN_WUXING,
    WUXING,
    WUXING_RELATIONS,
    ZHI_CANG_GAN,
    ZHI_WUXING,
    analyze_zhi_combinations,
    get_changsheng_state,
    get_nayin,
    get_shensha,
    get_ten_gods_relation,
)


class ProfessionalAnalyzer:
    """专业八字分析器 - 使用完整的传统命理数据"""

    def __init__(self):
        """
        初始化分析器.
        """

    def get_ten_gods_analysis(self, day_master: str, other_stem: str) -> str:
        """
        获取十神分析.
        """
        return get_ten_gods_relation(day_master, other_stem)

    def analyze_eight_char_structure(
        self, eight_char_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        全面分析八字结构.
        """
        year_gan = (
            eight_char_data.get("year", {}).get("heaven_stem", {}).get("name", "")
        )
        year_zhi = (
            eight_char_data.get("year", {}).get("earth_branch", {}).get("name", "")
        )
        month_gan = (
            eight_char_data.get("month", {}).get("heaven_stem", {}).get("name", "")
        )
        month_zhi = (
            eight_char_data.get("month", {}).get("earth_branch", {}).get("name", "")
        )
        day_gan = eight_char_data.get("day", {}).get("heaven_stem", {}).get("name", "")
        day_zhi = eight_char_data.get("day", {}).get("earth_branch", {}).get("name", "")
        hour_gan = (
            eight_char_data.get("hour", {}).get("heaven_stem", {}).get("name", "")
        )
        hour_zhi = (
            eight_char_data.get("hour", {}).get("earth_branch", {}).get("name", "")
        )

        # 基础信息
        gan_list = [year_gan, month_gan, day_gan, hour_gan]
        zhi_list = [year_zhi, month_zhi, day_zhi, hour_zhi]

        analysis = {
            "day_master": day_gan,
            "ten_gods": self._analyze_ten_gods(day_gan, gan_list, zhi_list),
            "nayin": self._analyze_nayin(gan_list, zhi_list),
            "changsheng": self._analyze_changsheng(day_gan, zhi_list),
            "zhi_relations": analyze_zhi_combinations(zhi_list),
            "wuxing_balance": self._analyze_wuxing_balance(gan_list, zhi_list),
            "shensha": self._analyze_shensha(gan_list, zhi_list),
            "strength": self._analyze_day_master_strength(day_gan, month_zhi, zhi_list),
            "useful_god": self._determine_useful_god(
                day_gan, month_zhi, gan_list, zhi_list
            ),
        }

        return analysis

    def _analyze_ten_gods(
        self, day_master: str, gan_list: List[str], zhi_list: List[str]
    ) -> Dict[str, List[str]]:
        """
        分析十神分布.
        """
        ten_gods = {
            "比肩": [],
            "劫财": [],
            "食神": [],
            "伤官": [],
            "偏财": [],
            "正财": [],
            "七杀": [],
            "正官": [],
            "偏印": [],
            "正印": [],
        }

        # 天干十神
        for i, gan in enumerate(gan_list):
            if gan == day_master:
                continue

            ten_god = get_ten_gods_relation(day_master, gan)
            pillar_names = ["年干", "月干", "日干", "时干"]
            if ten_god in ten_gods:
                ten_gods[ten_god].append(f"{pillar_names[i]}{gan}")

        # 地支藏干十神
        pillar_names = ["年支", "月支", "日支", "时支"]
        for i, zhi in enumerate(zhi_list):
            cang_gan = ZHI_CANG_GAN.get(zhi, {})
            for gan, strength in cang_gan.items():
                if gan == day_master:
                    continue

                ten_god = get_ten_gods_relation(day_master, gan)
                if ten_god in ten_gods:
                    ten_gods[ten_god].append(
                        f"{pillar_names[i]}{zhi}藏{gan}({strength})"
                    )

        return ten_gods

    def _analyze_nayin(self, gan_list: List[str], zhi_list: List[str]) -> List[str]:
        """
        分析纳音.
        """
        nayin_list = []
        pillar_names = ["年柱", "月柱", "日柱", "时柱"]

        for i, (gan, zhi) in enumerate(zip(gan_list, zhi_list)):
            nayin = get_nayin(gan, zhi)
            nayin_list.append(f"{pillar_names[i]}{gan}{zhi}：{nayin}")

        return nayin_list

    def _analyze_changsheng(self, day_master: str, zhi_list: List[str]) -> List[str]:
        """
        分析长生十二宫.
        """
        changsheng_list = []
        pillar_names = ["年支", "月支", "日支", "时支"]

        for i, zhi in enumerate(zhi_list):
            state = get_changsheng_state(day_master, zhi)
            changsheng_list.append(f"{pillar_names[i]}{zhi}：{state}")

        return changsheng_list

    def _analyze_wuxing_balance(
        self, gan_list: List[str], zhi_list: List[str]
    ) -> Dict[str, Any]:
        """
        分析五行平衡.
        """
        wuxing_count = {element: 0 for element in WUXING}

        # 天干五行
        for gan in gan_list:
            wuxing = GAN_WUXING.get(gan, "")
            if wuxing in wuxing_count:
                wuxing_count[wuxing] += 2  # 天干力量较强

        # 地支五行
        for zhi in zhi_list:
            wuxing = ZHI_WUXING.get(zhi, "")
            if wuxing in wuxing_count:
                wuxing_count[wuxing] += 1

            # 地支藏干
            cang_gan = ZHI_CANG_GAN.get(zhi, {})
            for gan, strength in cang_gan.items():
                wuxing = GAN_WUXING.get(gan, "")
                if wuxing in wuxing_count:
                    wuxing_count[wuxing] += strength / 10  # 藏干力量较弱

        # 找出最强和最弱的五行
        max_wuxing = max(wuxing_count, key=wuxing_count.get)
        min_wuxing = min(wuxing_count, key=wuxing_count.get)

        return {
            "distribution": wuxing_count,
            "strongest": max_wuxing,
            "weakest": min_wuxing,
            "balance_score": self._calculate_balance_score(wuxing_count),
        }

    def _calculate_balance_score(self, wuxing_count: Dict[str, float]) -> float:
        """
        计算五行平衡分数（0-100，100为完全平衡）
        """
        values = list(wuxing_count.values())
        if not values:
            return 0

        average = sum(values) / len(values)
        variance = sum((v - average) ** 2 for v in values) / len(values)
        # 转换为0-100分数，方差越小分数越高
        balance_score = max(0, 100 - variance * 10)
        return round(balance_score, 2)

    def _analyze_shensha(
        self, gan_list: List[str], zhi_list: List[str]
    ) -> Dict[str, List[str]]:
        """
        分析神煞 - 修复版本，正确区分以日干查和以日支查的神煞.
        """
        shensha = {
            "天乙贵人": [],
            "文昌贵人": [],
            "驿马星": [],
            "桃花星": [],
            "华盖星": [],
        }

        day_gan = gan_list[2] if len(gan_list) > 2 else ""
        day_zhi = zhi_list[2] if len(zhi_list) > 2 else ""
        pillar_names = ["年支", "月支", "日支", "时支"]

        # 以日干查的神煞
        day_gan_shensha = [
            ("tianyi", "天乙贵人"),
            ("wenchang", "文昌贵人"),
        ]

        for shensha_type, shensha_name in day_gan_shensha:
            shensha_zhi = get_shensha(day_gan, shensha_type)
            if shensha_zhi:
                for i, zhi in enumerate(zhi_list):
                    if zhi in shensha_zhi:
                        shensha[shensha_name].append(f"{pillar_names[i]}{zhi}")

        # 以日支查的神煞
        day_zhi_shensha = [
            ("yima", "驿马星"),
            ("taohua", "桃花星"),
            ("huagai", "华盖星"),
        ]

        for shensha_type, shensha_name in day_zhi_shensha:
            shensha_zhi = get_shensha(day_zhi, shensha_type)
            if shensha_zhi:
                for i, zhi in enumerate(zhi_list):
                    if zhi == shensha_zhi:  # 这些神煞返回的是单个地支
                        shensha[shensha_name].append(f"{pillar_names[i]}{zhi}")

        return shensha

    def _analyze_day_master_strength(
        self, day_master: str, month_zhi: str, zhi_list: List[str]
    ) -> Dict[str, Any]:
        """
        分析日主强弱.
        """
        # 基础月令力量
        month_element = ZHI_WUXING.get(month_zhi, "")
        day_element = GAN_WUXING.get(day_master, "")

        # 月令生克关系
        month_relation = WUXING_RELATIONS.get((day_element, month_element), "")

        # 计算得生得助
        same_element_count = 0
        help_element_count = 0

        for zhi in zhi_list:
            zhi_element = ZHI_WUXING.get(zhi, "")
            if zhi_element == day_element:
                same_element_count += 1
            elif WUXING_RELATIONS.get((zhi_element, day_element)) == "↓":  # 生我
                help_element_count += 1

        # 简单强弱判断
        strength_score = 0
        if month_relation == "↑":  # 我生月令
            strength_score -= 30
        elif month_relation == "↓":  # 月令生我
            strength_score += 30
        elif month_relation == "=":  # 同类
            strength_score += 20
        elif month_relation == "←":  # 月令克我
            strength_score -= 20
        elif month_relation == "→":  # 我克月令
            strength_score -= 10

        strength_score += same_element_count * 15
        strength_score += help_element_count * 10

        if strength_score >= 30:
            strength_level = "偏强"
        elif strength_score >= 10:
            strength_level = "中和"
        elif strength_score >= -10:
            strength_level = "偏弱"
        else:
            strength_level = "很弱"

        return {
            "level": strength_level,
            "score": strength_score,
            "month_relation": month_relation,
            "same_element_count": same_element_count,
            "help_element_count": help_element_count,
        }

    def _determine_useful_god(
        self, day_master: str, month_zhi: str, gan_list: List[str], zhi_list: List[str]
    ) -> Dict[str, Any]:
        """
        确定用神.
        """
        day_element = GAN_WUXING.get(day_master, "")
        strength_analysis = self._analyze_day_master_strength(
            day_master, month_zhi, zhi_list
        )

        useful_gods = []
        avoid_gods = []

        if strength_analysis["level"] in ["偏强", "很强"]:
            # 身强用克泄耗
            for element in WUXING:
                relation = WUXING_RELATIONS.get((day_element, element), "")
                if relation == "→":  # 我克者为财
                    useful_gods.append(f"{element}（财星）")
                elif relation == "↓":  # 我生者为食伤
                    useful_gods.append(f"{element}（食伤）")
                elif relation == "←":  # 克我者为官杀
                    useful_gods.append(f"{element}（官杀）")
        else:
            # 身弱用生扶
            for element in WUXING:
                relation = WUXING_RELATIONS.get((element, day_element), "")
                if relation == "↓":  # 生我者为印
                    useful_gods.append(f"{element}（印星）")
                elif relation == "=":  # 同我者为比劫
                    useful_gods.append(f"{element}（比劫）")

        return {
            "useful_gods": useful_gods[:3],  # 取前3个
            "avoid_gods": avoid_gods[:3],  # 取前3个
            "strategy": (
                "扶抑" if strength_analysis["level"] in ["偏弱", "很弱"] else "抑制"
            ),
        }

    def get_detailed_fortune_analysis(self, eight_char_data: Dict[str, Any]) -> str:
        """
        获取详细的命理分析文本.
        """
        analysis = self.analyze_eight_char_structure(eight_char_data)

        result_lines = []
        result_lines.append("=== 八字命理详细分析 ===\n")

        # 日主分析
        result_lines.append(
            f"【日主】{analysis['day_master']}（{GAN_WUXING.get(analysis['day_master'], '')}）"
        )
        result_lines.append(
            f"【强弱】{analysis['strength']['level']}（得分：{analysis['strength']['score']}）"
        )
        result_lines.append("")

        # 十神分析
        result_lines.append("【十神分布】")
        for god_name, positions in analysis["ten_gods"].items():
            if positions:
                result_lines.append(f"  {god_name}：{', '.join(positions)}")
        result_lines.append("")

        # 用神分析
        result_lines.append("【用神分析】")
        result_lines.append(f"  策略：{analysis['useful_god']['strategy']}")
        if analysis["useful_god"]["useful_gods"]:
            result_lines.append(
                f"  用神：{', '.join(analysis['useful_god']['useful_gods'])}"
            )
        result_lines.append("")

        # 五行平衡
        result_lines.append("【五行分布】")
        for element, count in analysis["wuxing_balance"]["distribution"].items():
            result_lines.append(f"  {element}：{count:.1f}")
        result_lines.append(f"  平衡分：{analysis['wuxing_balance']['balance_score']}")
        result_lines.append("")

        # 地支关系
        result_lines.append("【地支关系】")
        for relation_type, relations in analysis["zhi_relations"].items():
            if relations:
                result_lines.append(f"  {relation_type}：{', '.join(relations)}")
        result_lines.append("")

        # 神煞
        result_lines.append("【神煞分析】")
        for shensha_name, positions in analysis["shensha"].items():
            if positions:
                result_lines.append(f"  {shensha_name}：{', '.join(positions)}")
        result_lines.append("")

        # 纳音
        result_lines.append("【纳音五行】")
        for nayin in analysis["nayin"]:
            result_lines.append(f"  {nayin}")

        return "\n".join(result_lines)


# 全局分析器实例
_professional_analyzer = None


def get_professional_analyzer() -> ProfessionalAnalyzer:
    """
    获取专业分析器单例.
    """
    global _professional_analyzer
    if _professional_analyzer is None:
        _professional_analyzer = ProfessionalAnalyzer()
    return _professional_analyzer
