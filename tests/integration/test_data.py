import json
import zipfile

from typer.testing import CliRunner

from career import autostart, data
from career.cli.main import app
from career.database.database import Database

runner = CliRunner()


def test_export_import_roundtrip(seeded, home, tmp_path):
    out = data.export_json(seeded, tmp_path / "export.json")
    payload = json.loads(out.read_text())
    assert payload["format"] == "career-agent-export"
    assert len(payload["tables"]["events"]) > 1000 and payload["tables"]["ai_analysis"]
    assert "api_key" not in out.read_text().lower()
    fresh = Database(tmp_path / "fresh.db")
    counts = data.import_json(fresh, out)
    assert counts["events"] == len(payload["tables"]["events"])
    assert data.import_json(fresh, out)["events"] == 0          # never duplicates
    assert fresh.count_sessions() == seeded.count_sessions()


def test_csv_and_markdown_export(seeded, tmp_path):
    folder = data.export_csv(seeded, tmp_path / "csv")
    assert (folder / "events.csv").read_text().startswith("id,timestamp,type")
    md = data.export_markdown(seeded, tmp_path / "career.md").read_text()
    assert "## Projects" in md and "Supervisor" in md and "## CV" in md


def test_backup_and_restore(seeded, home, tmp_path):
    zpath = data.backup(home, tmp_path)
    assert zpath.name.startswith("career-backup-") and zpath.suffix == ".zip"
    names = zipfile.ZipFile(zpath).namelist()
    assert "career.db" in names and "README.txt" in names
    before = seeded.count_events()
    seeded.close()
    home.database.unlink()
    data.restore(home, zpath)
    assert Database(home.database).count_events() == before


def test_import_rejects_other_files(tmp_path, home):
    bad = tmp_path / "x.json"
    bad.write_text('{"hello": 1}')
    try:
        data.import_json(Database(home.database), bad)
    except ValueError as exc:
        assert "Career Agent export" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_autostart_linux_entry(monkeypatch, tmp_path):
    monkeypatch.setattr(autostart.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("CAREER_AGENT_HOME", raising=False)
    path = autostart.enable()
    text = path.read_text()
    assert path == tmp_path / "autostart" / "career-agent.desktop"
    assert "Exec=" in text and "-m career start" in text
    assert autostart.is_enabled() and autostart.disable() and not autostart.is_enabled()


def test_autostart_macos_and_windows_files(monkeypatch, tmp_path):
    monkeypatch.setattr(autostart.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(autostart.platform, "system", lambda: "Darwin")
    plist = autostart.enable().read_text()
    assert "<key>RunAtLoad</key>" in plist and "<string>career</string>" in plist
    monkeypatch.setattr(autostart.platform, "system", lambda: "Windows")
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    vbs = autostart.enable()
    text = vbs.read_text()
    assert vbs.name == "career-agent.vbs"
    assert 'CreateObject("WScript.Shell")' in text and '""-m"" ""career"" ""start""' in text and ", 0, False" in text


def test_cli_career_commands(seeded, home, tmp_path):
    for cmd in (["today", "--date", "2026-10-16"], ["skills"], ["projects"], ["achievements"], ["memory"],
                ["analyze", "--week"], ["analyze", "--month"], ["cv"], ["config"]):
        result = runner.invoke(app, cmd)
        assert result.exit_code == 0, (cmd, result.output)
    assert "Meaningful work" in runner.invoke(app, ["today", "--date", "2026-10-16"]).output
    assert "Python" in runner.invoke(app, ["skills"]).output
    pdf = tmp_path / "cv.pdf"
    assert runner.invoke(app, ["cv", "--format", "pdf", "--output", str(pdf)]).exit_code == 0
    assert pdf.read_bytes()[:4] == b"%PDF"
    out = runner.invoke(app, ["analyze", "--days", "3"]).output
    assert "Analyzed" in out
    assert runner.invoke(app, ["config", "set", "collector.idle_threshold", "240"]).exit_code == 0
    assert "240.0" in runner.invoke(app, ["config"]).output
    assert runner.invoke(app, ["export", "--format", "json", "--output", str(tmp_path / "e.json")]).exit_code == 0
    assert runner.invoke(app, ["backup", "--output", str(tmp_path / "b")]).exit_code == 0
    assert "paused" in runner.invoke(app, ["pause", "10"]).output.lower()
    assert "PAUSED" in runner.invoke(app, ["status"]).output or "stopped" in runner.invoke(app, ["status"]).output
    assert "resumed" in runner.invoke(app, ["resume"]).output


def test_cli_review_flow(seeded, home):
    from career.career.reports import Reports

    before = len(Reports(seeded).review_items())
    result = runner.invoke(app, ["review"], input="y\nn\ns\nq\n")
    assert result.exit_code == 0, result.output
    assert "reviewed" in result.output
    assert len(Reports(seeded).review_items()) == before - 2
