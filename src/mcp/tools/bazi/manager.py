"""
八字命理管理器 负责八字分析和命理计算的核心功能。
"""

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class BaziManager:
    """
    八字命理管理器。
    """

    def __init__(self):
        """
        初始化八字管理器.
        """

    def init_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        初始化并注册所有八字命理工具。
        """
        from .marriage_tools import (
            analyze_marriage_compatibility,
            analyze_marriage_timing,
        )
        from .tools import (
            build_bazi_from_lunar_datetime,
            build_bazi_from_solar_datetime,
            get_bazi_detail,
            get_chinese_calendar,
            get_solar_times,
        )

        # 获取八字详情（主要工具）
        bazi_detail_props = PropertyList(
            [
                Property("solar_datetime", PropertyType.STRING, default_value=""),
                Property("lunar_datetime", PropertyType.STRING, default_value=""),
                Property("gender", PropertyType.INTEGER, default_value=1),
                Property(
                    "eight_char_provider_sect", PropertyType.INTEGER, default_value=2
                ),
            ]
        )
        add_tool(
            (
                "self.bazi.get_bazi_detail",
                "根据时间（公历或农历）、性别来获取完整的八字命理分析信息。"
                "这是八字分析的核心工具，提供全面的命理解读。\n"
                "使用场景：\n"
                "1. 个人八字命理分析\n"
                "2. 生辰八字查询\n"
                "3. 命理咨询和解读\n"
                "4. 八字合婚分析\n"
                "5. 运势分析基础数据\n"
                "\n功能特点：\n"
                "- 支持公历和农历时间输入\n"
                "- 提供完整的四柱八字信息\n"
                "- 包含神煞、大运、刑冲合会分析\n"
                "- 支持不同的子时起法配置\n"
                "\n参数说明：\n"
                "  solar_datetime: 公历时间，ISO格式，如'2008-03-01T13:00:00+08:00'\n"
                "  lunar_datetime: 农历时间，如'2000-5-5 12:00:00'\n"
                "  gender: 性别，0=女性，1=男性\n"
                "  eight_char_provider_sect: 早晚子时配置，1=23:00-23:59日干支为明天，2=为当天（默认）\n"
                "\n注意：solar_datetime和lunar_datetime必须传且只传其中一个",
                bazi_detail_props,
                get_bazi_detail,
            )
        )

        # 根据八字获取公历时间
        solar_times_props = PropertyList([Property("bazi", PropertyType.STRING)])
        add_tool(
            (
                "self.bazi.get_solar_times",
                "根据八字推算可能的公历时间列表。返回的时间格式为：YYYY-MM-DD hh:mm:ss。\n"
                "使用场景：\n"
                "1. 八字反推生辰时间\n"
                "2. 验证八字的准确性\n"
                "3. 寻找历史上同八字的时间点\n"
                "4. 八字时间校验\n"
                "\n功能特点：\n"
                "- 基于八字干支组合推算时间\n"
                "- 支持多个可能时间的查询\n"
                "- 时间范围可配置\n"
                "\n参数说明：\n"
                "  bazi: 八字，按年柱、月柱、日柱、时柱顺序，用空格隔开\n"
                "        例如：'戊寅 己未 己卯 辛未'",
                solar_times_props,
                get_solar_times,
            )
        )

        # 获取黄历信息
        chinese_calendar_props = PropertyList(
            [Property("solar_datetime", PropertyType.STRING, default_value="")]
        )
        add_tool(
            (
                "self.bazi.get_chinese_calendar",
                "获取指定公历时间（默认今天）的中国传统黄历信息。"
                "提供完整的农历日期、干支、宜忌、神煞方位等信息。\n"
                "使用场景：\n"
                "1. 查询今日黄历宜忌\n"
                "2. 择日选时参考\n"
                "3. 传统节日查询\n"
                "4. 风水方位指导\n"
                "5. 民俗文化了解\n"
                "\n功能特点：\n"
                "- 完整的农历信息\n"
                "- 二十八宿和节气信息\n"
                "- 神煞方位指导\n"
                "- 彭祖百忌提醒\n"
                "- 传统节日标注\n"
                "- 宜忌事项建议\n"
                "\n参数说明：\n"
                "  solar_datetime: 公历时间，ISO格式，如'2008-03-01T13:00:00+08:00'\n"
                "                 如不提供则默认为当前时间",
                chinese_calendar_props,
                get_chinese_calendar,
            )
        )

        # 根据农历时间获取八字（已弃用）
        lunar_bazi_props = PropertyList(
            [
                Property("lunar_datetime", PropertyType.STRING),
                Property("gender", PropertyType.INTEGER, default_value=1),
                Property(
                    "eight_char_provider_sect", PropertyType.INTEGER, default_value=2
                ),
            ]
        )
        add_tool(
            (
                "self.bazi.build_bazi_from_lunar_datetime",
                "根据农历时间、性别来获取八字信息。\n"
                "注意：此工具已弃用，建议使用get_bazi_detail替代。\n"
                "\n参数说明：\n"
                "  lunar_datetime: 农历时间，例如：'2000-5-15 12:00:00'\n"
                "  gender: 性别，0=女性，1=男性\n"
                "  eight_char_provider_sect: 早晚子时配置",
                lunar_bazi_props,
                build_bazi_from_lunar_datetime,
            )
        )

        # 根据阳历时间获取八字（已弃用）
        solar_bazi_props = PropertyList(
            [
                Property("solar_datetime", PropertyType.STRING),
                Property("gender", PropertyType.INTEGER, default_value=1),
                Property(
                    "eight_char_provider_sect", PropertyType.INTEGER, default_value=2
                ),
            ]
        )
        add_tool(
            (
                "self.bazi.build_bazi_from_solar_datetime",
                "根据阳历时间、性别来获取八字信息。\n"
                "注意：此工具已弃用，建议使用get_bazi_detail替代。\n"
                "\n参数说明：\n"
                "  solar_datetime: 公历时间，ISO格式，如'2008-03-01T13:00:00+08:00'\n"
                "  gender: 性别，0=女性，1=男性\n"
                "  eight_char_provider_sect: 早晚子时配置",
                solar_bazi_props,
                build_bazi_from_solar_datetime,
            )
        )

        # 婚姻时机分析
        marriage_timing_props = PropertyList(
            [
                Property("solar_datetime", PropertyType.STRING, default_value=""),
                Property("lunar_datetime", PropertyType.STRING, default_value=""),
                Property("gender", PropertyType.INTEGER, default_value=1),
                Property(
                    "eight_char_provider_sect", PropertyType.INTEGER, default_value=2
                ),
            ]
        )
        add_tool(
            (
                "self.bazi.analyze_marriage_timing",
                "分析婚姻时机、配偶特征和婚姻质量。"
                "专门针对婚姻相关的命理分析，包括结婚时间预测、配偶特征等。\\n"
                "使用场景：\\n"
                "1. 预测最佳结婚时机\\n"
                "2. 分析配偶外貌和性格特征\\n"
                "3. 评估婚姻质量和稳定性\\n"
                "4. 识别婚姻中的潜在障碍\\n"
                "5. 寻找有利的结婚年份\\n"
                "\\n功能特点：\\n"
                "- 夫妻星强弱分析\\n"
                "- 结婚年龄段预测\\n"
                "- 配偶宫详细解读\\n"
                "- 婚姻阻碍识别\\n"
                "- 有利时间推荐\\n"
                "\\n参数说明：\\n"
                "  solar_datetime: 公历时间，ISO格式，如'2008-03-01T13:00:00+08:00'\\n"
                "  lunar_datetime: 农历时间，如'2000-5-5 12:00:00'\\n"
                "  gender: 性别，0=女性，1=男性\\n"
                "  eight_char_provider_sect: 早晚子时配置\\n"
                "\\n注意：solar_datetime和lunar_datetime必须传且只传其中一个",
                marriage_timing_props,
                analyze_marriage_timing,
            )
        )

        # 合婚分析
        marriage_compatibility_props = PropertyList(
            [
                Property("male_solar_datetime", PropertyType.STRING, default_value=""),
                Property("male_lunar_datetime", PropertyType.STRING, default_value=""),
                Property(
                    "female_solar_datetime", PropertyType.STRING, default_value=""
                ),
                Property(
                    "female_lunar_datetime", PropertyType.STRING, default_value=""
                ),
            ]
        )
        add_tool(
            (
                "self.bazi.analyze_marriage_compatibility",
                "分析两人八字合婚，评估婚姻匹配度和相处模式。"
                "通过对比双方八字，分析婚姻匹配程度和注意事项。\\n"
                "使用场景：\\n"
                "1. 婚前合婚分析\\n"
                "2. 评估双方匹配度\\n"
                "3. 识别相处中的问题\\n"
                "4. 获取婚姻改善建议\\n"
                "5. 选择最佳结婚时机\\n"
                "\\n功能特点：\\n"
                "- 五行匹配分析\\n"
                "- 生肖相配评估\\n"
                "- 日柱组合判断\\n"
                "- 综合匹配评分\\n"
                "- 具体改善建议\\n"
                "\\n参数说明：\\n"
                "  male_solar_datetime: 男方公历时间\\n"
                "  male_lunar_datetime: 男方农历时间\\n"
                "  female_solar_datetime: 女方公历时间\\n"
                "  female_lunar_datetime: 女方农历时间\\n"
                "\\n注意：男女双方时间信息各自只需提供公历或农历其中一个",
                marriage_compatibility_props,
                analyze_marriage_compatibility,
            )
        )


# 全局管理器实例
_bazi_manager = None


def get_bazi_manager() -> BaziManager:
    """
    获取八字管理器单例。
    """
    global _bazi_manager
    if _bazi_manager is None:
        _bazi_manager = BaziManager()
    return _bazi_manager
