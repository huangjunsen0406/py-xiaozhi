"""
婚姻分析工具函数.
"""

import json
from typing import Any, Dict, List

from src.utils.logging_config import get_logger

from .bazi_calculator import get_bazi_calculator
from .marriage_analyzer import get_marriage_analyzer

logger = get_logger(__name__)


async def analyze_marriage_timing(args: Dict[str, Any]) -> str:
    """
    分析婚姻时机和配偶信息.
    """
    try:
        solar_datetime = args.get("solar_datetime")
        lunar_datetime = args.get("lunar_datetime")
        gender = args.get("gender", 1)
        eight_char_provider_sect = args.get("eight_char_provider_sect", 2)

        if not solar_datetime and not lunar_datetime:
            return json.dumps(
                {
                    "success": False,
                    "message": "solar_datetime和lunar_datetime必须传且只传其中一个",
                },
                ensure_ascii=False,
            )

        # 先获取基础八字信息
        calculator = get_bazi_calculator()
        bazi_result = calculator.build_bazi(
            solar_datetime=solar_datetime,
            lunar_datetime=lunar_datetime,
            gender=gender,
            eight_char_provider_sect=eight_char_provider_sect,
        )

        # 进行婚姻专项分析
        marriage_analyzer = get_marriage_analyzer()

        # 构建适合婚姻分析的八字数据格式
        eight_char_dict = {
            "year": bazi_result.year_pillar,
            "month": bazi_result.month_pillar,
            "day": bazi_result.day_pillar,
            "hour": bazi_result.hour_pillar,
        }

        marriage_analysis = marriage_analyzer.analyze_marriage_timing(
            eight_char_dict, gender
        )

        # 合并结果
        result = {
            "basic_info": {
                "八字": bazi_result.bazi,
                "性别": "男" if gender == 1 else "女",
                "日主": bazi_result.day_master,
                "生肖": bazi_result.zodiac,
            },
            "marriage_analysis": marriage_analysis,
        }

        return json.dumps(
            {"success": True, "data": result}, ensure_ascii=False, indent=2
        )

    except Exception as e:
        logger.error(f"婚姻分析失败: {e}")
        return json.dumps(
            {"success": False, "message": f"婚姻分析失败: {str(e)}"},
            ensure_ascii=False,
        )


async def analyze_marriage_compatibility(args: Dict[str, Any]) -> str:
    """
    分析两人八字婚姻合婚.
    """
    try:
        # 男方信息
        male_solar = args.get("male_solar_datetime")
        male_lunar = args.get("male_lunar_datetime")

        # 女方信息
        female_solar = args.get("female_solar_datetime")
        female_lunar = args.get("female_lunar_datetime")

        if not (male_solar or male_lunar) or not (female_solar or female_lunar):
            return json.dumps(
                {
                    "success": False,
                    "message": "必须提供男女双方的时间信息",
                },
                ensure_ascii=False,
            )

        calculator = get_bazi_calculator()

        # 获取男方八字
        male_bazi = calculator.build_bazi(
            solar_datetime=male_solar, lunar_datetime=male_lunar, gender=1
        )

        # 获取女方八字
        female_bazi = calculator.build_bazi(
            solar_datetime=female_solar, lunar_datetime=female_lunar, gender=0
        )

        # 进行合婚分析
        compatibility_result = _analyze_compatibility(male_bazi, female_bazi)

        result = {
            "male_info": {
                "八字": male_bazi.bazi,
                "日主": male_bazi.day_master,
                "生肖": male_bazi.zodiac,
            },
            "female_info": {
                "八字": female_bazi.bazi,
                "日主": female_bazi.day_master,
                "生肖": female_bazi.zodiac,
            },
            "compatibility": compatibility_result,
        }

        return json.dumps(
            {"success": True, "data": result}, ensure_ascii=False, indent=2
        )

    except Exception as e:
        logger.error(f"合婚分析失败: {e}")
        return json.dumps(
            {"success": False, "message": f"合婚分析失败: {str(e)}"},
            ensure_ascii=False,
        )


