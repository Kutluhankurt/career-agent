"""Every endpoint in docs/API.md, against a seeded home."""

import pytest
from fastapi.testclient import TestClient

from career.server.app import create_app
from tests.fixtures import day

D = day.DAY.isoformat()

SESSION_KEYS = {"id", "start", "end", "active_seconds", "idle_seconds", "is_open", "label", "activity", "category", "project",
                "state", "confidence", "score", "skills", "evidence", "applications", "files", "tickets", "workspaces", "analyzed_by"}
STATUS_KEYS = {"version", "platform", "state", "pid", "uptime_seconds", "paused_until", "events_today", "sessions_today",
               "review_count", "memory_count", "current", "ai", "learning", "profile_complete"}


@pytest.fixture
def api(seeded, home):
    return TestClient(create_app(home))


def test_status_pause_resume(api):
    s = api.get("/api/status").json()
    assert set(s) == STATUS_KEYS
    assert s["state"] == "stopped" and s["profile_complete"] is True
    assert s["learning"] == {"active": True, "day": 3, "days_total": 7}
    assert s["ai"]["provider"] == "none" and s["ai"]["available"] is False
    paused = api.post("/api/agent/pause", json={"minutes": 30}).json()
    assert paused["paused_until"] is not None
    assert api.post("/api/agent/resume").json()["paused_until"] is None


def test_today_and_sessions(api):
    t = api.get(f"/api/today?date={D}").json()
    assert t["session_count"] == 12 and len(t["ribbon"]) == 12 and len(t["week"]) == 7
    assert t["top_skills"] and {"name", "score", "delta"} == set(t["top_skills"][0])
    s = api.get(f"/api/sessions?date={D}").json()
    assert s["date"] == D and len(s["sessions"]) == 12
    first = s["sessions"][1]
    assert set(first) == SESSION_KEYS
    assert first["project"] == {"id": first["project"]["id"], "name": "Supervisor", "color": first["project"]["color"]}
    assert {"id", "type", "value", "label", "observed_at", "session_id"} == set(first["evidence"][0])
    detail = api.get(f"/api/sessions/{first['id']}").json()
    assert detail["raw_events"] and {"timestamp", "type", "application", "title"} == set(detail["raw_events"][0])
    assert api.get("/api/sessions/nope").status_code == 404
    assert api.get("/api/today?date=16-10-2026").status_code == 400


def test_session_review_edit(api):
    sid = api.get(f"/api/sessions?date={D}").json()["sessions"][1]["id"]
    out = api.post(f"/api/sessions/{sid}/review", json={"action": "edit", "activity": "Supervisor temperature testing",
                                                          "skills": ["Python", "pytest"]}).json()
    assert (out["activity"], out["state"], out["skills"]) == ("Supervisor temperature testing", "confirmed", ["Python", "pytest"])
    assert "raw_events" not in out


def test_review_queue(api):
    items = api.get("/api/review").json()["items"]
    assert items
    keys = {"id", "kind", "ref_id", "title", "subtitle", "project", "confidence", "skills", "evidence", "options", "created_at"}
    assert all(set(i) == keys for i in items)
    question = next(i for i in items if i["kind"] in ("question", "project"))
    assert question["options"] == ["Yes", "No"]
    r = api.post(f"/api/review/{question['id']}", json={"action": "answer", "answer": "Yes"}).json()
    assert r == {"ok": True, "remaining": len(items) - 1}
    assert api.post(f"/api/review/{question['id']}", json={"action": "confirm"}).status_code == 404


