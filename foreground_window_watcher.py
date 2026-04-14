"""
前台窗口活动采集模块
使用 Windows API 轮询当前焦点窗口，并在窗口变化时发出事件。
"""

import ctypes
import os
import threading
import time
from ctypes import wintypes
from typing import Callable, Dict, Optional


class ForegroundWindowWatcher:
    """前台窗口监听器，负责采集当前焦点窗口变化。"""

    def __init__(
        self,
        on_change: Optional[Callable[[Dict[str, str]], None]] = None,
        poll_interval_seconds: int = 6,
    ):
        """
        初始化前台窗口监听器。

        Args:
            on_change: Optional[Callable[[Dict[str, str]], None]] - 窗口变化回调。
            poll_interval_seconds: int - 轮询间隔秒数。

        Returns:
            None - 无返回值。
        """
        self.on_change = on_change
        self.poll_interval_seconds = max(2, int(poll_interval_seconds))
        self._running = False
        self._thread = None
        self._last_signature = ""
        self._last_emitted_at = 0.0

        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.psapi = ctypes.WinDLL("psapi", use_last_error=True)

        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        self.user32.GetWindowTextLengthW.restype = ctypes.c_int
        self.user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user32.GetWindowTextW.restype = ctypes.c_int
        self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD

        self.kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel32.OpenProcess.restype = wintypes.HANDLE
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel32.CloseHandle.restype = wintypes.BOOL

        self.psapi.GetModuleBaseNameW.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD]
        self.psapi.GetModuleBaseNameW.restype = wintypes.DWORD

    def start(self):
        """
        启动监听线程。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """
        停止监听线程。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self._running = False

    def _watch_loop(self):
        """
        监听前台窗口变化。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        while self._running:
            snapshot = self._capture_foreground_window()
            if self._should_emit_snapshot(snapshot):
                self._last_signature = snapshot["signature"]
                self._last_emitted_at = time.time()
                if self.on_change:
                    self.on_change(snapshot)
            time.sleep(self.poll_interval_seconds)

    def _should_emit_snapshot(self, snapshot: Dict[str, str]) -> bool:
        """
        判断当前窗口快照是否需要发出。

        Args:
            snapshot: Dict[str, str] - 当前窗口快照。

        Returns:
            bool - 是否应触发事件。
        """
        signature = snapshot.get("signature", "")
        if not signature:
            return False

        title = snapshot.get("window_title", "").strip()
        if len(title) < 2:
            return False

        if signature != self._last_signature:
            return True

        return time.time() - self._last_emitted_at >= max(30, self.poll_interval_seconds * 5)

    def _capture_foreground_window(self) -> Dict[str, str]:
        """
        捕获当前前台窗口信息。

        Args:
            无。

        Returns:
            Dict[str, str] - 当前窗口快照。
        """
        hwnd = self.user32.GetForegroundWindow()
        if not hwnd:
            return self._build_snapshot("", "", "")

        title = self._get_window_title(hwnd)
        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process_name = self._get_process_name(pid.value)
        return self._build_snapshot(title, process_name, str(pid.value))

    def _build_snapshot(self, title: str, process_name: str, pid: str) -> Dict[str, str]:
        """
        组装窗口快照数据。

        Args:
            title: str - 窗口标题。
            process_name: str - 进程名称。
            pid: str - 进程 ID。

        Returns:
            Dict[str, str] - 标准化窗口快照。
        """
        normalized_process = process_name or "unknown"
        normalized_title = title.strip()
        return {
            "window_title": normalized_title,
            "process_name": normalized_process,
            "pid": pid,
            "signature": f"{normalized_process}|{normalized_title}",
            "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _get_window_title(self, hwnd) -> str:
        """
        读取窗口标题。

        Args:
            hwnd: object - 窗口句柄。

        Returns:
            str - 窗口标题。
        """
        length = self.user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        self.user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value

    def _get_process_name(self, pid: int) -> str:
        """
        根据进程 ID 获取进程名。

        Args:
            pid: int - 进程 ID。

        Returns:
            str - 进程名称。
        """
        process_query_limited_information = 0x1000
        process_vm_read = 0x0010
        process_handle = self.kernel32.OpenProcess(
            process_query_limited_information | process_vm_read,
            False,
            pid,
        )
        if not process_handle:
            return ""

        try:
            buffer = ctypes.create_unicode_buffer(260)
            copied = self.psapi.GetModuleBaseNameW(process_handle, None, buffer, len(buffer))
            if copied <= 0:
                return ""
            return os.path.splitext(buffer.value)[0]
        finally:
            self.kernel32.CloseHandle(process_handle)
