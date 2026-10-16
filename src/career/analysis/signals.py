"""Cheap, deterministic context signals pulled from window titles.

These are only what the session engine needs to tell "same work" from "different
work": workspace (repo/project folder), ticket IDs and file names. Sprint 4's context
builder extends this with Git, filesystem and browser data.
"""

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath, PureWindowsPath

TICKET_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d{1,6})\b")
_TICKET_STOPLIST = {"UTF", "ISO", "SHA", "RFC", "CVE", "COVID", "MP", "GPT", "X11", "I2C", "IP"}

FILE_EXTENSIONS = (
    "py|ipynb|js|jsx|ts|tsx|vue|java|kt|go|rs|c|cc|cpp|h|hpp|cs|rb|php|swift|sh|ps1|bat|"
    "sql|html|css|scss|json|yaml|yml|toml|ini|cfg|xml|md|rst|txt|csv|tsv|log|tm|"
    "xlsx|xls|docx|doc|pptx|ppt|pdf"
)
FILE_RE = re.compile(rf"(?<![\w/\\])([\w][\w.\-]*\.(?:{FILE_EXTENSIONS}))\b", re.IGNORECASE)

# "file.py — folder — Visual Studio Code" (macOS/Linux) or "file.py - folder - Visual Studio Code" (Windows)
_TITLE_SPLIT_RE = re.compile(r"\s+[—–-]\s+")
_EDITOR_SUFFIXES = {"visual studio code", "code - insiders", "cursor", "vscodium"}
_JETBRAINS_APPS = {"PyCharm", "IntelliJ IDEA", "WebStorm", "CLion", "GoLand", "Rider"}
# "user@host: ~/projects/supervisor"  or  "~/projects/supervisor — zsh"
_TERMINAL_PATH_RE = re.compile(r"(?:^|[:\s])((?:~|/|[A-Za-z]:\\)[^\s:]*)")
_REMOTE_SUFFIX_RE = re.compile(r"\s*\[(?:SSH|WSL|Dev Container|Codespaces)[^\]]*\]\s*$", re.IGNORECASE)


BROWSERS = {"Chrome", "Chromium", "Firefox", "Edge", "Safari", "Brave", "Opera", "Vivaldi", "Arc"}

# Recognisable sites from the end of browser titles ("AI-1842 Temperature Test - Jira - Google Chrome").
_SITE_SUFFIXES = {
    "jira": "Jira", "confluence": "Confluence", "github": "GitHub", "gitlab": "GitLab", "bitbucket": "Bitbucket",
    "stack overflow": "Stack Overflow", "google docs": "Google Docs", "google sheets": "Google Sheets",
    "google slides": "Google Slides", "google drive": "Google Drive", "gmail": "Gmail", "outlook": "Outlook",
    "youtube": "YouTube", "chatgpt": "ChatGPT", "claude": "Claude", "notion": "Notion", "linear": "Linear",
    "figma": "Figma", "grafana": "Grafana", "kibana": "Kibana", "sentry": "Sentry", "tailscale": "Tailscale",
    "aws management console": "AWS", "azure devops": "Azure DevOps", "microsoft teams": "Teams", "slack": "Slack",
    "medium": "Medium", "wikipedia": "Wikipedia", "linkedin": "LinkedIn", "trello": "Trello", "asana": "Asana",
}
_BROWSER_SUFFIX_RE = re.compile(
    r"\s+[—–-]\s+(?:Google Chrome|Chromium|Mozilla Firefox|Firefox|Microsoft Edge|Edge|Safari|Brave|Opera|Vivaldi)$",
    re.IGNORECASE,
)
_DOMAIN_RE = re.compile(r"\b((?:[a-z0-9-]+\.)+(?:com|org|net|io|dev|ai|app|co|tr|de|pl|eu|gov|edu))\b", re.IGNORECASE)

