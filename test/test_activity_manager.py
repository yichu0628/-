"""
活动流管理模块测试
验证活动记录与来源过滤逻辑。
"""

import os
import tempfile
import unittest

from activity_manager import ActivityManager


class ActivityManagerTestCase(unittest.TestCase):
    """活动流管理测试用例。"""

    def setUp(self):
        """
        创建临时数据库环境。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "activity.db")
        self.manager = ActivityManager(self.db_path)

    def tearDown(self):
        """
        清理临时目录。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.temp_dir.cleanup()

    def test_add_and_list_activity(self):
        """
        验证新增活动后可按倒序读取。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.manager.add_activity("manual", "记录灵感", "整理像素猫主视觉")
        activities = self.manager.get_recent_activities(limit=5)
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0]["title"], "记录灵感")
        self.assertEqual(activities[0]["details"], "整理像素猫主视觉")

    def test_filter_activity_by_source(self):
        """
        验证可按来源过滤活动。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.manager.add_activity("manual", "手动任务", "添加答辩任务")
        self.manager.add_activity("screenshot", "截图识别", "识别屏幕待办")
        manual_activities = self.manager.get_recent_activities_by_source("manual", limit=5)
        self.assertEqual(len(manual_activities), 1)
        self.assertEqual(manual_activities[0]["source"], "manual")


if __name__ == "__main__":
    unittest.main()
