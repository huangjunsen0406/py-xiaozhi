"""
日程管理器 负责日程数据的存储、查询、更新等核心功能.
"""

import os
from typing import List

from src.utils.logging_config import get_logger

from .database import get_calendar_database
from .models import CalendarEvent

logger = get_logger(__name__)


class CalendarManager:
    """
    日程管理器.
    """

    def __init__(self):
        self.db = get_calendar_database()
        # 尝试从旧的JSON文件迁移数据
        self._migrate_from_json_if_exists()

    def init_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        初始化并注册所有日程管理工具.
        """
        from .tools import (
            create_event,
            delete_event,
            delete_events_batch,
            get_categories,
            get_events_by_date,
            get_upcoming_events,
            update_event,
        )

        # 创建日程事件
        create_event_props = PropertyList(
            [
                Property("title", PropertyType.STRING),
                Property("start_time", PropertyType.STRING),
                Property("end_time", PropertyType.STRING, default_value=""),
                Property("description", PropertyType.STRING, default_value=""),
                Property("category", PropertyType.STRING, default_value="默认"),
                Property("reminder_minutes", PropertyType.INTEGER, default_value=15),
            ]
        )
        add_tool(
            (
                "self.calendar.create_event",
                "Create a new calendar event with intelligent duration setting and "
                "conflict detection. Automatically sets appropriate duration based on "
                "category if end_time is not provided.\n"
                "Use this tool when user wants to:\n"
                "1. Schedule a meeting, appointment, or task\n"
                "2. Create reminders or notifications\n"
                "3. Block time for work, personal activities\n"
                "4. Set up recurring activities (meetings, breaks, etc.)\n"
                "\nIntelligent Duration Rules:\n"
                "- '提醒', '休息', '站立' category: 5 minutes\n"
                "- '会议', '工作' category: 1 hour\n"
                "- Title contains '提醒', '站立', '休息': 5 minutes\n"
                "- Default: 30 minutes\n"
                "\nArgs:\n"
                "  title: Event title (required)\n"
                "  start_time: Start time in ISO format '2024-01-01T10:00:00' "
                "(required)\n"
                "  end_time: End time, auto-calculated if not provided\n"
                "  description: Event description\n"
                "  category: Event category (默认/工作/个人/会议/提醒)\n"
                "  reminder_minutes: Reminder time in minutes before event",
                create_event_props,
                create_event,
            )
        )

        # 查询日程
        query_events_props = PropertyList(
            [
                Property("date_type", PropertyType.STRING, default_value="today"),
                Property("category", PropertyType.STRING, default_value=""),
                Property("start_date", PropertyType.STRING, default_value=""),
                Property("end_date", PropertyType.STRING, default_value=""),
            ]
        )
        add_tool(
            (
                "self.calendar.get_events",
                "Query calendar events within specified time range with flexible "
                "filtering options. Supports multiple time range types and category "
                "filtering.\n"
                "Use this tool when user asks about:\n"
                "1. What's scheduled for today/tomorrow/this week/this month\n"
                "2. What meetings/events are coming up\n"
                "3. Show me my schedule for specific dates\n"
                "4. Filter events by category (work, personal, meetings, etc.)\n"
                "5. Check availability for a time period\n"
                "\nTime Range Options:\n"
                "- 'today': Today's events\n"
                "- 'tomorrow': Tomorrow's events\n"
                "- 'week': This week's events\n"
                "- 'month': This month's events\n"
                "- Custom: Use start_date and end_date\n"
                "\nArgs:\n"
                "  date_type: Query type (today/tomorrow/week/month)\n"
                "  category: Filter by category (optional)\n"
                "  start_date: Custom start date in ISO format (optional)\n"
                "  end_date: Custom end date in ISO format (optional)",
                query_events_props,
                get_events_by_date,
            )
        )

        # 获取即将到来的日程
        upcoming_events_props = PropertyList(
            [Property("hours", PropertyType.INTEGER, default_value=24)]
        )
        add_tool(
            (
                "self.calendar.get_upcoming_events",
                "Get upcoming calendar events within specified hours with "
                "time-until calculations. Shows how much time remains until each "
                "event starts.\n"
                "Use this tool when user asks about:\n"
                "1. What's coming up next\n"
                "2. What events are happening soon\n"
                "3. What's my next meeting/appointment\n"
                "4. Show me events in the next few hours\n"
                "5. What should I prepare for\n"
                "\nFeatures:\n"
                "- Shows time remaining until each event ('2小时30分钟后')\n"
                "- Sorts events by start time\n"
                "- Configurable time range (default 24 hours)\n"
                "- Excludes past events\n"
                "\nArgs:\n"
                "  hours: Time range in hours to look ahead (default: 24)",
                upcoming_events_props,
                get_upcoming_events,
            )
        )

        # 更新日程
        update_event_props = PropertyList(
            [
                Property("event_id", PropertyType.STRING),
                Property("title", PropertyType.STRING, default_value=""),
                Property("start_time", PropertyType.STRING, default_value=""),
                Property("end_time", PropertyType.STRING, default_value=""),
                Property("description", PropertyType.STRING, default_value=""),
                Property("category", PropertyType.STRING, default_value=""),
                Property("reminder_minutes", PropertyType.INTEGER, default_value=15),
            ]
        )
        add_tool(
            (
                "self.calendar.update_event",
                "Update an existing calendar event with partial field updates. "
                "Allows modification of any event property without affecting others.\n"
                "Use this tool when user wants to:\n"
                "1. Change meeting time or duration\n"
                "2. Update event title or description\n"
                "3. Modify event category or reminder settings\n"
                "4. Reschedule appointments\n"
                "5. Add or change event details\n"
                "\nFeatures:\n"
                "- Partial updates (only specify fields to change)\n"
                "- Automatic timestamp updating\n"
                "- Preserves unchanged fields\n"
                "\nArgs:\n"
                "  event_id: Unique event identifier (required)\n"
                "  title: New event title (optional)\n"
                "  start_time: New start time in ISO format (optional)\n"
                "  end_time: New end time in ISO format (optional)\n"
                "  description: New description (optional)\n"
                "  category: New category (optional)\n"
                "  reminder_minutes: New reminder time in minutes (optional)",
                update_event_props,
                update_event,
            )
        )

        # 删除日程
        delete_event_props = PropertyList([Property("event_id", PropertyType.STRING)])
        add_tool(
            (
                "self.calendar.delete_event",
                "Delete a calendar event permanently from the schedule. "
                "Removes the event and all associated reminders.\n"
                "Use this tool when user wants to:\n"
                "1. Cancel a meeting or appointment\n"
                "2. Remove completed or outdated events\n"
                "3. Clear schedule conflicts\n"
                "4. Delete duplicate events\n"
                "5. Clean up old events\n"
                "\nArgs:\n"
                "  event_id: Unique identifier of the event to delete",
                delete_event_props,
                delete_event,
            )
        )

        # 批量删除日程
        delete_batch_props = PropertyList(
            [
                Property("start_date", PropertyType.STRING, default_value=""),
                Property("end_date", PropertyType.STRING, default_value=""),
                Property("category", PropertyType.STRING, default_value=""),
                Property("date_type", PropertyType.STRING, default_value=""),
                Property("delete_all", PropertyType.BOOLEAN, default_value=False),
            ]
        )
        add_tool(
            (
                "self.calendar.delete_events_batch",
                "Batch delete multiple calendar events based on specified "
                "criteria or delete all events. Supports flexible filtering "
                "and time-based deletion.\n"
                "Use this tool when user wants to:\n"
                "1. Clear all events from schedule\n"
                "2. Remove all events from a specific time period "
                "(today/week/month)\n"
                "3. Delete all events of a specific category\n"
                "4. Clean up schedule for a date range\n"
                "5. Bulk remove outdated or completed events\n"
                "\nDeletion Options:\n"
                "- delete_all=true: Remove all events from calendar\n"
                "- date_type: Remove events from 'today'/'tomorrow'/"
                "'week'/'month'\n"
                "- category: Remove all events of specific category\n"
                "- start_date + end_date: Remove events in custom date range\n"
                "\nSafety Features:\n"
                "- Returns count of deleted events\n"
                "- Lists titles of deleted events for confirmation\n"
                "- Transaction-safe deletion\n"
                "\nArgs:\n"
                "  start_date: Start date for range deletion "
                "(ISO format, optional)\n"
                "  end_date: End date for range deletion "
                "(ISO format, optional)\n"
                "  category: Delete events of specific category (optional)\n"
                "  date_type: Quick deletion for today/tomorrow/week/month "
                "(optional)\n"
                "  delete_all: Delete ALL events if true (default: false)",
                delete_batch_props,
                delete_events_batch,
            )
        )

        # 获取分类
        add_tool(
            (
                "self.calendar.get_categories",
                "Get all available calendar event categories for organizing "
                "and filtering events. Returns the complete list of categories "
                "that can be used when creating or updating events.\n"
                "Use this tool when user asks about:\n"
                "1. What categories are available for events\n"
                "2. How to organize or classify events\n"
                "3. What types of events can be created\n"
                "4. Available options for event categorization\n"
                "\nDefault Categories:\n"
                "- 默认 (Default)\n"
                "- 工作 (Work)\n"
                "- 个人 (Personal)\n"
                "- 会议 (Meeting)\n"
                "- 提醒 (Reminder)",
                PropertyList(),
                get_categories,
            )
        )

    def _migrate_from_json_if_exists(self):
        """
        从旧的JSON文件迁移数据（如果存在）
        """
        # 检查项目根目录中的旧JSON文件
        from src.utils.resource_finder import get_project_root, get_user_cache_dir

        try:
            project_root = get_project_root()
            json_file = project_root / "cache" / "calendar_data.json"
        except Exception:
            # 如果无法获取项目根目录，检查用户缓存目录
            user_cache_dir = get_user_cache_dir(create=False)
            json_file = user_cache_dir / "calendar_data.json"

        if os.path.exists(json_file):
            logger.info("发现旧的JSON数据文件，开始迁移到SQLite...")
            if self.db.migrate_from_json(json_file):
                # 迁移成功后备份原文件
                backup_file = f"{json_file}.backup"
                os.rename(json_file, backup_file)
                logger.info(f"数据迁移完成，原文件已备份为: {backup_file}")
            else:
                logger.warning("数据迁移失败，保留原JSON文件")

    def add_event(self, event: CalendarEvent) -> bool:
        """
        添加事件.
        """
        return self.db.add_event(event.to_dict())

    def get_events(
        self, start_date: str = None, end_date: str = None, category: str = None
    ) -> List[CalendarEvent]:
        """
        获取事件列表.
        """
        try:
            events_data = self.db.get_events(start_date, end_date, category)
            return [CalendarEvent.from_dict(event_data) for event_data in events_data]
        except Exception as e:
            logger.error(f"获取日程失败: {e}")
            return []

    def update_event(self, event_id: str, **kwargs) -> bool:
        """
        更新事件.
        """
        return self.db.update_event(event_id, **kwargs)

    def delete_event(self, event_id: str) -> bool:
        """
        删除事件.
        """
        return self.db.delete_event(event_id)

    def delete_events_batch(
        self,
        start_date: str = None,
        end_date: str = None,
        category: str = None,
        delete_all: bool = False,
    ):
        """
        批量删除事件.
        """
        return self.db.delete_events_batch(start_date, end_date, category, delete_all)

    def get_categories(self) -> List[str]:
        """
        获取所有分类.
        """
        return self.db.get_categories()


# 全局管理器实例
_calendar_manager = None


def get_calendar_manager() -> CalendarManager:
    """
    获取日程管理器单例.
    """
    global _calendar_manager
    if _calendar_manager is None:
        _calendar_manager = CalendarManager()
    return _calendar_manager
