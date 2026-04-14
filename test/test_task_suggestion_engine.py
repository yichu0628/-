"""
候选任务整理模块测试
验证活动流到候选待办的生成逻辑。
"""

import unittest

from task_suggestion_engine import TaskSuggestionEngine


class TaskSuggestionEngineTestCase(unittest.TestCase):
    """候选任务整理器测试用例。"""

    def setUp(self):
        """
        创建测试用整理器。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.engine = TaskSuggestionEngine()

    def test_build_candidates_from_manual_activity(self):
        """
        验证手动灵感记录可生成候选任务。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        tasks = []
        activities = [
            {"source": "manual", "title": "记录灵感", "details": "整理像素猫动效细节", "payload": {}},
        ]
        candidates = self.engine.build_candidates(tasks, activities, limit=5)
        self.assertTrue(candidates)
        self.assertEqual(candidates[0]["task"], "整理像素猫动效细节")

    def test_build_candidates_for_high_priority_without_deadline(self):
        """
        验证高优先级无截止时间任务会生成补充建议。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        tasks = [
            {"task": "完成比赛演示", "priority": 1, "deadline": None, "status": "pending"},
        ]
        candidates = self.engine.build_candidates(tasks, [], limit=5)
        self.assertTrue(any("补充明确截止时间" in item["task"] for item in candidates))

    def test_skip_duplicate_existing_task(self):
        """
        验证与现有任务重复的候选不会重复生成。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        tasks = [
            {"task": "整理像素猫动效细节", "priority": 2, "deadline": None, "status": "pending"},
        ]
        activities = [
            {"source": "manual", "title": "记录灵感", "details": "整理像素猫动效细节", "payload": {}},
        ]
        candidates = self.engine.build_candidates(tasks, activities, limit=5)
        self.assertEqual(len(candidates), 0)


if __name__ == "__main__":
    unittest.main()
