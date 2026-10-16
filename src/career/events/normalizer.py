"""Maps raw, OS-specific application identifiers to one friendly name.

Windows reports "Code.exe", Linux "code" / "Code", macOS "Code" or "Visual Studio Code":
all of them become "VS Code" so the rest of the system never sees OS differences.
"""

from pathlib import PurePath

_ALIASES: dict[str, str] = {
    "code": "VS Code",
    "visual studio code": "VS Code",
    "code - insiders": "VS Code",
    "cursor": "Cursor",
    "google-chrome": "Chrome",
    "google chrome": "Chrome",
    "chrome": "Chrome",
    "chromium": "Chromium",
    "chromium-browser": "Chromium",
    "firefox": "Firefox",
    "navigator": "Firefox",
    "msedge": "Edge",
    "microsoft edge": "Edge",
    "safari": "Safari",
    "gnome-terminal-server": "Terminal",
    "gnome-terminal": "Terminal",
    "terminal": "Terminal",
    "konsole": "Terminal",
    "xterm": "Terminal",
    "iterm2": "Terminal",
    "windowsterminal": "Terminal",
    "cmd": "Terminal",
    "powershell": "Terminal",
    "pwsh": "Terminal",
    "excel": "Excel",
    "microsoft excel": "Excel",
    "libreoffice-calc": "Excel",
    "winword": "Word",
    "microsoft word": "Word",
    "slack": "Slack",
    "teams": "Teams",
    "ms-teams": "Teams",
    "microsoft teams": "Teams",
    "pycharm": "PyCharm",
    "jetbrains-pycharm": "PyCharm",
    "jetbrains-pycharm-ce": "PyCharm",
    "explorer": "File Explorer",
    "finder": "Finder",
    "nautilus": "Files",
    "org.gnome.nautilus": "Files",
}


def normalize_application(raw: str | None) -> str | None:
    if not raw:
        return None
    name = PurePath(raw.strip()).name
    if name.lower().endswith((".exe", ".app")):
        name = name[:-4]
    return _ALIASES.get(name.lower(), name)
