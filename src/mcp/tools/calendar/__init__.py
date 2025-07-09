"""日程管理工具包.

提供完整的日程管理功能，包括事件创建、查询、更新、删除等操作。
"""

from .database import CalendarDatabase, get_calendar_database
from .manager import CalendarManager, get_calendar_manager
from .models import CalendarEvent
from .reminder_service import CalendarReminderService, get_reminder_service
from .tools import (
    create_event,
    delete_event,
    delete_events_batch,
    get_categories,
    get_events_by_date,
    get_upcoming_events,
    update_event,
)

__all__ = [
    "CalendarManager",
    "get_calendar_manager",
    "CalendarEvent",
    "CalendarDatabase",
    "get_calendar_database",
    "CalendarReminderService",
    "get_reminder_service",
    "create_event",
    "delete_event",
    "delete_events_batch",
    "get_categories",
    "get_events_by_date",
    "get_upcoming_events",
    "update_event",
]