# Commands recognisable from terminal titles ("pytest tests/", "python3 main.py", "ssh root@10.0.0.4")
_COMMANDS = {
    "pytest": "pytest", "python": "python", "python3": "python", "pip": "pip", "uv": "uv", "npm": "npm",
    "npx": "npm", "yarn": "yarn", "pnpm": "pnpm", "node": "node", "git": "git", "make": "make", "cmake": "cmake",
    "docker": "docker", "docker-compose": "docker", "kubectl": "kubectl", "ssh": "ssh", "scp": "scp", "rsync": "rsync",
    "cargo": "cargo", "go": "go", "gradle": "gradle", "mvn": "maven", "terraform": "terraform", "ansible": "ansible",
    "ansible-playbook": "ansible", "vim": "vim", "nvim": "vim", "htop": "htop", "journalctl": "journalctl",
    "systemctl": "systemctl", "gcc": "gcc", "g++": "gcc", "tail": "tail", "grep": "grep", "psql": "psql",
    "mysql": "mysql", "sqlite3": "sqlite", "adb": "adb", "minicom": "minicom", "picocom": "minicom", "tmux": "tmux",
    "claude": "claude", "career": "career", "tailscale": "tailscale", "ffmpeg": "ffmpeg", "gst-launch-1.0": "gstreamer",
}
_SHELLS = {"bash", "zsh", "fish", "sh", "pwsh", "powershell", "cmd"}


@dataclass
class Signals:
    workspaces: set[str] = field(default_factory=set)
    tickets: set[str] = field(default_factory=set)
    files: set[str] = field(default_factory=set)
    sites: set[str] = field(default_factory=set)
    commands: set[str] = field(default_factory=set)

    @property
    def keyed(self) -> bool:
        """True when the span says *which* work it is (workspace or ticket)."""
        return bool(self.workspaces or self.tickets)


def extract_tickets(text: str) -> set[str]:
    return {t for t in TICKET_RE.findall(text) if t.split("-")[0] not in _TICKET_STOPLIST}


def extract_files(text: str) -> set[str]:
    return {f for f in FILE_RE.findall(text) if not f.lower().startswith(("www.", "http"))}


def extract_workspace(application: str | None, title: str) -> str | None:
    if application in ("VS Code", "Cursor"):
        parts = [p for p in _TITLE_SPLIT_RE.split(title) if p]
        if parts and parts[-1].lower() in _EDITOR_SUFFIXES:
            parts = parts[:-1]
        if len(parts) >= 2:
            return _clean_workspace(parts[-1])
        if len(parts) == 1 and not FILE_RE.fullmatch(parts[0].lstrip("● ")):
            return _clean_workspace(parts[0])
        return None
    if application in _JETBRAINS_APPS:
        parts = [p for p in _TITLE_SPLIT_RE.split(title) if p]
        return _clean_workspace(parts[0]) if len(parts) >= 2 else None
    if application == "Terminal":
        match = _TERMINAL_PATH_RE.search(title)
        if match:
            raw = match.group(1).rstrip("/\\")
            path = PureWindowsPath(raw) if "\\" in raw else PurePosixPath(raw)
            name = path.name
            if name and name not in ("~", ""):
                return name
    return None


def _clean_workspace(value: str) -> str | None:
    value = _REMOTE_SUFFIX_RE.sub("", value).strip().lstrip("● ").strip()
    if not value or value.lower() in ("welcome", "untitled", "settings", "extensions"):
        return None
    return value


def extract_site(application: str | None, title: str) -> str | None:
    if application not in BROWSERS:
        return None
    page = _BROWSER_SUFFIX_RE.sub("", title)
    parts = [p.strip() for p in _TITLE_SPLIT_RE.split(page) if p.strip()]
    for part in reversed(parts[1:] or parts):
        site = _SITE_SUFFIXES.get(part.lower())
        if site:
            return site
    domain = _DOMAIN_RE.search(page)
    return domain.group(1).lower() if domain else None


def extract_commands(application: str | None, title: str) -> set[str]:
    if application != "Terminal":
        return set()
    found = set()
    # the running command usually leads the title, or follows "user@host: path" / "—"
    for chunk in re.split(r"\s+[—–]\s+|:\s|;|&&|\|", title):
        words = chunk.strip().split()
        if not words:
            continue
        first = words[0].rsplit("/", 1)[-1].lower()
        if first == "sudo" and len(words) > 1:
            first = words[1].rsplit("/", 1)[-1].lower()
        if first in _COMMANDS:
            found.add(_COMMANDS[first])
        elif first in ("python", "python3") or first.startswith("python3."):
            found.add("python")
    return found - _SHELLS


def extract(application: str | None, title: str | None) -> Signals:
    if not title:
        return Signals()
    workspace = extract_workspace(application, title)
    site = extract_site(application, title)
    return Signals(
        workspaces={workspace} if workspace else set(),
        tickets=extract_tickets(title),
        files=extract_files(title),
        sites={site} if site else set(),
        commands=extract_commands(application, title),
    )
