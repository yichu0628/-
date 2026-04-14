"""
时间轴快照管理模块测试
验证快照落盘与重复上下文节流逻辑。
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from timeline_snapshot_manager import TimelineSnapshotManager


class TimelineSnapshotManagerTestCase(unittest.TestCase):
    """时间轴快照管理器测试用例。"""

    def setUp(self):
        """
        创建测试用快照管理器。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manager = TimelineSnapshotManager(
            snapshot_dir=self.temp_dir.name,
            thumbnail_size=(120, 80),
            max_snapshots=6,
            min_interval_seconds=20,
        )

    def tearDown(self):
        """
        清理临时目录。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.temp_dir.cleanup()

    def test_capture_snapshot_creates_files(self):
        """
        验证抓取快照后会生成原图和缩略图。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        with patch.object(self.manager, "_grab_screen", return_value=Image.new("RGB", (640, 360), "#123456")):
            payload = self.manager.capture_snapshot("code|README", "README.md - VS Code", "code")

        self.assertIsNotNone(payload)
        self.assertTrue(os.path.exists(payload["image_path"]))
        self.assertTrue(os.path.exists(payload["thumbnail_path"]))

    def test_skip_repeated_signature_within_interval(self):
        """
        验证同一上下文在节流时间内不会重复抓图。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        with patch.object(self.manager, "_grab_screen", return_value=Image.new("RGB", (640, 360), "#654321")):
            first = self.manager.capture_snapshot("code|README", "README.md - VS Code", "code")
            second = self.manager.capture_snapshot("code|README", "README.md - VS Code", "code")

        self.assertIsNotNone(first)
        self.assertIsNone(second)


if __name__ == "__main__":
    unittest.main()
