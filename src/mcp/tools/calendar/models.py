"""
日程管理数据模型.
"""

import uuid
from datetime import datetime
from typing import Any, Dict


class CalendarEvent:
    """
    日程事件数据模型.
    """

    def __init__(
        self,
        title: str,
        start_time: str,
        end_time: str,
        description: str = "",
        category: str = "默认",
        reminder_minutes: int = 15,
        event_id: str = None,
    ):
        self.id = event_id or str(uuid.uuid4())
        self.title = title
        self.start_time = start_time  # ISO格式: "2024-01-01T10:00:00"
        self.end_time = end_time
        self.description = description
        self.category = category
        self.reminder_minutes = reminder_minutes
        self.reminder_time = self._calculate_reminder_time()
        self.reminder_sent = False
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典.
        """
        return {
            "id": self.id,
            "title": self.title,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "description": self.description,
            "category": self.category,
            "reminder_minutes": self.reminder_minutes,
            "reminder_time": self.reminder_time,
            "reminder_sent": self.reminder_sent,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalendarEvent":
        """
        从字典创建事件.
        """
        event = cls(
            title=data["title"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            description=data.get("description", ""),
            category=data.get("category", "默认"),
            reminder_minutes=data.get("reminder_minutes", 15),
            event_id=data["id"],
        )
        event.reminder_time = data.get("reminder_time", event.reminder_time)
        event.reminder_sent = data.get("reminder_sent", False)
        event.created_at = data.get("created_at", event.created_at)
        event.updated_at = data.get("updated_at", event.updated_at)
        return event

    def _calculate_reminder_time(self) -> str:
        """
        计算提醒时间.
        """
        try:
            from datetime import timedelta

            start_dt = datetime.fromisoformat(self.start_time)
            reminder_dt = start_dt - timedelta(minutes=self.reminder_minutes)
            return reminder_dt.isoformat()
        except Exception:
            return self.start_time  # 如果计算失败，返回开始时间