def _analyze_compatibility(male_bazi, female_bazi) -> Dict[str, Any]:
    """分析两人八字合婚 - 使用专业算法"""
    # 获取双方日柱
    male_day_gan = male_bazi.day_master
    female_day_gan = female_bazi.day_pillar["天干"]["天干"]

    male_day_zhi = male_bazi.day_pillar["地支"]["地支"]
    female_day_zhi = female_bazi.day_pillar["地支"]["地支"]

    # 专业五行分析
    element_analysis = _analyze_element_compatibility(male_day_gan, female_day_gan)

    # 生肖相配分析
    zodiac_analysis = _analyze_zodiac_compatibility(
        male_bazi.zodiac, female_bazi.zodiac
    )

    # 日柱相配分析
    pillar_analysis = _analyze_pillar_compatibility(
        male_day_gan + male_day_zhi, female_day_gan + female_day_zhi
    )

    # 地支关系分析
    branch_analysis = _analyze_branch_relationships(male_bazi, female_bazi)

    # 八字互补分析
    complement_analysis = _analyze_complement(male_bazi, female_bazi)

    # 综合评分
    total_score = (
        element_analysis["score"] * 0.3
        + zodiac_analysis["score"] * 0.2
        + pillar_analysis["score"] * 0.2
        + branch_analysis["score"] * 0.15
        + complement_analysis["score"] * 0.15
    )

    return {
        "overall_score": round(total_score, 1),
        "overall_level": _get_compatibility_level(total_score),
        "element_analysis": element_analysis,
        "zodiac_analysis": zodiac_analysis,
        "pillar_analysis": pillar_analysis,
        "branch_analysis": branch_analysis,
        "complement_analysis": complement_analysis,
        "suggestions": _get_professional_suggestions(
            total_score, element_analysis, zodiac_analysis
        ),
    }


def _analyze_element_compatibility(male_gan: str, female_gan: str) -> Dict[str, Any]:
    """
    专业五行相配分析.
    """
    from .professional_data import GAN_WUXING, WUXING_RELATIONS

    male_element = GAN_WUXING.get(male_gan, "")
    female_element = GAN_WUXING.get(female_gan, "")

    element_relation = WUXING_RELATIONS.get((male_element, female_element), "")

    # 亓不位分析
    score_map = {
        "↓": 90,  # 男生女，夫妻恩爱
        "=": 80,  # 同类相配，志趣相投
        "←": 50,  # 女克男，女强男弱
        "→": 55,  # 男克女，男强女弱
        "↑": 85,  # 女生男，妻贤夫贵
    }

    desc_map = {
        "↓": "男生女，夫妻恩爱，家庭和睦",
        "=": "同类相配，志趣相投，容易理解",
        "←": "女克男，女强男弱，需要平衡",
        "→": "男克女，男强女弱，需要包容",
        "↑": "女生男，妻贤夫贵，互相成就",
    }

    return {
        "male_element": male_element,
        "female_element": female_element,
        "relation": element_relation,
        "score": score_map.get(element_relation, 70),
        "description": desc_map.get(element_relation, "关系平和"),
    }


