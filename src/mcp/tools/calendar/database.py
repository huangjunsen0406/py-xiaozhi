"""
日程管理SQLite数据库操作模块.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.utils.logging_config import get_logger
from src.utils.resource_finder import get_user_data_dir

logger = get_logger(__name__)


def _get_database_file_path() -> str:
    """
    获取数据库文件路径，确保在可写目录中.
    """
    data_dir = get_user_data_dir()
    database_file = str(data_dir / "calendar.db")
    logger.debug(f"使用数据库文件路径: {database_file}")
    return database_file


# 数据库文件路径 - 使用函数获取确保可写
DATABASE_FILE = _get_database_file_path()


class CalendarDatabase:
    """
    日程管理数据库操作类.
    """

    def __init__(self):
        self.db_file = DATABASE_FILE
        self._ensure_database()

    def _ensure_database(self):
        """
        确保数据库和表存在.
        """
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)

        with self._get_connection() as conn:
            # 创建事件表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    category TEXT DEFAULT '默认',
                    reminder_minutes INTEGER DEFAULT 15,
                    reminder_time TEXT,
                    reminder_sent BOOLEAN DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """
            )

            # 创建分类表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            """
            )

            # 插入默认分类
            default_categories = ["默认", "工作", "个人", "会议", "提醒"]
            for category in default_categories:
                conn.execute(
                    "INSERT OR IGNORE INTO categories (name) VALUES (?)", (category,)
                )

            conn.commit()

            # 检查并添加新字段（数据库升级）
            self._upgrade_database(conn)

            logger.info("数据库初始化完成")

    @contextmanager
    def _get_connection(self):
        """
        获取数据库连接的上下文管理器.
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row  # 使结果可以按列名访问
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def add_event(self, event_data: Dict[str, Any]) -> bool:
        """
        添加事件.
        """
        try:
            with self._get_connection() as conn:
                # 检查时间冲突
                if self._has_conflict(conn, event_data):
                    return False

                conn.execute(
                    """
                    INSERT INTO events (
                        id, title, start_time, end_time, description,
                        category, reminder_minutes, reminder_time, reminder_sent,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        event_data["id"],
                        event_data["title"],
                        event_data["start_time"],
                        event_data["end_time"],
                        event_data["description"],
                        event_data["category"],
                        event_data["reminder_minutes"],
                        event_data.get("reminder_time"),
                        event_data.get("reminder_sent", False),
                        event_data["created_at"],
                        event_data["updated_at"],
                    ),
                )
                conn.commit()
                logger.info(f"添加事件成功: {event_data['title']}")
                return True
        except Exception as e:
            logger.error(f"添加事件失败: {e}")
            return False

    def get_events(
        self, start_date: str = None, end_date: str = None, category: str = None
    ) -> List[Dict[str, Any]]:
        """
        获取事件列表.
        """
        try:
            with self._get_connection() as conn:
                query = "SELECT * FROM events WHERE 1=1"
                params = []

                if start_date:
                    query += " AND start_time >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND start_time <= ?"
                    params.append(end_date)

                if category:
                    query += " AND category = ?"
                    params.append(category)

                query += " ORDER BY start_time"

                cursor = conn.execute(query, params)
                rows = cursor.fetchall()

                events = []
                for row in rows:
                    events.append(dict(row))

                return events
        except Exception as e:
            logger.error(f"获取事件失败: {e}")
            return []

    def update_event(self, event_id: str, **kwargs) -> bool:
        """
        更新事件.
        """
        try:
            with self._get_connection() as conn:
                # 构建更新查询
                set_clauses = []
                params = []

                for key, value in kwargs.items():
                    if key in [
                        "title",
                        "start_time",
                        "end_time",
                        "description",
                        "category",
                        "reminder_minutes",
                    ]:
                        set_clauses.append(f"{key} = ?")
                        params.append(value)

                if not set_clauses:
                    return False

                # 添加更新时间
                set_clauses.append("updated_at = ?")
                params.append(datetime.now().isoformat())
                params.append(event_id)

                query = f"UPDATE events SET {', '.join(set_clauses)} WHERE id = ?"

                cursor = conn.execute(query, params)
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"更新事件成功: {event_id}")
                    return True
                else:
                    logger.warning(f"事件不存在: {event_id}")
                    return False
        except Exception as e:
            logger.error(f"更新事件失败: {e}")
            return False

    def delete_event(self, event_id: str) -> bool:
        """
        删除事件.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"删除事件成功: {event_id}")
                    return True
                else:
                    logger.warning(f"事件不存在: {event_id}")
                    return False
        except Exception as e:
            logger.error(f"删除事件失败: {e}")
            return False

    def delete_events_batch(
        self,
        start_date: str = None,
        end_date: str = None,
        category: str = None,
        delete_all: bool = False,
    ) -> Dict[str, Any]:
        """批量删除事件.

        Args:
            start_date: 开始日期，ISO格式
            end_date: 结束日期，ISO格式
            category: 分类筛选
            delete_all: 是否删除所有事件

        Returns:
            包含删除结果的字典
        """
        try:
            with self._get_connection() as conn:
                if delete_all:
                    # 删除所有事件
                    cursor = conn.execute("SELECT COUNT(*) FROM events")
                    total_count = cursor.fetchone()[0]

                    if total_count == 0:
                        return {
                            "success": True,
                            "deleted_count": 0,
                            "message": "没有事件需要删除",
                        }

                    cursor = conn.execute("DELETE FROM events")
                    conn.commit()

                    logger.info(f"删除所有事件成功，共删除 {total_count} 个事件")
                    return {
                        "success": True,
                        "deleted_count": total_count,
                        "message": f"成功删除所有 {total_count} 个事件",
                    }

                else:
                    # 按条件删除事件
                    # 首先查询符合条件的事件
                    query = "SELECT id, title FROM events WHERE 1=1"
                    params = []

                    if start_date:
                        query += " AND start_time >= ?"
                        params.append(start_date)

                    if end_date:
                        query += " AND start_time <= ?"
                        params.append(end_date)

                    if category:
                        query += " AND category = ?"
                        params.append(category)

                    cursor = conn.execute(query, params)
                    events_to_delete = cursor.fetchall()

                    if not events_to_delete:
                        return {
                            "success": True,
                            "deleted_count": 0,
                            "message": "没有符合条件的事件需要删除",
                        }

                    # 执行删除
                    delete_query = "DELETE FROM events WHERE 1=1"
                    delete_params = []

                    if start_date:
                        delete_query += " AND start_time >= ?"
                        delete_params.append(start_date)

                    if end_date:
                        delete_query += " AND start_time <= ?"
                        delete_params.append(end_date)

                    if category:
                        delete_query += " AND category = ?"
                        delete_params.append(category)

                    cursor = conn.execute(delete_query, delete_params)
                    deleted_count = cursor.rowcount
                    conn.commit()

                    # 记录删除的事件标题
                    deleted_titles = [event[1] for event in events_to_delete]
                    logger.info(
                        f"批量删除事件成功，共删除 {deleted_count} 个事件: "
                        f"{', '.join(deleted_titles[:3])}"
                        f"{'...' if len(deleted_titles) > 3 else ''}"
                    )

                    return {
                        "success": True,
                        "deleted_count": deleted_count,
                        "deleted_titles": deleted_titles,
                        "message": f"成功删除 {deleted_count} 个事件",
                    }

        except Exception as e:
            logger.error(f"批量删除事件失败: {e}")
            return {
                "success": False,
                "deleted_count": 0,
                "message": f"批量删除失败: {str(e)}",
            }

    def get_event_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        根据ID获取事件.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,))
                row = cursor.fetchone()

                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"获取事件失败: {e}")
            return None

    def get_categories(self) -> List[str]:
        """
        获取所有分类.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT name FROM categories ORDER BY name")
                rows = cursor.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"获取分类失败: {e}")
            return ["默认"]

    def add_category(self, category_name: str) -> bool:
        """
        添加新分类.
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO categories (name) VALUES (?)",
                    (category_name,),
                )
                conn.commit()
                logger.info(f"添加分类成功: {category_name}")
                return True
        except Exception as e:
            logger.error(f"添加分类失败: {e}")
            return False

    def delete_category(self, category_name: str) -> bool:
        """
        删除分类（如果没有事件使用）
        """
        try:
            with self._get_connection() as conn:
                # 检查是否有事件使用该分类
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM events WHERE category = ?", (category_name,)
                )
                count = cursor.fetchone()[0]

                if count > 0:
                    logger.warning(f"分类 '{category_name}' 正在使用中，无法删除")
                    return False

                cursor = conn.execute(
                    "DELETE FROM categories WHERE name = ?", (category_name,)
                )
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"删除分类成功: {category_name}")
                    return True
                else:
                    logger.warning(f"分类不存在: {category_name}")
                    return False
        except Exception as e:
            logger.error(f"删除分类失败: {e}")
            return False

    def _has_conflict(
        self, conn: sqlite3.Connection, event_data: Dict[str, Any]
    ) -> bool:
        """
        检查时间冲突.
        """
        cursor = conn.execute(
            """
            SELECT title FROM events
            WHERE id != ? AND (
                (start_time < ? AND end_time > ?) OR
                (start_time < ? AND end_time > ?)
            )
        """,
            (
                event_data["id"],
                event_data["end_time"],
                event_data["start_time"],
                event_data["start_time"],
                event_data["end_time"],
            ),
        )

        conflicting_events = cursor.fetchall()

        if conflicting_events:
            for event in conflicting_events:
                logger.warning(f"时间冲突: 与事件 '{event[0]}' 冲突")
            return True

        return False

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息.
        """
        try:
            with self._get_connection() as conn:
                # 总事件数
                cursor = conn.execute("SELECT COUNT(*) FROM events")
                total_events = cursor.fetchone()[0]

                # 按分类统计
                cursor = conn.execute(
                    """
                    SELECT category, COUNT(*)
                    FROM events
                    GROUP BY category
                    ORDER BY COUNT(*) DESC
                """
                )
                category_stats = dict(cursor.fetchall())

                # 今天的事件数
                today = datetime.now().strftime("%Y-%m-%d")
                cursor = conn.execute(
                    """
                    SELECT COUNT(*) FROM events
                    WHERE date(start_time) = ?
                """,
                    (today,),
                )
                today_events = cursor.fetchone()[0]

                return {
                    "total_events": total_events,
                    "category_stats": category_stats,
                    "today_events": today_events,
                }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}

    def migrate_from_json(self, json_file_path: str) -> bool:
        """
        从JSON文件迁移数据.
        """
        try:
            import json

            if not os.path.exists(json_file_path):
                logger.info("JSON文件不存在，跳过迁移")
                return True

            with open(json_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            events_data = data.get("events", [])
            categories_data = data.get("categories", [])

            with self._get_connection() as conn:
                # 迁移分类
                for category in categories_data:
                    conn.execute(
                        "INSERT OR IGNORE INTO categories (name) VALUES (?)",
                        (category,),
                    )

                # 迁移事件
                for event_data in events_data:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO events (
                            id, title, start_time, end_time, description,
                            category, reminder_minutes, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            event_data["id"],
                            event_data["title"],
                            event_data["start_time"],
                            event_data["end_time"],
                            event_data.get("description", ""),
                            event_data.get("category", "默认"),
                            event_data.get("reminder_minutes", 15),
                            event_data.get("created_at", datetime.now().isoformat()),
                            event_data.get("updated_at", datetime.now().isoformat()),
                        ),
                    )

                conn.commit()
                logger.info(
                    f"成功迁移 {len(events_data)} 个事件和 {len(categories_data)} 个分类"
                )
                return True

        except Exception as e:
            logger.error(f"数据迁移失败: {e}")
            return False

    def _upgrade_database(self, conn: sqlite3.Connection):
        """
        升级数据库结构.
        """
        try:
            # 检查是否存在新字段
            cursor = conn.execute("PRAGMA table_info(events)")
            columns = [col[1] for col in cursor.fetchall()]

            # 添加reminder_time字段
            if "reminder_time" not in columns:
                conn.execute("ALTER TABLE events ADD COLUMN reminder_time TEXT")
                logger.info("已添加reminder_time字段")

            # 添加reminder_sent字段
            if "reminder_sent" not in columns:
                conn.execute(
                    "ALTER TABLE events ADD COLUMN reminder_sent BOOLEAN DEFAULT 0"
                )
                logger.info("已添加reminder_sent字段")

            # 为现有事件计算并设置reminder_time
            cursor = conn.execute(
                "SELECT id, start_time, reminder_minutes "
                "FROM events WHERE reminder_time IS NULL"
            )
            events_to_update = cursor.fetchall()

            for event in events_to_update:
                event_id, start_time, reminder_minutes = event
                try:
                    from datetime import timedelta

                    start_dt = datetime.fromisoformat(start_time)
                    reminder_dt = start_dt - timedelta(minutes=reminder_minutes)

                    conn.execute(
                        "UPDATE events SET reminder_time = ? WHERE id = ?",
                        (reminder_dt.isoformat(), event_id),
                    )
                except Exception as e:
                    logger.warning(f"计算事件{event_id}的提醒时间失败: {e}")

            if events_to_update:
                logger.info(f"已为{len(events_to_update)}个现有事件设置提醒时间")

            conn.commit()

        except Exception as e:
            logger.error(f"数据库升级失败: {e}", exc_info=True)


# 全局数据库实例
_calendar_db = None


def get_calendar_database() -> CalendarDatabase:
    """
    获取数据库实例单例.
    """
    global _calendar_db
    if _calendar_db is None:
        _calendar_db = CalendarDatabase()
    return _calendar_db
