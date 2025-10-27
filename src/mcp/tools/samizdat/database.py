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
    database_file = str(data_dir / "samizdat.db")
    logger.debug(f"使用数据库文件路径: {database_file}")
    return database_file


# 数据库文件路径 - 使用函数获取确保可写
DATABASE_FILE = _get_database_file_path()


class SamizdatDatabase:
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
                CREATE TABLE IF NOT EXISTS Entries (
                    Id TEXT PRIMARY KEY,
                    AgentName TEXT ,
                    CreatedTime TEXT ,
                    Title TEXT ,
                    Text TEXT DEFAULT ''
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS AgentState (
                    AgentName TEXT PRIMARY KEY,
                    State TEXT
                )
            """
            )            
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS AgentBody (
                    AgentName TEXT PRIMARY KEY,
                    Body TEXT
                )
            """
            )
            conn.commit()

            logger.info("Initialisation de la base de données terminée")

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
            logger.error(f"Impossible de se connecter: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def add_entry(self, entry_data: Dict[str, Any]) -> bool:
        try:
            with self._get_connection() as conn:

                conn.execute(
                    """
                    INSERT INTO Entries (
                        Id, Title, Text, CreatedTime, AgentName
                    ) VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        entry_data["Id"],
                        entry_data["Title"],
                        entry_data["Text"],
                        entry_data["CreatedTime"],
                        entry_data["AgentName"],
                    ),
                )
                conn.commit()
                logger.info(f"Ajout réussi de : {entry_data['Title']}")
                return True
        except Exception as e:
            logger.error(f"Erreur Insertion: {e}")
            return False

    def get_entriesTitle(
        self, AgentName: str = None
    ) -> List[Dict[str, Any]]:
        """
        获取事件列表.
        """
        try:
            with self._get_connection() as conn:
                query = "SELECT Id, Title, CreatedTime, AgentName, 'Pour lire le texte utiliser *get_text_by_id*' AS Text FROM Entries WHERE AgentName = ? ORDER BY CreatedTime DESC LIMIT 50"
                params = []
                params.append(AgentName)

                cursor = conn.execute(query, params)
                rows = cursor.fetchall()

                entries = []
                for row in rows:
                    entries.append(dict(row))

                return entries
        except Exception as e:
            logger.error(f"erreur db get_entriesTitle: {e}")
            return []

    def get_last_entry(
        self, AgentName: str = None
    ) -> List[Dict[str, Any]]:
        """
        获取事件列表.
        """
        try:
            with self._get_connection() as conn:
                query = "SELECT * FROM Entries WHERE AgentName = ? ORDER BY CreatedTime DESC LIMIT 1"
                params = []
                params.append(AgentName)

                cursor = conn.execute(query, params)
                rows = cursor.fetchall()

                entries = []
                for row in rows:
                    entries.append(dict(row))

                return entries

        except Exception as e:
            logger.error(f"erreur yyyy : {e}")
            return []

    def get_text_by_id(self, entry_id: str) -> str:
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT Text FROM Entries WHERE Id = ?", (entry_id,))
                text = cursor.fetchone()[0]
                return text
                
        except Exception as e:
            logger.error(f"erreur db get_text_by_id : {e}")
            return {}

        except Exception as e:
            logger.error(f"获取事件失败: {e}")
            return None

    def get_statistics(self, AgentName: str = None) -> Dict[str, Any]:
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM Entries WHERE AgentName = ?", (AgentName,))
                total_entries = cursor.fetchone()[0]

                return {"total_entries": total_entries,}
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}

    def get_agent_state(self, AgentName: str = None) -> str:
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT State FROM AgentState WHERE AgentName = ?", (AgentName,))
                state = cursor.fetchone()[0]
                return state
                
        except Exception as e:
            logger.error(f"erreur db get_agent_state : {e}")
            return {}

    def save_agent_state(self, args: Dict[str, Any] ) -> bool:
        try:
            with self._get_connection() as conn:
                conn.execute("INSERT OR REPLACE INTO AgentState (AgentName, state) VALUES (?,?)",
                    (
                        args["AgentName"],
                        args["state"],
                    ),
                )
                conn.commit()
                logger.info("db-Update State réussi")
                return True
        except Exception as e:
            logger.error(f"db-Erreur Update State: {e}")
            return False

    def get_body(self, AgentName: str = None) -> str:
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT Body FROM AgentBody WHERE AgentName = ?", (AgentName,))
                body = cursor.fetchone()[0]
                return body
                
        except Exception as e:
            logger.error(f"erreur db get_agent_state : {e}")
            return {}

    def save_body(self, args: Dict[str, Any] ) -> bool:
        try:
            with self._get_connection() as conn:
                conn.execute("INSERT OR REPLACE INTO AgentBody (AgentName, Body) VALUES (?,?)",
                    (
                        args["AgentName"],
                        args["body"],
                    ),
                )
                conn.commit()
                logger.info("db-Update State réussi")
                return True
        except Exception as e:
            logger.error(f"db-Erreur Update State: {e}")
            return False

_samizdat_db = None


def get_samizdat_database() -> SamizdatDatabase:
    """
    获取数据库实例单例.
    """
    global _samizdat_db
    if _samizdat_db is None:
        _samizdat_db = SamizdatDatabase()
    return _samizdat_db
