"""
截图监听模块
支持快捷键截图和剪贴板截图监听
"""

import os
import time
import threading
from datetime import datetime
from typing import Callable, Optional

from PIL import ImageGrab, Image
import pynput.keyboard as keyboard
import pyperclip


class ScreenshotListener:
    """截图监听器，支持快捷键触发和剪贴板监听"""

    def __init__(
        self,
        hotkey: str = "ctrl+shift+s",
        temp_dir: str = "./temp_screenshots",
        watch_clipboard: bool = True,
        on_screenshot: Optional[Callable[[str], None]] = None
    ):
        """
        初始化截图监听器

        Args:
            hotkey: 触发截图的快捷键，格式如 "ctrl+shift+s"
            temp_dir: 截图临时保存目录
            watch_clipboard: 是否监听剪贴板截图
            on_screenshot: 截图回调函数，接收截图文件路径
        """
        self.hotkey = hotkey
        self.temp_dir = temp_dir
        self.watch_clipboard = watch_clipboard
        self.on_screenshot = on_screenshot

        self._running = False
        self._keyboard_listener = None
        self._clipboard_thread = None
        self._last_clipboard_hash = None

        # 确保临时目录存在
        os.makedirs(temp_dir, exist_ok=True)

    def _parse_hotkey(self, hotkey_str: str) -> keyboard.HotKey:
        """解析快捷键字符串为 pynput HotKey 对象"""
        parts = hotkey_str.lower().split("+")
        keys = []
        for part in parts:
            part = part.strip()
            if part == "ctrl":
                keys.append(keyboard.Key.ctrl)
            elif part == "alt":
                keys.append(keyboard.Key.alt)
            elif part == "shift":
                keys.append(keyboard.Key.shift)
            elif part == "cmd" or part == "win":
                keys.append(keyboard.Key.cmd)
            elif len(part) == 1:
                keys.append(keyboard.KeyCode.from_char(part))
            else:
                # 处理功能键如 f1, f2 等
                try:
                    keys.append(getattr(keyboard.Key, part))
                except AttributeError:
                    print(f"[警告] 无法识别的按键: {part}")

        return keyboard.HotKey(keys, self._on_hotkey_triggered)

    def _on_hotkey_triggered(self):
        """快捷键触发时的回调"""
        print(f"[截图] 检测到快捷键 {self.hotkey}，正在截图...")
        self._take_screenshot()

    def _take_screenshot(self) -> Optional[str]:
        """执行截图并保存到临时目录"""
        try:
            # 截取全屏
            screenshot = ImageGrab.grab()

            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = os.path.join(self.temp_dir, filename)

            # 保存截图
            screenshot.save(filepath, "PNG")
            print(f"[截图] 已保存: {filepath}")

            # 调用回调
            if self.on_screenshot:
                self.on_screenshot(filepath)

            return filepath

        except Exception as e:
            print(f"[错误] 截图失败: {e}")
            return None

    def _get_image_hash(self, image: Image.Image) -> str:
        """计算图像的简单哈希值用于比较"""
        # 缩小图像并转为灰度，计算像素和作为简单哈希
        small = image.resize((32, 32)).convert("L")
        return str(sum(small.getdata()))

    def _clipboard_watcher(self):
        """剪贴板监听线程"""
        print("[剪贴板] 开始监听剪贴板截图...")

        while self._running:
            try:
                # 检查剪贴板是否有图片
                clipboard_content = pyperclip.paste()

                # 尝试从剪贴板获取图片
                try:
                    img = ImageGrab.grabclipboard()

                    if img is not None:
                        # 计算哈希避免重复处理
                        current_hash = self._get_image_hash(img)

                        if current_hash != self._last_clipboard_hash:
                            self._last_clipboard_hash = current_hash

                            # 保存剪贴板图片
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"clipboard_{timestamp}.png"
                            filepath = os.path.join(self.temp_dir, filename)

                            img.save(filepath, "PNG")
                            print(f"[剪贴板] 检测到新截图: {filepath}")

                            if self.on_screenshot:
                                self.on_screenshot(filepath)

                except Exception:
                    # 剪贴板中没有图片，忽略
                    pass

            except Exception as e:
                print(f"[剪贴板] 监听出错: {e}")

            # 每0.5秒检查一次
            time.sleep(0.5)

    def start(self):
        """启动截图监听"""
        if self._running:
            print("[截图监听] 已经在运行中")
            return

        self._running = True
        print(f"[截图监听] 启动中，快捷键: {self.hotkey}")

        # 启动快捷键监听
        hotkey_obj = self._parse_hotkey(self.hotkey)

        def on_press(key):
            try:
                hotkey_obj.press(key)
            except AttributeError:
                pass

        def on_release(key):
            try:
                hotkey_obj.release(key)
            except AttributeError:
                pass

        self._keyboard_listener = keyboard.Listener(
            on_press=on_press,
            on_release=on_release
        )
        self._keyboard_listener.start()

        # 启动剪贴板监听
        if self.watch_clipboard:
            self._clipboard_thread = threading.Thread(
                target=self._clipboard_watcher,
                daemon=True
            )
            self._clipboard_thread.start()

        print("[截图监听] 已启动，按快捷键或复制截图以触发")

    def stop(self):
        """停止截图监听"""
        self._running = False

        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None

        print("[截图监听] 已停止")

    def is_running(self) -> bool:
        """检查监听器是否在运行"""
        return self._running


def take_manual_screenshot(temp_dir: str = "./temp_screenshots") -> Optional[str]:
    """
    手动截图函数（供外部调用）

    Args:
        temp_dir: 截图保存目录

    Returns:
        截图文件路径，失败返回 None
    """
    os.makedirs(temp_dir, exist_ok=True)

    try:
        screenshot = ImageGrab.grab()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"manual_{timestamp}.png"
        filepath = os.path.join(temp_dir, filename)
        screenshot.save(filepath, "PNG")
        print(f"[手动截图] 已保存: {filepath}")
        return filepath
    except Exception as e:
        print(f"[错误] 手动截图失败: {e}")
        return None


# 测试代码
if __name__ == "__main__":
    def on_screenshot_callback(filepath: str):
        print(f"收到截图: {filepath}")

    listener = ScreenshotListener(
        hotkey="ctrl+shift+s",
        temp_dir="./test_screenshots",
        watch_clipboard=True,
        on_screenshot=on_screenshot_callback
    )

    listener.start()

    try:
        print("按 Ctrl+C 退出...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()
