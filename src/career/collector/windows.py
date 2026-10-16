"""Windows collector using the Win32 API through ctypes (no extra dependencies).

Active window: GetForegroundWindow + GetWindowTextW + GetWindowThreadProcessId.
Idle time:     GetLastInputInfo. Neither call needs administrator rights.
"""

import ctypes
import logging
import sys

from career.collector.base import ActiveWindow, ActivityCollector, CollectorUnavailable

log = logging.getLogger(__name__)


class _LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


class WindowsCollector(ActivityCollector):
    name = "windows"

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise CollectorUnavailable("WindowsCollector only runs on Windows")
        from ctypes import wintypes

        self._wintypes = wintypes
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32
        self._user32.GetForegroundWindow.restype = wintypes.HWND
        self._user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        self._user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self._user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self._kernel32.GetTickCount64.restype = ctypes.c_ulonglong

    def get_active_window(self) -> ActiveWindow | None:
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            return None
        length = self._user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        self._user32.GetWindowTextW(hwnd, buf, length + 1)
        pid = self._wintypes.DWORD()
        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = self.process_name(pid.value)
        return ActiveWindow(application=process, title=buf.value or None, pid=pid.value or None, process=process)

    def get_idle_time(self) -> float | None:
        info = _LastInputInfo()
        info.cbSize = ctypes.sizeof(info)
        if not self._user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        # dwTime is a 32-bit tick count; compare within the same 32-bit space.
        now = self._kernel32.GetTickCount64() & 0xFFFFFFFF
        return ((now - info.dwTime) & 0xFFFFFFFF) / 1000.0
