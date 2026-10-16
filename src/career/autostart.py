"""Start Career Agent at login (roadmap §47). No administrator rights needed anywhere.

Linux    XDG autostart entry (~/.config/autostart/career-agent.desktop). It runs inside the
         graphical session, so the agent can see windows (a systemd user service usually
         starts without DISPLAY and couldn't).
macOS    LaunchAgent (~/Library/LaunchAgents/dev.career-agent.agent.plist)
Windows  a hidden launcher script in the user's Startup folder
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

LABEL = "dev.career-agent.agent"


def _python() -> str:
    exe = Path(sys.executable)
    if platform.system() == "Windows":
        pythonw = exe.with_name("pythonw.exe")
        if pythonw.exists():
            return str(pythonw)
    return str(exe)


def _command() -> list[str]:
    if getattr(sys, "frozen", False):  # standalone binary
        return [sys.executable, "start"]
    return [_python(), "-m", "career", "start"]


def autostart_path() -> Path:
    system = platform.system()
    if system == "Linux":
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return base / "autostart" / "career-agent.desktop"
    if system == "Darwin":
        return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    if system == "Windows":
        appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "career-agent.vbs"
    raise RuntimeError(f"Autostart isn't supported on {system}")


def _home_env() -> str | None:
    return os.environ.get("CAREER_AGENT_HOME")


def enable() -> Path:
    path = autostart_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = _command()
    system = platform.system()
    home = _home_env()
    if system == "Linux":
        exec_line = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        if home:
            exec_line = f'env CAREER_AGENT_HOME="{home}" {exec_line}'
        path.write_text(
            "[Desktop Entry]\nType=Application\nName=Career Agent\n"
            "Comment=Turns your daily work into a career record\n"
            f"Exec={exec_line}\nX-GNOME-Autostart-enabled=true\nNoDisplay=true\nTerminal=false\n",
            encoding="utf-8",
        )
    elif system == "Darwin":
        args = "".join(f"\n        <string>{c}</string>" for c in cmd)
        env = f"\n    <key>EnvironmentVariables</key>\n    <dict><key>CAREER_AGENT_HOME</key><string>{home}</string></dict>" if home else ""
        path.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LABEL}</string>
    <key>ProgramArguments</key>
    <array>{args}
    </array>
    <key>RunAtLoad</key>
    <true/>{env}
</dict>
</plist>
""", encoding="utf-8")
    else:
        quoted = " ".join(f'""{c}""' for c in cmd)
        env = f'Set e = sh.Environment("PROCESS")\ne("CAREER_AGENT_HOME") = "{home}"\n' if home else ""
        path.write_text(f'Set sh = CreateObject("WScript.Shell")\n{env}sh.Run "{quoted}", 0, False\n', encoding="utf-8")
    return path


def disable() -> bool:
    path = autostart_path()
    if platform.system() == "Darwin" and path.exists() and shutil.which("launchctl"):
        subprocess.run(["launchctl", "unload", str(path)], capture_output=True, check=False)
    if path.exists():
        path.unlink()
        return True
    return False


def is_enabled() -> bool:
    try:
        return autostart_path().exists()
    except RuntimeError:
        return False
