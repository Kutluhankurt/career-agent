"""macOS collector using built-in tools (no PyObjC dependency).

Active window: `osascript` asking System Events for the frontmost process and its
               front window title. Window titles need the Accessibility permission;
               without it only the application name is reported.
Idle time:     `ioreg -c IOHIDSystem` → HIDIdleTime (nanoseconds).
"""

import logging
import re
import subprocess
import sys

from career.collector.base import ActiveWindow, ActivityCollector, CollectorUnavailable

log = logging.getLogger(__name__)

_FRONT_SCRIPT = """
tell application "System Events"
    set p to first application process whose frontmost is true
    set appName to name of p
    set appPid to unix id of p
    set winTitle to ""
    try
        set winTitle to name of front window of p
    end try
end tell
return appName & "\\n" & appPid & "\\n" & winTitle
"""

_IDLE_RE = re.compile(r'"HIDIdleTime"\s*=\s*(\d+)')


def parse_hid_idle(output: str) -> float | None:
    match = _IDLE_RE.search(output)
    return int(match.group(1)) / 1_000_000_000 if match else None


def parse_front_window(output: str) -> ActiveWindow | None:
    lines = output.rstrip("\n").split("\n")
    if not lines or not lines[0]:
        return None
    app = lines[0]
    pid = int(lines[1]) if len(lines) > 1 and lines[1].isdigit() else None
    title = lines[2] if len(lines) > 2 and lines[2] else None
    return ActiveWindow(application=app, title=title, pid=pid, process=app)


class MacOSCollector(ActivityCollector):
    name = "macos"

    def __init__(self) -> None:
        if sys.platform != "darwin":
            raise CollectorUnavailable("MacOSCollector only runs on macOS")
        self._warned = False

    def _run(self, *args: str) -> str | None:
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=3, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.debug("%s failed: %s", args[0], exc)
            return None
        if result.returncode != 0:
            if not self._warned and "not allowed" in result.stderr.lower():
                log.warning("Accessibility permission missing; window titles unavailable.")
                self._warned = True
            return None
        return result.stdout

    def get_active_window(self) -> ActiveWindow | None:
        out = self._run("osascript", "-e", _FRONT_SCRIPT)
        return parse_front_window(out) if out else None

    def get_idle_time(self) -> float | None:
        out = self._run("ioreg", "-c", "IOHIDSystem", "-d", "4")
        return parse_hid_idle(out) if out else None
