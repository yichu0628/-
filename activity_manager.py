"""
活动流管理模块
负责记录识别来源、用户操作与系统整理结果。
"""

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


class ActivityManager:
    """活动流管理器，负责本地活动日志的存储与读取。"""

    def __init__(self, db_path: str = "./glance_tasks.db"):
        """
        初始化活动流管理器。

        Args:
            db_path: str - SQLite 数据库文件路径。

        Returns:
            None - 无返回值。
        """
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """
        初始化活动流数据表。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_logs (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                details TEXT,
                payload TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()

    def _generate_id(self) -> str:
        """
        生成唯一活动 ID。

        Args:
            无。

        Returns:
            str - 唯一活动标识。
        """
        return str(uuid.uuid4())

    def add_activity(
        self,
        source: str,
        title: str,
        details: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        新增一条活动记录。

        Args:
            source: str - 活动来源，例如 screenshot、voice、manual。
            title: str - 活动标题。
            details: str - 活动详情。
            payload: Optional[Dict[str, Any]] - 结构化附加数据。

        Returns:
            Dict[str, Any] - 新增后的活动对象。
        """
        activity = {
            "id": self._generate_id(),
            "source": source,
            "title": title,
            "details": details,
            "payload": payload or {},
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO activity_logs (id, source, title, details, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                activity["id"],
                activity["source"],
                activity["title"],
                activity["details"],
                json.dumps(activity["payload"], ensure_ascii=False),
                activity["created_at"],
            ),
        )
        conn.commit()
        conn.close()
        return activity

    def get_recent_activities(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取最近活动列表。

        Args:
            limit: int - 返回条目数量上限。

        Returns:
            List[Dict[str, Any]] - 活动列表，按时间倒序排列。
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, source, title, details, payload, created_at
            FROM activity_logs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (max(1, limit),),
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_dict(row) for row in rows]

    def get_recent_activities_by_source(self, source: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        按来源获取最近活动列表。

        Args:
            source: str - 活动来源。
            limit: int - 返回条目数量上限。

        Returns:
            List[Dict[str, Any]] - 活动列表。
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, source, title, details, payload, created_at
            FROM activity_logs
            WHERE source = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (source, max(1, limit)),
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_dict(row) for row in rows]

    def _row_to_dict(self, row: tuple) -> Dict[str, Any]:
        """
        将数据库行转为活动字典。

        Args:
            row: tuple - 数据库查询结果行。

        Returns:
            Dict[str, Any] - 活动对象。
        """
        payload_text = row[4] or "{}"
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            payload = {}

        return {
            "id": row[0],
            "source": row[1],
            "title": row[2],
            "details": row[3] or "",
            "payload": payload,
            "created_at": row[5],
        }
