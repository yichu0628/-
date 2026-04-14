"""
任务管理模块
使用 SQLite 本地存储任务数据
"""

import os
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import sqlite3


class TaskManager:
    """任务管理器，负责本地任务存储和业务逻辑"""

    def __init__(self, db_path: str = "./glance_tasks.db"):
        """
        初始化任务管理器

        Args:
            db_path: SQLite 数据库文件路径
        """
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                deadline TEXT,
                priority INTEGER DEFAULT 2,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()
        print(f"[数据库] 初始化完成: {self.db_path}")

    def _generate_id(self) -> str:
        """生成唯一任务 ID"""
        return str(uuid.uuid4())

    def add_task(
        self,
        task: str,
        deadline: Optional[str] = None,
        priority: int = 2
    ) -> Dict[str, Any]:
        """
        添加新任务

        Args:
            task: 任务描述
            deadline: 截止时间，格式 "YYYY-MM-DD HH:MM"
            priority: 优先级 1-3

        Returns:
            新创建的任务对象
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task_id = self._generate_id()

        task_obj = {
            "id": task_id,
            "task": task,
            "deadline": deadline,
            "priority": max(1, min(3, priority)),
            "status": "pending",
            "created_at": now,
            "updated_at": now
        }

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO tasks (id, task, deadline, priority, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            task_obj["id"],
            task_obj["task"],
            task_obj["deadline"],
            task_obj["priority"],
            task_obj["status"],
            task_obj["created_at"],
            task_obj["updated_at"]
        ))

        conn.commit()
        conn.close()

        print(f"[任务] 添加成功: {task}")
        return task_obj

    def add_tasks_from_llm(self, llm_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从 LLM 解析结果批量添加任务

        Args:
            llm_tasks: LLM 返回的任务列表

        Returns:
            新创建的任务列表
        """
        added_tasks = []
        for llm_task in llm_tasks:
            task_obj = self.add_task(
                task=llm_task.get("task", "未命名任务"),
                deadline=llm_task.get("deadline"),
                priority=llm_task.get("priority", 2)
            )
            added_tasks.append(task_obj)

        return added_tasks

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取单个任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_dict(row)
        return None

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """获取所有任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tasks ORDER BY priority ASC, deadline ASC")
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_dict(row) for row in rows]

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """获取所有待办任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM tasks
            WHERE status = 'pending'
            ORDER BY priority ASC, deadline ASC
        """)
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_dict(row) for row in rows]

    def get_upcoming_tasks(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        获取即将到期的任务

        Args:
            hours: 未来多少小时内到期的任务

        Returns:
            即将到期的任务列表
        """
        now = datetime.now()
        future = now + timedelta(hours=hours)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM tasks
            WHERE status = 'pending' AND deadline IS NOT NULL
            ORDER BY deadline ASC
        """)
        rows = cursor.fetchall()
        conn.close()

        upcoming = []
        for row in rows:
            task = self._row_to_dict(row)
            if task["deadline"]:
                try:
                    deadline_dt = datetime.strptime(task["deadline"], "%Y-%m-%d %H:%M")
                    if now <= deadline_dt <= future:
                        upcoming.append(task)
                except ValueError:
                    pass

        return upcoming

    def get_today_tasks(self) -> List[Dict[str, Any]]:
        """获取今日截止的任务"""
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM tasks
            WHERE status = 'pending' AND deadline IS NOT NULL
            ORDER BY deadline ASC
        """)
        rows = cursor.fetchall()
        conn.close()

        today_tasks = []
        for row in rows:
            task = self._row_to_dict(row)
            if task["deadline"]:
                try:
                    deadline_dt = datetime.strptime(task["deadline"], "%Y-%m-%d %H:%M")
                    if today <= deadline_dt.date() < tomorrow:
                        today_tasks.append(task)
                except ValueError:
                    pass

        return today_tasks

    def complete_task(self, task_id: str) -> bool:
        """标记任务为已完成"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE tasks
            SET status = 'completed', updated_at = ?
            WHERE id = ?
        """, (now, task_id))

        affected = cursor.rowcount
        conn.commit()
        conn.close()

        if affected > 0:
            print(f"[任务] 已完成: {task_id}")
            return True
        return False

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

        affected = cursor.rowcount
        conn.commit()
        conn.close()

        if affected > 0:
            print(f"[任务] 已删除: {task_id}")
            return True
        return False

    def update_task(
        self,
        task_id: str,
        task: Optional[str] = None,
        deadline: Optional[str] = None,
        priority: Optional[int] = None,
        status: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """更新任务"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        updates = []
        params = []

        if task is not None:
            updates.append("task = ?")
            params.append(task)
        if deadline is not None:
            updates.append("deadline = ?")
            params.append(deadline)
        if priority is not None:
            updates.append("priority = ?")
            params.append(max(1, min(3, priority)))
        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if not updates:
            return self.get_task(task_id)

        updates.append("updated_at = ?")
        params.append(now)
        params.append(task_id)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(f"""
            UPDATE tasks
            SET {', '.join(updates)}
            WHERE id = ?
        """, params)

        conn.commit()
        conn.close()

        print(f"[任务] 已更新: {task_id}")
        return self.get_task(task_id)

    def get_tasks_for_sync(self) -> List[Dict[str, Any]]:
        """获取用于 MQTT 同步的任务列表（仅待办任务）"""
        return self.get_pending_tasks()

    def clear_completed_tasks(self) -> int:
        """清除所有已完成的任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM tasks WHERE status = 'completed'")
        affected = cursor.rowcount
        conn.commit()
        conn.close()

        print(f"[任务] 已清除 {affected} 个已完成任务")
        return affected

    def _row_to_dict(self, row: tuple) -> Dict[str, Any]:
        """将数据库行转换为字典"""
        return {
            "id": row[0],
            "task": row[1],
            "deadline": row[2],
            "priority": row[3],
            "status": row[4],
            "created_at": row[5],
            "updated_at": row[6]
        }


# 测试代码
if __name__ == "__main__":
    manager = TaskManager("./test_tasks.db")

    # 添加测试任务
    task1 = manager.add_task(
        task="完成项目文档",
        deadline="2026-05-12 18:00",
        priority=1
    )
    print(f"添加任务: {task1}")

    # 获取所有任务
    all_tasks = manager.get_all_tasks()
    print(f"所有任务: {json.dumps(all_tasks, ensure_ascii=False, indent=2)}")

    # 获取今日任务
    today = manager.get_today_tasks()
    print(f"今日任务: {today}")
