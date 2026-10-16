import pytest

from career.events.normalizer import normalize_application


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Code.exe", "VS Code"),        # Windows
        ("code", "VS Code"),            # Linux WM_CLASS instance
        ("Code", "VS Code"),            # Linux WM_CLASS class / macOS
        ("Visual Studio Code", "VS Code"),
        ("chrome.exe", "Chrome"),
        ("Google-chrome", "Chrome"),
        ("Gnome-terminal-server", "Terminal"),
        ("EXCEL.EXE", "Excel"),
        ("/usr/bin/firefox", "Firefox"),
        ("Unknown Tool", "Unknown Tool"),
        ("", None),
        (None, None),
    ],
)
def test_normalize_application(raw, expected):
    assert normalize_application(raw) == expected