def _analyze_zodiac_compatibility(
    male_zodiac: str, female_zodiac: str
) -> Dict[str, Any]:
    """
    专业生肖相配分析.
    """
    from .professional_data import ZHI_CHONG, ZHI_HAI, ZHI_LIUHE, ZHI_SANHE, ZHI_XING

    # 生肖对应地支映射
    zodiac_to_zhi = {
        "鼠": "子",
        "牛": "丑",
        "虎": "寅",
        "兔": "卯",
        "龙": "辰",
        "蛇": "巳",
        "马": "午",
        "羊": "未",
        "猴": "申",
        "鸡": "酉",
        "狗": "戌",
        "猪": "亥",
    }

    male_zhi = zodiac_to_zhi.get(male_zodiac, "")
    female_zhi = zodiac_to_zhi.get(female_zodiac, "")

    # 检查关系
    if (male_zhi, female_zhi) in ZHI_LIUHE or (female_zhi, male_zhi) in ZHI_LIUHE:
        return {
            "score": 90,
            "level": "天作之合",
            "description": "六合生肖，感情深厚",
            "relation": "六合",
        }

    # 检查三合
    for sanhe_group in ZHI_SANHE:
        if male_zhi in sanhe_group and female_zhi in sanhe_group:
            return {
                "score": 85,
                "level": "天作之合",
                "description": "三合生肖，相处融洽",
                "relation": "三合",
            }

    # 检查相冲
    if (male_zhi, female_zhi) in ZHI_CHONG or (female_zhi, male_zhi) in ZHI_CHONG:
        return {
            "score": 30,
            "level": "相冲不合",
            "description": "生肖相冲，矛盾较多",
            "relation": "相冲",
        }

    # 检查相刑
    for xing_group in ZHI_XING:
        if male_zhi in xing_group and female_zhi in xing_group:
            return {
                "score": 40,
                "level": "相刑不合",
                "description": "生肖相刑，需要化解",
                "relation": "相刑",
            }

    # 检查相害
    if (male_zhi, female_zhi) in ZHI_HAI or (female_zhi, male_zhi) in ZHI_HAI:
        return {
            "score": 45,
            "level": "相害不合",
            "description": "生肖相害，小有不合",
            "relation": "相害",
        }

    # 普通关系
    return {
        "score": 70,
        "level": "一般",
        "description": "生肖平和，无特别冲突",
        "relation": "平和",
    }


def _analyze_pillar_compatibility(
    male_pillar: str, female_pillar: str
) -> Dict[str, Any]:
    """
    专业日柱相配分析.
    """
    if male_pillar == female_pillar:
        return {"score": 55, "description": "日柱相同，共通点多但需要差异化解"}

    # 分析干支组合
    male_gan, male_zhi = male_pillar[0], male_pillar[1]
    female_gan, female_zhi = female_pillar[0], female_pillar[1]

    score = 70  # 基础分数

    # 天干关系
    from .professional_data import get_ten_gods_relation

    gan_relation = get_ten_gods_relation(male_gan, female_gan)
    if gan_relation in ["正财", "偏财", "正官", "七杀"]:
        score += 10

    # 地支关系
    from .professional_data import ZHI_CHONG, ZHI_LIUHE

    if (male_zhi, female_zhi) in ZHI_LIUHE or (female_zhi, male_zhi) in ZHI_LIUHE:
        score += 15
    elif (male_zhi, female_zhi) in ZHI_CHONG or (female_zhi, male_zhi) in ZHI_CHONG:
        score -= 20

    return {
        "score": min(95, max(30, score)),
        "description": f"日柱组合分析：{gan_relation}关系",
    }


def _analyze_branch_relationships(male_bazi, female_bazi) -> Dict[str, Any]:
    """
    分析地支关系.
    """
    # 获取双方四柱地支
    male_branches = [
        male_bazi.year_pillar["地支"]["地支"],
        male_bazi.month_pillar["地支"]["地支"],
        male_bazi.day_pillar["地支"]["地支"],
        male_bazi.hour_pillar["地支"]["地支"],
    ]

    female_branches = [
        female_bazi.year_pillar["地支"]["地支"],
        female_bazi.month_pillar["地支"]["地支"],
        female_bazi.day_pillar["地支"]["地支"],
        female_bazi.hour_pillar["地支"]["地支"],
    ]

    # 分析地支间关系
    from .professional_data import analyze_zhi_combinations

    combined_branches = male_branches + female_branches
    relationships = analyze_zhi_combinations(combined_branches)

    score = 70
    if relationships.get("liuhe", []):
        score += 10
    if relationships.get("sanhe", []):
        score += 8
    if relationships.get("chong", []):
        score -= 15
    if relationships.get("xing", []):
        score -= 10

    return {
        "score": min(95, max(30, score)),
        "relationships": relationships,
        "description": f"地支关系分析：{len(relationships.get('liuhe', []))}个六合、{len(relationships.get('chong', []))}个相冲",
    }


