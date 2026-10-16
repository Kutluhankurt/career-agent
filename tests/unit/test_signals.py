import pytest

from career.analysis.signals import extract, extract_files, extract_tickets, extract_workspace


@pytest.mark.parametrize(
    ("app", "title", "workspace"),
    [
        ("VS Code", "temperature_test.py — supervisor — Visual Studio Code", "supervisor"),
        ("VS Code", "main.py - VersionUpdater_v2.3 - Visual Studio Code", "VersionUpdater_v2.3"),  # Windows dashes
        ("VS Code", "● config.yaml — supervisor [SSH: nxp-lab] — Visual Studio Code", "supervisor"),
        ("VS Code", "supervisor — Visual Studio Code", "supervisor"),
        ("VS Code", "Welcome — Visual Studio Code", None),
        ("VS Code", "notes.md — Visual Studio Code", None),
        ("PyCharm", "mobilai – test_camera.py", "mobilai"),
        ("Terminal", "alex@nxp-lab: ~/work/supervisor", "supervisor"),
        ("Terminal", "alex@desk: ~", None),
        ("Terminal", r"C:\Users\alex\VersionUpdater_v2.3", "VersionUpdater_v2.3"),
        ("Chrome", "AI-1842 Temperature Test - Jira - Google Chrome", None),
    ],
)
def test_workspace(app, title, workspace):
    assert extract_workspace(app, title) == workspace


def test_tickets():
    assert extract_tickets("AI-1842 Temperature Test - Jira") == {"AI-1842"}
    assert extract_tickets("MAI-311 and AI-1842") == {"MAI-311", "AI-1842"}
    assert extract_tickets("Encoding UTF-8 issue, ISO-9001") == set()
    assert extract_tickets("lowercase ai-1842") == set()


def test_files():
    assert extract_files("temperature_test.py — supervisor") == {"temperature_test.py"}
    assert extract_files("Temperature_Result.xlsx - Excel") == {"Temperature_Result.xlsx"}
    assert extract_files("Visit www.example.com") == set()
    assert extract_files("v2.3 release") == set()


def test_extract_combines():
    s = extract("VS Code", "AI-1842_notes.md — supervisor — Visual Studio Code")
    assert s.workspaces == {"supervisor"}
    assert s.files == {"AI-1842_notes.md"}
    assert s.keyed
    assert not extract("Slack", "Slack | #general").keyed
    assert not extract("Slack", None).keyed
