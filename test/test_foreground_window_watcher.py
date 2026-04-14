"""
前台窗口采集模块测试
验证窗口快照去重与重复发出策略。
"""

import unittest
from unittest.mock import patch

from foreground_window_watcher import ForegroundWindowWatcher


class ForegroundWindowWatcherTestCase(unittest.TestCase):
    """前台窗口采集器测试用例。"""

    def setUp(self):
        """
        创建测试用监听器实例。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.watcher = ForegroundWindowWatcher(poll_interval_seconds=6)

    def test_emit_when_signature_changes(self):
        """
        验证窗口签名变化时会触发事件。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        snapshot = {
            "signature": "code|README.md",
            "window_title": "README.md - VS Code",
        }
        self.assertTrue(self.watcher._should_emit_snapshot(snapshot))

    def test_skip_short_title(self):
        """
        验证过短窗口标题不会触发事件。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        snapshot = {
            "signature": "code|x",
            "window_title": "x",
        }
        self.assertFalse(self.watcher._should_emit_snapshot(snapshot))

    def test_repeat_signature_requires_interval(self):
        """
        验证相同窗口需达到时间间隔后才会再次发出。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.watcher._last_signature = "code|README.md"
        self.watcher._last_emitted_at = 100.0
        snapshot = {
            "signature": "code|README.md",
            "window_title": "README.md - VS Code",
        }

        with patch("foreground_window_watcher.time.time", return_value=120.0):
            self.assertFalse(self.watcher._should_emit_snapshot(snapshot))

        with patch("foreground_window_watcher.time.time", return_value=140.0):
            self.assertTrue(self.watcher._should_emit_snapshot(snapshot))


if __name__ == "__main__":
    unittest.main()