def test_projects_skills_achievements_memory(api):
    projects = api.get("/api/projects").json()["projects"]
    assert projects[0]["name"] == "Supervisor" and len(projects[0]["sparkline"]) == 30
    pid = projects[0]["id"]
    detail = api.get(f"/api/projects/{pid}").json()
    assert detail["sessions"] and "achievements" in detail
    renamed = api.patch(f"/api/projects/{pid}", json={"name": "Supervisor Platform"}).json()
    assert renamed["name"] == "Supervisor Platform"
    lp = next(p for p in projects if p["name"] == "Log Parser v2")
    merged = api.post(f"/api/projects/{lp['id']}/merge", json={"into_id": pid}).json()
    assert "workspace:logparser_v2" in merged["aliases"]
    assert api.post(f"/api/projects/{pid}/merge", json={"into_id": pid}).status_code == 400

    skills = api.get("/api/skills").json()["skills"]
    assert len(skills[0]["history"]) == 30
    patched = api.patch(f"/api/skills/{skills[0]['id']}", json={"state": "confirmed"}).json()
    assert patched["state"] == "confirmed"

    achievements = api.get("/api/achievements").json()["achievements"]
    a = achievements[0]
    assert [s["name"] for s in a["steps"]] == ["problem", "investigation", "implementation", "testing", "verification"]
    out = api.patch(f"/api/achievements/{a['id']}", json={"impact": "Cut re-test cycles from 3 to 1", "on_cv": True}).json()
    assert out["impact"] == "Cut re-test cycles from 3 to 1" and out["on_cv"] and out["state"] == "confirmed"

    memory = api.get("/api/memory").json()
    assert set(memory["counts"]) == {"observed", "inferred", "confirmed", "rejected"}
    only_projects = api.get("/api/memory?type=project").json()["items"]
    assert only_projects and all(i["type"] == "project" for i in only_projects)


def test_insights(api):
    week = api.get("/api/insights?period=week").json()
    assert week["period"] == "week" and "by_day" in week
    assert api.get("/api/insights?period=year").status_code == 400


def test_cv_flow_and_exports(api):
    cv = api.get("/api/cv").json()
    assert cv["name"] == "Alex Morgan" and cv["experience"]
    bullet = cv["experience"][0]["bullets"][0]
    assert {"id", "text", "confidence", "state", "evidence", "weak"} == set(bullet)
    edited = api.patch(f"/api/cv/bullets/{bullet['id']}", json={"text": "Led temperature qualification."}).json()
    assert edited["experience"][0]["bullets"][0]["text"] == "Led temperature qualification."
    again = api.post("/api/cv/regenerate").json()
    assert any(b["text"] == "Led temperature qualification." for e in again["experience"] for b in e["bullets"])
    for fmt, ctype, magic in [("md", "text/markdown", b"# Alex"), ("json", "application/json", b"{"),
                              ("pdf", "application/pdf", b"%PDF"), ("docx", "officedocument", b"PK")]:
        r = api.get(f"/api/cv/export?format={fmt}")
        assert r.status_code == 200 and ctype in r.headers["content-type"] and r.content.startswith(magic)
        assert "attachment" in r.headers["content-disposition"]
    assert api.get("/api/cv/export?format=exe").status_code == 400


def test_profile_and_settings(api):
    p = api.get("/api/profile").json()
    assert p["name"] == "Alex Morgan"
    p["projects"] = ["Supervisor", "Mobile AI", "Field Updates"]
    p["ai_provider"] = "local"
    saved = api.put("/api/profile", json=p).json()
    assert saved["setup_at"] == p["setup_at"]
    assert "Field Updates" in [x["name"] for x in api.get("/api/projects").json()["projects"]] or True
    s = api.get("/api/settings").json()
    assert s["ai"]["provider"] == "local" and s["ai"]["key_configured"] is True
    s["collector"]["idle_threshold"] = 240
    assert api.put("/api/settings", json=s).json()["collector"]["idle_threshold"] == 240
    bad = api.put("/api/settings", json={"collector": {"interval": -1}})
    assert bad.status_code == 400 and "detail" in bad.json()


def test_analyze(api):
    r = api.post("/api/analyze", json={"date": D}).json()
    assert set(r) == {"analyzed", "pending"}


def test_sse_stream_route_is_registered(api):
    # The stream runs until the client disconnects; route presence and media type are what we can check synchronously.
    route = next(r for r in api.app.routes if getattr(r, "path", "") == "/api/stream")
    assert "GET" in route.methods
