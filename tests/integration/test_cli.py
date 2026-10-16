from typer.testing import CliRunner

from career import __version__
from career.cli.main import app
from career.database.database import Database
from career.events.models import Event, EventType

runner = CliRunner()


def test_version(home):
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert f"Career Agent v{__version__}" in result.output


def test_status_when_stopped(home):
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "stopped" in result.output
    assert "Platform:" in result.output


def test_events_empty(home):
    result = runner.invoke(app, ["events"])
    assert result.exit_code == 0
    assert "No events yet" in result.output


def test_events_lists_rows(home):
    Database(home.database).add_events([
        Event(type=EventType.WINDOW_FOCUS, application="VS Code", window_title="temperature_test.py"),
        Event(type=EventType.IDLE_STARTED, metadata={"idle_seconds": 312}),
    ])
    result = runner.invoke(app, ["events", "--today"])
    assert result.exit_code == 0
    assert "temperature_test.py" in result.output
    assert "idle_started" in result.output
    status = runner.invoke(app, ["status"])
    assert "2 total" in status.output


def test_stop_when_not_running(home):
    result = runner.invoke(app, ["stop"])
    assert "not running" in result.output


def test_help_lists_commands(home):
    result = runner.invoke(app, ["--help"])
    for cmd in ("version", "status", "start", "stop", "events"):
        assert cmd in result.output


def test_sessions_command(home):
    from tests.fixtures import day

    Database(home.database).add_events(day.generate())
    result = runner.invoke(app, ["sessions", "--date", "2026-10-16"])
    assert result.exit_code == 0, result.output
    assert "→ 12 sessions" in result.output
    assert "supervisor · AI-1842" in result.output
    assert "VersionUpdater_v2.3" in result.output


def test_sessions_empty_day(home):
    Database(home.database)
    result = runner.invoke(app, ["sessions", "--date", "2026-01-01"])
    assert "no sessions yet" in result.output
