"""
日程管理MCP工具函数 提供给MCP服务器调用的异步工具函数.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict

from src.utils.logging_config import get_logger

from .manager import get_calendar_manager
from .models import CalendarEvent

logger = get_logger(__name__)


async def create_event(args: Dict[str, Any]) -> str:
    """
    创建日程事件.
    """
    try:
        title = args["title"]
        start_time = args["start_time"]
        end_time = args.get("end_time")
        description = args.get("description", "")
        category = args.get("category", "默认")
        reminder_minutes = args.get("reminder_minutes", 15)

        # 如果没有结束时间，根据分类智能设置默认时长
        if not end_time:
            start_dt = datetime.fromisoformat(start_time)

            # 根据分类设置不同的默认时长
            if category in ["提醒", "休息", "站立"]:
                # 短时间活动：5分钟
                end_dt = start_dt + timedelta(minutes=5)
            elif category in ["会议", "工作"]:
                # 工作相关：1小时
                end_dt = start_dt + timedelta(hours=1)
            elif (
                "提醒" in title.lower()
                or "站立" in title.lower()
                or "休息" in title.lower()
            ):
                # 根据标题判断：短时间活动
                end_dt = start_dt + timedelta(minutes=5)
            else:
                # 默认情况：30分钟
                end_dt = start_dt + timedelta(minutes=30)

            end_time = end_dt.isoformat()

        # 验证时间格式
        datetime.fromisoformat(start_time)
        datetime.fromisoformat(end_time)

        # 创建事件
        event = CalendarEvent(
            title=title,
            start_time=start_time,
            end_time=end_time,
            description=description,
            category=category,
            reminder_minutes=reminder_minutes,
        )

        manager = get_calendar_manager()
        if manager.add_event(event):
            return json.dumps(
                {
                    "success": True,
                    "message": "日程创建成功",
                    "event_id": event.id,
                    "event": event.to_dict(),
                },
                ensure_ascii=False,
            )
        else:
            return json.dumps(
                {"success": False, "message": "日程创建失败，可能存在时间冲突"},
                ensure_ascii=False,
            )

    except Exception as e:
        logger.error(f"创建日程失败: {e}")
        return json.dumps(
            {"success": False, "message": f"创建日程失败: {str(e)}"}, ensure_ascii=False
        )


async def get_events_by_date(args: Dict[str, Any]) -> str:
    """
    按日期查询日程.
    """
    try:
        date_type = args.get("date_type", "today")  # today, tomorrow, week, month
        category = args.get("category")

        now = datetime.now()

        if date_type == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
        elif date_type == "tomorrow":
            start_date = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end_date = start_date + timedelta(days=1)
        elif date_type == "week":
            # 本周
            days_since_monday = now.weekday()
            start_date = (now - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end_date = start_date + timedelta(days=7)
        elif date_type == "month":
            # 本月
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                end_date = start_date.replace(year=now.year + 1, month=1)
            else:
                end_date = start_date.replace(month=now.month + 1)
        else:
            # 自定义日期范围
            start_date = (
                datetime.fromisoformat(args["start_date"])
                if args.get("start_date")
                else None
            )
            end_date = (
                datetime.fromisoformat(args["end_date"])
                if args.get("end_date")
                else None
            )

        manager = get_calendar_manager()
        events = manager.get_events(
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
            category=category,
        )

        # 格式化输出
        events_data = []
        for event in events:
            event_dict = event.to_dict()
            # 添加人性化时间显示
            start_dt = datetime.fromisoformat(event.start_time)
            end_dt = datetime.fromisoformat(event.end_time)
            event_dict["display_time"] = (
                f"{start_dt.strftime('%m/%d %H:%M')} - {end_dt.strftime('%H:%M')}"
            )
            events_data.append(event_dict)

        return json.dumps(
            {
                "success": True,
                "date_type": date_type,
                "total_events": len(events_data),
                "events": events_data,
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        logger.error(f"查询日程失败: {e}")
        return json.dumps(
            {"success": False, "message": f"查询日程失败: {str(e)}"}, ensure_ascii=False
        )


async def update_event(args: Dict[str, Any]) -> str:
    """
    更新日程事件.
    """
    try:
        event_id = args["event_id"]

        # 构建更新字段
        update_fields = {}
        for field in [
            "title",
            "start_time",
            "end_time",
            "description",
            "category",
            "reminder_minutes",
        ]:
            if field in args:
                update_fields[field] = args[field]

        if not update_fields:
            return json.dumps(
                {"success": False, "message": "没有提供要更新的字段"},
                ensure_ascii=False,
            )

        manager = get_calendar_manager()
        if manager.update_event(event_id, **update_fields):
            return json.dumps(
                {
                    "success": True,
                    "message": "日程更新成功",
                    "updated_fields": list(update_fields.keys()),
                },
                ensure_ascii=False,
            )
        else:
            return json.dumps(
                {"success": False, "message": "日程更新失败，事件不存在"},
                ensure_ascii=False,
            )

    except Exception as e:
        logger.error(f"更新日程失败: {e}")
        return json.dumps(
            {"success": False, "message": f"更新日程失败: {str(e)}"}, ensure_ascii=False
        )


async def delete_event(args: Dict[str, Any]) -> str:
    """
    删除日程事件.
    """
    try:
        event_id = args["event_id"]

        manager = get_calendar_manager()
        if manager.delete_event(event_id):
            return json.dumps(
                {"success": True, "message": "日程删除成功"}, ensure_ascii=False
            )
        else:
            return json.dumps(
                {"success": False, "message": "日程删除失败，事件不存在"},
                ensure_ascii=False,
            )

    except Exception as e:
        logger.error(f"删除日程失败: {e}")
        return json.dumps(
            {"success": False, "message": f"删除日程失败: {str(e)}"}, ensure_ascii=False
        )


async def delete_events_batch(args: Dict[str, Any]) -> str:
    """
    批量删除日程事件.
    """
    try:
        start_date = args.get("start_date")
        end_date = args.get("end_date")
        category = args.get("category")
        delete_all = args.get("delete_all", False)
        date_type = args.get("date_type")

        # 处理date_type参数（类似get_events_by_date）
        if date_type and not (start_date and end_date):
            now = datetime.now()

            if date_type == "today":
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date + timedelta(days=1)
            elif date_type == "tomorrow":
                start_date = (now + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                end_date = start_date + timedelta(days=1)
            elif date_type == "week":
                # 本周
                days_since_monday = now.weekday()
                start_date = (now - timedelta(days=days_since_monday)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                end_date = start_date + timedelta(days=7)
            elif date_type == "month":
                # 本月
                start_date = now.replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                )
                if now.month == 12:
                    end_date = start_date.replace(year=now.year + 1, month=1)
                else:
                    end_date = start_date.replace(month=now.month + 1)

            # 转换为ISO格式字符串
            if isinstance(start_date, datetime):
                start_date = start_date.isoformat()
            if isinstance(end_date, datetime):
                end_date = end_date.isoformat()

        manager = get_calendar_manager()
        result = manager.delete_events_batch(
            start_date=start_date,
            end_date=end_date,
            category=category,
            delete_all=delete_all,
        )

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"批量删除日程失败: {e}")
        return json.dumps(
            {"success": False, "message": f"批量删除日程失败: {str(e)}"},
            ensure_ascii=False,
        )


async def get_categories(args: Dict[str, Any]) -> str:
    """
    获取所有日程分类.
    """
    try:
        manager = get_calendar_manager()
        categories = manager.get_categories()

        return json.dumps(
            {"success": True, "categories": categories}, ensure_ascii=False
        )

    except Exception as e:
        logger.error(f"获取分类失败: {e}")
        return json.dumps(
            {"success": False, "message": f"获取分类失败: {str(e)}"}, ensure_ascii=False
        )


async def get_upcoming_events(args: Dict[str, Any]) -> str:
    """
    获取即将到来的日程（未来24小时内）
    """
    try:
        hours = args.get("hours", 24)  # 默认查询未来24小时

        now = datetime.now()
        end_time = now + timedelta(hours=hours)

        manager = get_calendar_manager()
        events = manager.get_events(
            start_date=now.isoformat(), end_date=end_time.isoformat()
        )

        # 计算提醒时间
        upcoming_events = []
        for event in events:
            event_dict = event.to_dict()
            start_dt = datetime.fromisoformat(event.start_time)

            # 计算距离开始的时间
            time_until = start_dt - now
            if time_until.total_seconds() > 0:
                hours_until = int(time_until.total_seconds() // 3600)
                minutes_until = int((time_until.total_seconds() % 3600) // 60)

                if hours_until > 0:
                    time_display = f"{hours_until}小时{minutes_until}分钟后"
                else:
                    time_display = f"{minutes_until}分钟后"

                event_dict["time_until"] = time_display
                event_dict["time_until_minutes"] = int(time_until.total_seconds() // 60)
                upcoming_events.append(event_dict)

        return json.dumps(
            {
                "success": True,
                "query_hours": hours,
                "total_events": len(upcoming_events),
                "events": upcoming_events,
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        logger.error(f"获取即将到来的日程失败: {e}")
        return json.dumps(
            {"success": False, "message": f"获取即将到来的日程失败: {str(e)}"},
            ensure_ascii=False,
        )
