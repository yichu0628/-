"""
任务管理模块测试
验证基础增删改查行为。
"""

import os
import tempfile
import unittest

from task_manager import TaskManager


class TaskManagerTestCase(unittest.TestCase):
    """任务管理测试用例。"""

    def setUp(self):
        """
        创建临时数据库环境。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "tasks.db")
        self.manager = TaskManager(self.db_path)

    def tearDown(self):
        """
        清理临时测试目录。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.temp_dir.cleanup()

    def test_add_and_get_task(self):
        """
        验证添加任务后可正确读取。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        task = self.manager.add_task("整理答辩材料", "2026-04-15 12:00", 1)
        fetched = self.manager.get_task(task["id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["task"], "整理答辩材料")
        self.assertEqual(fetched["priority"], 1)

    def test_complete_task(self):
        """
        验证任务可被标记为完成。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        task = self.manager.add_task("完成 UI 重构")
        result = self.manager.complete_task(task["id"])
        updated = self.manager.get_task(task["id"])
        self.assertTrue(result)
        self.assertEqual(updated["status"], "completed")

    def test_delete_task(self):
        """
        验证任务删除逻辑。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        task = self.manager.add_task("删除测试任务")
        result = self.manager.delete_task(task["id"])
        self.assertTrue(result)
        self.assertIsNone(self.manager.get_task(task["id"]))


if __name__ == "__main__":
    unittest.main()
