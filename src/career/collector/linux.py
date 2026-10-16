"""Linux collector for X11 sessions (and XWayland windows).

Active window: `xprop` (part of x11-utils, present on most desktops).
Idle time:     XScreenSaver extension via ctypes; falls back to `xprintidle`.

Native Wayland compositors don't expose the focused window to other apps; there
get_active_window() returns None and collection continues with what is available.
"""

import ctypes
import ctypes.util
import logging
import os
import re
import shutil
import subprocess

from career.collector.base import ActiveWindow, ActivityCollector

log = logging.getLogger(__name__)

_ACTIVE_RE = re.compile(r"window id # (0x[0-9a-fA-F]+)")
_PROP_RE = re.compile(r"^(?P<name>[A-Z_]+)\([A-Z0-9_]+\)\s*=\s*(?P<value>.*)$")
_QUOTED_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _unescape(value: str) -> str:
    return re.sub(r"\\(.)", r"\1", value)


def parse_active_window_id(output: str) -> str | None:
    match = _ACTIVE_RE.search(output)
    if not match or int(match.group(1), 16) == 0:
        return None
    return match.group(1)


def parse_window_props(output: str) -> dict[str, list[str] | str]:
    """Parse `xprop -id <wid> _NET_WM_NAME WM_NAME WM_CLASS _NET_WM_PID` output."""
    props: dict[str, list[str] | str] = {}
    for line in output.splitlines():
        match = _PROP_RE.match(line.strip())
        if not match:
            continue
        name, value = match.group("name"), match.group("value")
        quoted = _QUOTED_RE.findall(value)
        if quoted:
            # xprop prints UTF-8 text and only escapes quotes and backslashes.
            props[name] = [_unescape(q) for q in quoted]
        else:
            props[name] = value.strip()
    return props


class _XScreenSaverInfo(ctypes.Structure):
    _fields_ = [
        ("window", ctypes.c_ulong),
        ("state", ctypes.c_int),
        ("kind", ctypes.c_int),
        ("til_or_since", ctypes.c_ulong),
        ("idle", ctypes.c_ulong),
        ("eventMask", ctypes.c_ulong),
    ]


class LinuxCollector(ActivityCollector):
    name = "linux"

    def __init__(self) -> None:
        self._xprop = shutil.which("xprop")
        self._xprintidle = shutil.which("xprintidle")
        self._xlib = None
        self._xss = None
        self._display = None
        self._info = None

    # lifecycle -----------------------------------------------------------
    def start(self) -> None:
        if not os.environ.get("DISPLAY"):
            log.warning("No DISPLAY set; window and idle detection are limited (Wayland or headless session).")
        if not self._xprop:
            log.warning("xprop not found; install x11-utils to enable active window detection.")
        self._open_xss()

    def stop(self) -> None:
        if self._xlib and self._display:
            if self._info:
                self._xlib.XFree(self._info)
            self._xlib.XCloseDisplay(self._display)
        self._display = self._info = None

    def _open_xss(self) -> None:
        try:
            xlib_path = ctypes.util.find_library("X11")
            xss_path = ctypes.util.find_library("Xss")
            if not (xlib_path and xss_path and os.environ.get("DISPLAY")):
                return
            xlib, xss = ctypes.cdll.LoadLibrary(xlib_path), ctypes.cdll.LoadLibrary(xss_path)
            xlib.XOpenDisplay.restype = ctypes.c_void_p
            xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
            xlib.XDefaultRootWindow.restype = ctypes.c_ulong
            xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
            xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]
            xlib.XFree.argtypes = [ctypes.c_void_p]
            xss.XScreenSaverAllocInfo.restype = ctypes.POINTER(_XScreenSaverInfo)
            xss.XScreenSaverQueryInfo.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(_XScreenSaverInfo)]
            display = xlib.XOpenDisplay(None)
            if not display:
                return
            self._xlib, self._xss, self._display = xlib, xss, display
            self._info = xss.XScreenSaverAllocInfo()
        except OSError as exc:
            log.warning("XScreenSaver unavailable: %s", exc)

    # probes --------------------------------------------------------------
    def _run(self, *args: str) -> str | None:
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=2, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.debug("%s failed: %s", args[0], exc)
            return None
        return result.stdout if result.returncode == 0 else None

    def get_active_window(self) -> ActiveWindow | None:
        if not self._xprop:
            return None
        root = self._run(self._xprop, "-root", "_NET_ACTIVE_WINDOW")
        wid = parse_active_window_id(root or "")
        if not wid:
            return None
        out = self._run(self._xprop, "-id", wid, "_NET_WM_NAME", "WM_NAME", "WM_CLASS", "_NET_WM_PID")
        if out is None:
            return None
        props = parse_window_props(out)
        title_vals = props.get("_NET_WM_NAME") or props.get("WM_NAME")
        title = title_vals[0] if isinstance(title_vals, list) and title_vals else None
        wm_class = props.get("WM_CLASS")
        pid_raw = props.get("_NET_WM_PID")
        pid = int(pid_raw) if isinstance(pid_raw, str) and pid_raw.isdigit() else None
        process = self.process_name(pid)
        app = wm_class[-1] if isinstance(wm_class, list) and wm_class else process
        return ActiveWindow(application=app, title=title, pid=pid, process=process, extra={"window_id": wid})

    def get_idle_time(self) -> float | None:
        if self._display and self._info:
            root = self._xlib.XDefaultRootWindow(self._display)
            if self._xss.XScreenSaverQueryInfo(self._display, root, self._info):
                return self._info.contents.idle / 1000.0
        if self._xprintidle:
            out = self._run(self._xprintidle)
            if out and out.strip().isdigit():
                return int(out.strip()) / 1000.0
        return None
