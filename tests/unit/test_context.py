from datetime import timedelta

from career.analysis.context import ProfileContext, build_context
from career.analysis.sessions import SessionEngine
from career.events.models import Event, EventType
from tests.fixtures.loader import load


def test_context_packet_for_supervisor_session():
    _, events = load("supervisor_temperature")
    [session] = SessionEngine().build(events)
    t = session.start + timedelta(minutes=30)
    extra = [
        Event(timestamp=t, type=EventType.FILE_CHANGED, window_title="temperature_test.py",
              metadata={"name": "temperature_test.py", "extension": "py"}),
        Event(timestamp=t, type=EventType.FILE_CHANGED, window_title="Temperature_Result.xlsx",
              metadata={"name": "Temperature_Result.xlsx", "extension": "xlsx"}),
        Event(timestamp=t + timedelta(minutes=5), type=EventType.GIT_ACTIVITY, metadata={
            "kind": "commit", "repository": "supervisor", "branch": "feature/temperature-test", "hash": "abc123def456",
            "message": "Fix temperature validation", "files": ["temperature_test.py"], "added": 12, "removed": 3}),
    ]
    ctx = build_context(session, events + extra, ProfileContext(job_title="Test Engineer"))
    assert ctx.time == session.start.astimezone().strftime("%H:%M") + "-" + session.end.astimezone().strftime("%H:%M")
    assert ctx.tickets == ["AI-1842"]
    assert ctx.workspaces == ["supervisor"]
    assert ctx.sites == ["Jira"]
    assert "Temperature_Result.xlsx" in ctx.files
    assert ctx.file_actions == {"py": 1, "xlsx": 1}
    assert ctx.git[0].repository == "supervisor"
    assert ctx.git[0].branch == "feature/temperature-test"
    assert ctx.git[0].commits[0].message == "Fix temperature validation"
    assert ctx.profile.job_title == "Test Engineer"
    vocab = ctx.evidence_vocabulary()
    assert {"AI-1842", "temperature_test.py", "abc123def456", "Jira", "Excel"} <= vocab
    assert "Improved reliability by 37%" not in vocab
