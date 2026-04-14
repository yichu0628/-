"""
日程整理模块测试
验证活动与任务汇总后的摘要结果。
"""

import unittest

from schedule_engine import ScheduleEngine


class ScheduleEngineTestCase(unittest.TestCase):
    """日程整理器测试用例。"""

    def setUp(self):
        """
        创建测试用日程整理器。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.engine = ScheduleEngine()

    def test_build_daily_digest_contains_sections(self):
        """
        验证整理结果包含概览、安排和洞察。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        tasks = [
            {"task": "整理比赛演示", "deadline": "2099-04-14 18:00", "priority": 1, "status": "pending"},
            {"task": "补 README", "deadline": None, "priority": 2, "status": "pending"},
        ]
        activities = [
            {"source": "screenshot", "title": "识别截图任务", "details": "新增 2 条任务", "created_at": "2099-04-14 10:00:00"},
            {"source": "manual", "title": "记录灵感", "details": "改成像素猫 UI", "created_at": "2099-04-14 09:00:00"},
        ]
        digest = self.engine.build_daily_digest(tasks, activities)
        self.assertIn("overview", digest)
        self.assertIn("schedule", digest)
        self.assertIn("insights", digest)
        self.assertTrue(digest["schedule"])
        self.assertTrue(digest["insights"])

    def test_build_daily_digest_includes_capture_insight(self):
        """
        验证自动采集活动会出现在洞察中。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        tasks = []
        activities = [
            {"source": "capture", "title": "窗口焦点变化", "details": "code | floating_app.py", "created_at": "2099-04-14 10:00:00"},
        ]
        digest = self.engine.build_daily_digest(tasks, activities)
        self.assertTrue(any("窗口采集" in line for line in digest["insights"]))
        self.assertTrue(any("最近关注窗口" in line for line in digest["insights"]))

    def test_build_daily_digest_includes_snapshot_insight(self):
        """
        验证屏幕快照活动会出现在洞察中。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        tasks = []
        activities = [
            {"source": "snapshot", "title": "记录屏幕快照", "details": "code | task_manager.py", "created_at": "2099-04-14 10:05:00"},
        ]
        digest = self.engine.build_daily_digest(tasks, activities)
        self.assertTrue(any("屏幕快照" in line for line in digest["insights"]))
        self.assertTrue(any("最近已记录屏幕快照" in line for line in digest["insights"]))

    def test_build_daily_digest_without_data(self):
        """
        验证空数据下也能返回默认摘要。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        digest = self.engine.build_daily_digest([], [])
        self.assertTrue(any("没有待处理事项" in line for line in digest["schedule"]))
        self.assertTrue(any("没有活动记录" in line for line in digest["insights"]))


if __name__ == "__main__":
    unittest.main()
