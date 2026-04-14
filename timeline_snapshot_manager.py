"""
时间轴快照管理模块
负责低频记录屏幕快照、生成缩略图并清理旧文件。
"""

import os
import time
import uuid
from typing import Dict, Optional, Tuple

from PIL import Image, ImageGrab


class TimelineSnapshotManager:
    """时间轴快照管理器，负责屏幕快照和缩略图生成。"""

    def __init__(
        self,
        snapshot_dir: str = "./timeline_snapshots",
        thumbnail_size: Tuple[int, int] = (320, 180),
        max_snapshots: int = 24,
        min_interval_seconds: int = 20,
    ):
        """
        初始化快照管理器。

        Args:
            snapshot_dir: str - 快照存储目录。
            thumbnail_size: Tuple[int, int] - 缩略图尺寸。
            max_snapshots: int - 保留的快照数量上限。
            min_interval_seconds: int - 同一上下文最短抓图间隔。

        Returns:
            None - 无返回值。
        """
        self.snapshot_dir = snapshot_dir
        self.thumbnail_size = thumbnail_size
        self.max_snapshots = max(4, int(max_snapshots))
        self.min_interval_seconds = max(5, int(min_interval_seconds))
        self._last_signature = ""
        self._last_captured_at = 0.0
        os.makedirs(self.snapshot_dir, exist_ok=True)

    def capture_snapshot(self, signature: str, window_title: str, process_name: str) -> Optional[Dict[str, str]]:
        """
        按当前上下文抓取一张屏幕快照。

        Args:
            signature: str - 当前上下文签名。
            window_title: str - 当前窗口标题。
            process_name: str - 当前进程名称。

        Returns:
            Optional[Dict[str, str]] - 成功时返回快照信息，跳过或失败返回 None。
        """
        if not self._should_capture(signature):
            return None

        image = self._grab_screen()
        if image is None:
            return None

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        token = uuid.uuid4().hex[:8]
        image_name = f"snapshot_{timestamp}_{token}.png"
        thumb_name = f"thumb_{timestamp}_{token}.png"
        image_path = os.path.join(self.snapshot_dir, image_name)
        thumb_path = os.path.join(self.snapshot_dir, thumb_name)

        image.save(image_path, "PNG")
        thumbnail = image.copy()
        thumbnail.thumbnail(self.thumbnail_size)
        thumbnail.save(thumb_path, "PNG")

        self._last_signature = signature
        self._last_captured_at = time.time()
        self._cleanup_old_snapshots()

        return {
            "image_path": image_path,
            "thumbnail_path": thumb_path,
            "window_title": window_title,
            "process_name": process_name,
            "signature": signature,
            "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _should_capture(self, signature: str) -> bool:
        """
        判断当前上下文是否应抓图。

        Args:
            signature: str - 当前上下文签名。

        Returns:
            bool - 是否执行抓图。
        """
        if not signature:
            return False

        if signature != self._last_signature:
            return True

        return time.time() - self._last_captured_at >= self.min_interval_seconds

    def _grab_screen(self) -> Optional[Image.Image]:
        """
        获取当前屏幕图像。

        Args:
            无。

        Returns:
            Optional[Image.Image] - 抓图结果。
        """
        try:
            return ImageGrab.grab()
        except Exception:
            return None

    def _cleanup_old_snapshots(self):
        """
        清理超出上限的旧快照文件。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        files = []
        for name in os.listdir(self.snapshot_dir):
            if not name.endswith(".png"):
                continue
            full_path = os.path.join(self.snapshot_dir, name)
            files.append((os.path.getmtime(full_path), full_path))

        files.sort(reverse=True)
        for _, stale_path in files[self.max_snapshots * 2:]:
            try:
                os.remove(stale_path)
            except OSError:
                continue