def _analyze_complement(male_bazi, female_bazi) -> Dict[str, Any]:
    """
    分析八字互补性.
    """
    # 分析五行互补
    from .professional_data import GAN_WUXING, WUXING, ZHI_WUXING

    male_elements = []
    female_elements = []

    # 获取男方五行
    for pillar in [
        male_bazi.year_pillar,
        male_bazi.month_pillar,
        male_bazi.day_pillar,
        male_bazi.hour_pillar,
    ]:
        gan = pillar["天干"]["天干"]
        zhi = pillar["地支"]["地支"]
        male_elements.extend([GAN_WUXING.get(gan, ""), ZHI_WUXING.get(zhi, "")])

    # 获取女方五行
    for pillar in [
        female_bazi.year_pillar,
        female_bazi.month_pillar,
        female_bazi.day_pillar,
        female_bazi.hour_pillar,
    ]:
        gan = pillar["天干"]["天干"]
        zhi = pillar["地支"]["地支"]
        female_elements.extend([GAN_WUXING.get(gan, ""), ZHI_WUXING.get(zhi, "")])

    # 统计五行分布
    from collections import Counter

    male_counter = Counter(male_elements)
    female_counter = Counter(female_elements)

    # 计算互补性
    complement_score = 0
    for element in WUXING:
        male_count = male_counter.get(element, 0)
        female_count = female_counter.get(element, 0)

        # 互补加分
        if male_count > 0 and female_count == 0:
            complement_score += 5
        elif male_count == 0 and female_count > 0:
            complement_score += 5
        elif abs(male_count - female_count) <= 1:
            complement_score += 2

    return {
        "score": min(90, 50 + complement_score),
        "male_elements": dict(male_counter),
        "female_elements": dict(female_counter),
        "description": f"五行互补性分析，补分{complement_score}",
    }


def _get_professional_suggestions(
    total_score: float,
    element_analysis: Dict[str, Any],
    zodiac_analysis: Dict[str, Any],
) -> List[str]:
    """
    获取专业合婚建议.
    """
    suggestions = []

    if total_score >= 80:
        suggestions.extend(["天作之合，婚姻美满", "互相扶持，白头偕老"])
    elif total_score >= 70:
        suggestions.extend(["基础良好，需要磨合", "多沟通理解，感情可长久"])
    elif total_score >= 60:
        suggestions.extend(["需要努力经营", "多包容对方，化解矛盾"])
    else:
        suggestions.extend(["建议谨慎考虑", "如结婚需要择日化解"])

    # 根据五行分析添加建议
    if element_analysis["relation"] == "←":
        suggestions.append("女方需要多体谅男方，避免过于强势")
    elif element_analysis["relation"] == "→":
        suggestions.append("男方需要多关心女方，避免过于专横")

    # 根据生肖分析添加建议
    if zodiac_analysis["relation"] == "相冲":
        suggestions.append("生肖相冲，建议佩戴化解物品或择吉日结婚")

    return suggestions


def _get_compatibility_level(score: float) -> str:
    """
    获取合婚等级.
    """
    if score >= 80:
        return "上等婚"
    elif score >= 70:
        return "中上婚"
    elif score >= 60:
        return "中等婚"
    else:
        return "下等婚"


def _get_compatibility_suggestions(score: float) -> List[str]:
    """
    获取合婚建议.
    """
    if score >= 80:
        return ["天作之合，婚姻美满", "互相扶持，白头偕老", "继续保持良好沟通"]
    elif score >= 70:
        return ["基础良好，需要磨合", "多沟通理解，感情可长久", "注重共同兴趣培养"]
    elif score >= 60:
        return [
            "需要努力经营",
            "多包容对方，化解矛盾",
            "建议婚前辅导",
            "共同制定婚姻规则",
        ]
    else:
        return [
            "建议谨慎考虑",
            "如结婚需要择日化解",
            "多行善积德改善运势",
            "需要专业指导",
        ]
