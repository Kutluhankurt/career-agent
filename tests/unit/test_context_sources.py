import subprocess
from pathlib import Path

import pytest

from career.analysis.signals import extract, extract_commands, extract_site
from career.collector import MockCollector, Sample
from career.collector.filesystem import FileActivity, is_relevant
from career.collector.git import Git, GitWatcher, discover_repos, parse_log
from career.events.models import EventType
from career.events.processor import EventProcessor, redact


# --- browser sites & terminal commands --------------------------------------
@pytest.mark.parametrize(
    ("app", "title", "site"),
    [
        ("Chrome", "AI-1842 Temperature Test - Jira - Google Chrome", "Jira"),
        ("Firefox", "Camera pipeline - Confluence — Mozilla Firefox", "Confluence"),
        ("Chrome", "acme/supervisor: Edge AI supervisor - GitHub - Google Chrome", "GitHub"),
        ("Chrome", "python - How to mock time? - Stack Overflow - Google Chrome", "Stack Overflow"),
        ("Chrome", "Grafana dashboards at grafana.example.com - Google Chrome", "grafana.example.com"),
        ("Chrome", "Homepage - Google Chrome", None),
        ("VS Code", "Jira notes", None),
    ],
)
def test_site(app, title, site):
    assert extract_site(app, title) == site


@pytest.mark.parametrize(
    ("title", "commands"),
    [
        ("pytest tests/test_temperature.py", {"pytest"}),
        ("alex@desk: ~/VersionUpdater_v2.3", set()),
        ("python3 main.py | tee -a update_logs.txt", {"python", "tail"} - {"tail"}),
        ("ssh root@10.0.0.4", {"ssh"}),
        ("sudo systemctl restart trueai", {"systemctl"}),
        ("~/work/supervisor — git status — zsh", {"git"}),
    ],
)
def test_commands(title, commands):
    assert extract_commands("Terminal", title) == commands


def test_signals_include_sites_and_commands():
    assert extract("Chrome", "MAI-311 Camera freeze - Jira - Google Chrome").sites == {"Jira"}
    assert extract("Terminal", "pytest -k temperature").commands == {"pytest"}


# --- privacy -------------------------------------------------------------------
def test_redact_secrets():
    assert redact("export OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwx") == "export OPENAI_API_KEY=[redacted]"
    assert "ghp_" not in redact("token ghp_abcdefghijklmnopqrstuvwxyz0123")
    assert redact("password: hunter2 — Terminal") == "[redacted] — Terminal"
    assert redact("temperature_test.py") == "temperature_test.py"


def test_excluded_apps_and_private_windows():
    collector = MockCollector([Sample("Signal", "Chat with Ayşe")])
    events = EventProcessor(collector, excluded_apps=["signal"]).tick()
    assert (events[0].application, events[0].window_title, events[0].metadata) == ("Private", None, {})
    events = EventProcessor(MockCollector([Sample("Google-chrome", "New Incognito Tab - Google Chrome")])).tick()
    assert events[0].application == "Private"


def test_browser_tracking_off_keeps_only_app():
    events = EventProcessor(MockCollector([Sample("Google-chrome", "AI-1842 - Jira")]), browser_tracking=False).tick()
    assert (events[0].application, events[0].window_title) == ("Chrome", None)


# --- filesystem ----------------------------------------------------------------
def test_file_relevance():
    assert is_relevant(Path("/w/supervisor/temperature_test.py"))
    assert not is_relevant(Path("/w/supervisor/.git/index"))
    assert not is_relevant(Path("/w/app/node_modules/x/index.js"))
    assert not is_relevant(Path("/w/a/.temperature_test.py.swp"))
    assert not is_relevant(Path("/w/a/~$Temperature_Result.xlsx"))


def test_file_events_debounced_metadata_only(tmp_path):
    repo = tmp_path / "supervisor"
    fa = FileActivity([repo], debounce=10)
    assert fa.record(repo / "src" / "temperature_test.py", "modified", now=100)
    assert not fa.record(repo / "src" / "temperature_test.py", "modified", now=105)
    assert fa.record(repo / "src" / "temperature_test.py", "modified", now=111)
    events = fa.drain()
    assert len(events) == 2 and fa.drain() == []
    meta = events[0].metadata
    assert events[0].type == EventType.FILE_CHANGED
    assert meta == {"action": "modified", "name": "temperature_test.py", "extension": "py",
                    "folder": str(repo / "src"), "repository": "supervisor"}


def test_watchdog_sees_real_writes(tmp_path):
    import time

    repo = tmp_path / "repo"
    repo.mkdir()
    fa = FileActivity([repo], debounce=0)
    fa.start()
    try:
        time.sleep(0.3)
        (repo / "notes.md").write_text("x")
        deadline = time.time() + 5
        events = []
        while time.time() < deadline and not events:
            time.sleep(0.1)
            events = fa.drain()
    finally:
        fa.stop()
    assert any(e.metadata["name"] == "notes.md" for e in events)


# --- git -------------------------------------------------------------------------
def git(repo: Path, *args: str) -> None:
    import os

    env = {**os.environ, "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "T",
           "GIT_COMMITTER_EMAIL": "t@x"}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "work" / "supervisor"
    r.mkdir(parents=True)
    git(r, "init", "-q")
    git(r, "symbolic-ref", "HEAD", "refs/heads/main")
    (r / "temperature_test.py").write_text("print(1)\n")
    git(r, "add", ".")
    git(r, "commit", "-q", "-m", "Initial")
    return r


def test_discover_repos(tmp_path, repo):
    (tmp_path / "work" / "node_modules" / "pkg" / ".git").mkdir(parents=True)
    assert discover_repos([str(tmp_path)], depth=3) == [repo]


def test_git_watcher_reports_new_commits_and_branch_switch(repo):
    watcher = GitWatcher([repo])
    assert watcher.check(repo) == []  # first look only remembers
    (repo / "temperature_test.py").write_text("print(1)\nprint(2)\nprint(3)\n")
    (repo / "config.yaml").write_text("limit: 85\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "Fix temperature validation")
    git(repo, "checkout", "-q", "-b", "feature/temperature-test")
    events = watcher.check(repo)
    kinds = [e.metadata["kind"] for e in events]
    assert kinds == ["branch_switch", "commit"]
    commit = events[1].metadata
    assert commit["message"] == "Fix temperature validation"
    assert set(commit["files"]) == {"temperature_test.py", "config.yaml"}
    assert (commit["added"], commit["removed"]) == (3, 0)
    assert commit["repository"] == "supervisor"
    assert watcher.check(repo) == []
    assert Git(repo).branch() == "feature/temperature-test"
    assert watcher.repo_for(str(repo / "src")) == repo


def test_parse_log_handles_binary_numstat():
    out = "\x1eabc123\x1fT\x1f2026-10-16T09:00:00+03:00\x1fAdd image\n-\t-\tlogo.png\n2\t0\tREADME.md\n"
    [c] = parse_log(out)
    assert (c.files, c.added, c.removed) == (["logo.png", "README.md"], 2, 0)
