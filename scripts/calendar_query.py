#!/usr/bin/env python3
"""
日程查询脚本 用于查看和管理日程安排.
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

from src.logging import get_logger
from src.mcp.tools.calendar import get_calendar_manager

# 添加项目根目录到Python路径 - 必须在导入src模块之前
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logger = get_logger()


class CalendarQueryScript:
    """
    日程查询脚本类.
    """

    def __init__(self):
        self.manager = get_calendar_manager()

    def format_event_display(self, event, show_details=True):
        """
        格式化事件显示.
        """
        start_dt = datetime.fromisoformat(event.start_time)
        end_dt = datetime.fromisoformat(event.end_time)

        # 基本信息
        time_str = f"{start_dt.strftime('%m/%d %H:%M')} - {end_dt.strftime('%H:%M')}"
        basic_info = f"📅 {time_str} | 【{event.category}】{event.title}"

        if not show_details:
            return basic_info

        # 详细信息
        details = []
        if event.description:
            details.append(f"   📝 备注: {event.description}")

        # 提醒信息
        if event.reminder_minutes > 0:
            details.append(f"   ⏰ 提醒: 提前{event.reminder_minutes}分钟")
            if hasattr(event, "reminder_sent") and event.reminder_sent:
                details.append("   ✅ 提醒状态: 已发送")
            else:
                details.append("   ⏳ 提醒状态: 待发送")

        # 时间距离
        now = datetime.now()
        time_diff = start_dt - now
        if time_diff.total_seconds() > 0:
            days = time_diff.days
            hours = int(time_diff.seconds // 3600)
            minutes = int((time_diff.seconds % 3600) // 60)

            time_until_parts = []
            if days > 0:
                time_until_parts.append(f"{days}天")
            if hours > 0:
                time_until_parts.append(f"{hours}小时")
            if minutes > 0:
                time_until_parts.append(f"{minutes}分钟")

            if time_until_parts:
                details.append(f"   🕐 距离开始: {' '.join(time_until_parts)}")
            else:
                details.append("   🕐 距离开始: 即将开始")
        elif start_dt <= now <= end_dt:
            details.append("   🔴 状态: 正在进行中")
        else:
            details.append("   ✅ 状态: 已结束")

        if details:
            return basic_info + "\n" + "\n".join(details)
        return basic_info

    async def query_today(self):
        """
        查询今日日程.
        """
        print("📅 今日日程安排")
        print("=" * 50)

        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        events = self.manager.get_events(
            start_date=today_start.isoformat(), end_date=today_end.isoformat()
        )

        if not events:
            print("🎉 今天没有安排任何日程")
            return

        print(f"📊 共有 {len(events)} 个日程:\n")
        for i, event in enumerate(events, 1):
            print(f"{i}. {self.format_event_display(event)}")
            if i < len(events):
                print()

    async def query_tomorrow(self):
        """
        查询明日日程.
        """
        print("📅 明日日程安排")
        print("=" * 50)

        now = datetime.now()
        tomorrow_start = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        tomorrow_end = tomorrow_start + timedelta(days=1)

        events = self.manager.get_events(
            start_date=tomorrow_start.isoformat(), end_date=tomorrow_end.isoformat()
        )

        if not events:
            print("🎉 明天没有安排任何日程")
            return

        print(f"📊 共有 {len(events)} 个日程:\n")
        for i, event in enumerate(events, 1):
            print(f"{i}. {self.format_event_display(event)}")
            if i < len(events):
                print()

    async def query_week(self):
        """
        查询本周日程.
        """
        print("📅 本周日程安排")
        print("=" * 50)

        now = datetime.now()
        # 本周一
        days_since_monday = now.weekday()
        week_start = (now - timedelta(days=days_since_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_end = week_start + timedelta(days=7)

        events = self.manager.get_events(
            start_date=week_start.isoformat(), end_date=week_end.isoformat()
        )

        if not events:
            print("🎉 本周没有安排任何日程")
            return

        print(f"📊 共有 {len(events)} 个日程:\n")

        # 按日期分组显示
        events_by_date = {}
        for event in events:
            event_date = datetime.fromisoformat(event.start_time).date()
            if event_date not in events_by_date:
                events_by_date[event_date] = []
            events_by_date[event_date].append(event)

        for date in sorted(events_by_date.keys()):
            weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][
                date.weekday()
            ]
            print(f"📆 {date.strftime('%m月%d日')} ({weekday})")
            print("-" * 30)

            for event in events_by_date[date]:
                print(f"  {self.format_event_display(event, show_details=False)}")
            print()

    async def query_upcoming(self, hours=24):
        """
        查询即将到来的日程.
        """
        print(f"📅 未来 {hours} 小时内的日程")
        print("=" * 50)

        now = datetime.now()
        end_time = now + timedelta(hours=hours)

        events = self.manager.get_events(
            start_date=now.isoformat(), end_date=end_time.isoformat()
        )

        if not events:
            print(f"🎉 未来 {hours} 小时内没有安排任何日程")
            return

        print(f"📊 共有 {len(events)} 个日程:\n")
        for i, event in enumerate(events, 1):
            print(f"{i}. {self.format_event_display(event)}")
            if i < len(events):
                print()

    async def query_by_category(self, category=None):
        """
        按分类查询日程.
        """
        if category:
            print(f"📅 【{category}】分类的日程")
            print("=" * 50)

            events = self.manager.get_events(category=category)

            if not events:
                print(f"🎉 【{category}】分类下没有任何日程")
                return

            print(f"📊 共有 {len(events)} 个日程:\n")
            for i, event in enumerate(events, 1):
                print(f"{i}. {self.format_event_display(event)}")
                if i < len(events):
                    print()
        else:
            print("📅 所有分类统计")
            print("=" * 50)

            categories = self.manager.get_categories()

            if not categories:
                print("🎉 暂无任何分类")
                return

            print("📊 分类列表:")
            for i, cat in enumerate(categories, 1):
                # 统计每个分类的事件数量
                events = self.manager.get_events(category=cat)
                print(f"{i}. 【{cat}】- {len(events)} 个日程")

    async def query_all(self):
        """
        查询所有日程.
        """
        print("📅 所有日程安排")
        print("=" * 50)

        events = self.manager.get_events()

        if not events:
            print("🎉 暂无任何日程安排")
            return

        print(f"📊 总共有 {len(events)} 个日程:\n")

        # 按时间排序并分组显示
        now = datetime.now()
        past_events = []
        current_events = []
        future_events = []

        for event in events:
            start_dt = datetime.fromisoformat(event.start_time)
            end_dt = datetime.fromisoformat(event.end_time)

            if end_dt < now:
                past_events.append(event)
            elif start_dt <= now <= end_dt:
                current_events.append(event)
            else:
                future_events.append(event)

        # 显示正在进行的事件
        if current_events:
            print("🔴 正在进行中:")
            for event in current_events:
                print(f"  {self.format_event_display(event, show_details=False)}")
            print()

        # 显示未来事件
        if future_events:
            print("⏳ 即将到来:")
            for event in future_events[:5]:  # 只显示前5个
                print(f"  {self.format_event_display(event, show_details=False)}")
            if len(future_events) > 5:
                print(f"  ... 还有 {len(future_events) - 5} 个日程")
            print()

        # 显示最近的过去事件
        if past_events:
            recent_past = sorted(past_events, key=lambda e: e.start_time, reverse=True)[
                :3
            ]
            print("✅ 最近完成:")
            for event in recent_past:
                print(f"  {self.format_event_display(event, show_details=False)}")
            if len(past_events) > 3:
                print(f"  ... 还有 {len(past_events) - 3} 个已完成的日程")

    async def search_events(self, keyword):
        """
        搜索日程.
        """
        print(f"🔍 搜索包含 '{keyword}' 的日程")
        print("=" * 50)

        all_events = self.manager.get_events()
        matched_events = []

        for event in all_events:
            if (
                keyword.lower() in event.title.lower()
                or keyword.lower() in event.description.lower()
                or keyword.lower() in event.category.lower()
            ):
                matched_events.append(event)

        if not matched_events:
            print(f"🎉 没有找到包含 '{keyword}' 的日程")
            return

        print(f"📊 找到 {len(matched_events)} 个匹配的日程:\n")
        for i, event in enumerate(matched_events, 1):
            print(f"{i}. {self.format_event_display(event)}")
            if i < len(matched_events):
                print()


async def main():
    """
    主函数.
    """
    parser = argparse.ArgumentParser(description="日程查询脚本")
    parser.add_argument(
        "command",
        nargs="?",
        default="today",
        choices=["today", "tomorrow", "week", "upcoming", "category", "all", "search"],
        help="查询类型",
    )
    parser.add_argument("--hours", type=int, default=24, help="upcoming查询的小时数")
    parser.add_argument("--category", type=str, help="指定分类名称")
    parser.add_argument("--keyword", type=str, help="搜索关键词")

    args = parser.parse_args()

    script = CalendarQueryScript()

    try:
        if args.command == "today":
            await script.query_today()
        elif args.command == "tomorrow":
            await script.query_tomorrow()
        elif args.command == "week":
            await script.query_week()
        elif args.command == "upcoming":
            await script.query_upcoming(args.hours)
        elif args.command == "category":
            await script.query_by_category(args.category)
        elif args.command == "all":
            await script.query_all()
        elif args.command == "search":
            if not args.keyword:
                print("❌ 搜索需要提供关键词，使用 --keyword 参数")
                return
            await script.search_events(args.keyword)

        print("\n" + "=" * 50)
        print("💡 使用帮助:")
        print("  python scripts/calendar_query.py today      # 查看今日日程")
        print("  python scripts/calendar_query.py tomorrow   # 查看明日日程")
        print("  python scripts/calendar_query.py week       # 查看本周日程")
        print(
            "  python scripts/calendar_query.py upcoming --hours 48  # 查看未来48小时"
        )
        print(
            "  python scripts/calendar_query.py category --category 工作  # 查看工作分类"
        )
        print("  python scripts/calendar_query.py all        # 查看所有日程")
        print("  python scripts/calendar_query.py search --keyword 开发  # 搜索日程")

    except Exception as e:
        logger.error(f"查询日程失败: {e}", exc_info=True)
        print(f"❌ 查询失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
