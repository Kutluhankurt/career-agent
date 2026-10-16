from datetime import date, timedelta

from career.career import cv as cv_engine
from career.career.evidence import TruthState
from career.career.projects import merge_projects, pretty, similar
from career.career.reports import Reports
from career.career.review import resolve
from career.career.skills import score_skills
from career.career.store import MemoryStore
from career.database.models import AchievementRow, AnalysisRow
from career.ai.base import FakeProvider
from tests.fixtures import day


def test_project_names():
    assert pretty("VersionUpdater_v2.3") == "Version Updater v2.3"
    assert pretty("logParser_v2") == "Log Parser v2"
    assert pretty("supervisor") == "Supervisor"
    assert similar("Mobile AI", "mobilai") and similar("Supervisor", "supervisor-fw")
    assert not similar("Supervisor", "mobilai")


def test_projects_from_profile_discovery_and_ticket_learning(seeded):
    store = MemoryStore(seeded)
    projects = {p.name: p for p in store.projects()}
    assert set(projects) == {"Supervisor", "Mobile AI", "Version Updater v2.3", "Log Parser v2"}
    assert projects["Supervisor"].state == "confirmed"           # named during setup
    assert "workspace:mobilai" in projects["Mobile AI"].aliases   # fuzzy match to the folder
    assert "ticket:AI" in projects["Supervisor"].aliases          # learned from co-occurrence
    assert "ticket:MAI" in projects["Mobile AI"].aliases
    assert projects["Log Parser v2"].state == "inferred"          # discovered, waiting for review


def test_analyses_and_rerun_keep_user_decisions(seeded):
    from career.career.memory import MemoryEngine
    from career.config import Settings

    store = MemoryStore(seeded)
    rows = store.analyses(since_day=day.DAY.isoformat())
    assert len(rows) == 12
    sup = next(a for a in rows if a.activity == "Supervisor testing")
    assert sup.category == "Testing" and "Python" in sup.skills
    assert {e["type"] for e in sup.evidence} >= {"ticket", "file"}
    sup.state, sup.activity, sup.edited = "confirmed", "Supervisor temperature testing", True
    store.save(sup)
    MemoryEngine(seeded, Settings()).update_day(day.DAY)
    again = store.get(AnalysisRow, sup.session_id)
    assert (again.state, again.activity) == ("confirmed", "Supervisor temperature testing")


def test_ai_catches_up_once_then_is_not_reasked(seeded):
    from career.ai.base import AIError
    from career.career.memory import MemoryEngine
    from career.config import Settings

    # sessions the rules were unsure about get one AI attempt when a provider appears...
    p = FakeProvider([AIError("offline")] * 20)
    MemoryEngine(seeded, Settings(), p).update_day(day.DAY)
    asked = len(p.calls)
    assert 0 < asked < 12
    # ...and an unchanged session is not asked again after that attempt
    MemoryEngine(seeded, Settings(), p).update_day(day.DAY)
    assert len(p.calls) == asked


def test_skill_scores_reward_evidence_and_confirmation(seeded):
    store = MemoryStore(seeded)
    analyses = store.analyses()
    base = score_skills(analyses, {}, day.DAY)
    assert base["Python"].score > base["Log analysis"].score
    assert all(0 <= s.score <= 100 for s in base.values())
    confirmed = score_skills(analyses, {"Python": "confirmed"}, day.DAY)
    assert confirmed["Python"].score > base["Python"].score
    assert "Python" not in score_skills(analyses, {"Python": "rejected"}, day.DAY)
    for a in analyses:
        a.state = TruthState.REJECTED
    assert score_skills(analyses, {}, day.DAY) == {}


def test_achievements_have_steps_and_no_invented_impact(seeded):
    store = MemoryStore(seeded)
    achs = {a.title: a for a in store.achievements()}
    title = "Investigated and validated temperature test in Supervisor"
    assert title in achs
    a = achs[title]
    assert sum(1 for v in a.steps.values() if v) >= 3
    assert a.impact is None and a.state == "inferred"
    assert not any(ch.isdigit() for t in achs for ch in t)


def test_review_cards_group_and_resolve(seeded):
    store = MemoryStore(seeded)
    items = Reports(seeded).review_items()
    kinds = {i["kind"] for i in items}
    assert {"session", "project", "question", "achievement"} <= kinds
    card = next(i for i in items if i["kind"] == "session" and i["title"] == "Supervisor testing")
    assert card["subtitle"].startswith("9 sessions")                   # 3 per day × 3 days, one card per week
    remaining = resolve(store, card["id"], "edit", title="Supervisor temperature testing")
    assert remaining == len(items) - 1
    touched = [a for a in store.analyses() if a.activity == "Supervisor temperature testing"]
    assert len(touched) == 9 and all(a.state == "confirmed" and a.edited for a in touched)
    q = next(i for i in items if i["kind"] == "question")
    resolve(store, q["id"], "answer", answer="no")
    proj = next(p for p in store.projects() if p.id == q["project"]["id"])
    assert not any(al.startswith("workspace:") and al.split(":")[1] in q["title"].lower() for al in proj.aliases)


def test_confirmed_patterns_stop_being_asked(seeded):
    from career.career.review import sync_review

    store = MemoryStore(seeded)
    rows = store.analyses()
    for a in rows:
        if a.activity == "Mobile AI testing":
            a.state = "confirmed"
    store.save(*rows)
    reviews = store.reviews(status=None)
    for r in reviews:
        r.status = "done"
    store.save(*reviews)
    later = day.DAY + timedelta(days=7)
    new = store.analyses()[0]
    clone = AnalysisRow(**{c: getattr(new, c) for c in ("activity", "category", "project_id", "confidence", "skills", "evidence",
                                                         "provider", "model", "session_events", "active_seconds", "edited",
                                                         "created_at", "updated_at")},
                        session_id="future", day=later.isoformat(), state="inferred")
    clone.activity, clone.project_id = "Mobile AI testing", next(p.id for p in store.projects() if p.name == "Mobile AI")
    clone.category = "Testing"
    store.save(clone)
    sync_review(store, later)
    assert not any(r.kind == "session" and "future" in r.data.get("session_ids", []) for r in store.reviews())


def test_merge_projects(seeded):
    store = MemoryStore(seeded)
    p = {x.name: x for x in store.projects()}
    target = merge_projects(store, p["Log Parser v2"].id, p["Supervisor"].id)
    assert "workspace:logparser_v2" in target.aliases
    assert "Log Parser v2" not in {x.name for x in store.projects()}
    assert all(a.project_id != p["Log Parser v2"].id for a in store.analyses())


def test_cv_maps_bullets_to_evidence_and_respects_decisions(seeded):
    store = MemoryStore(seeded)
    cv = cv_engine.generate(store)
    projects = [x[0] for x in cv.experience]
    assert projects[0] == "Supervisor"
    bullets = [b for _, _, bs in cv.experience for b in bs]
    assert all(b.evidence for b in bullets)
    assert any("temperature testing workflows" in b.text for b in bullets)
    # user edits survive regeneration
    first = bullets[0]
    cv_engine.edit_bullet(store, first.id, "Led temperature qualification of edge devices.")
    again = cv_engine.generate(store)
    assert any(b.text == "Led temperature qualification of edge devices." and b.state == "confirmed"
               for _, _, bs in again.experience for b in bs)
    # rejected projects vanish from the CV
    proj = next(p for p in store.projects() if p.name == "Version Updater v2.3")
    proj.state = "rejected"
    store.save(proj)
    assert "Version Updater v2.3" not in [x[0] for x in cv_engine.generate(store).experience]


def test_cv_ai_polish_cannot_add_numbers(seeded):
    store = MemoryStore(seeded)
    drafts = cv_engine.generate(store)
    ids = [b.id for _, _, bs in drafts.experience for b in bs]
    answer = {"bullets": [{"id": ids[0], "text": "Cut test time by 40% across temperature workflows"},
                          {"id": ids[1], "text": "Maintained Log Parser v2 tooling in Python"}]}
    polished = cv_engine.generate(store, FakeProvider([answer]))
    texts = [b.text for _, _, bs in polished.experience for b in bs]
    assert not any("40%" in t for t in texts)
    assert "Maintained Log Parser v2 tooling in Python." in texts


def test_cv_includes_confirmed_achievement_with_user_impact(seeded):
    store = MemoryStore(seeded)
    ach = next(a for a in store.achievements() if "temperature" in a.title)
    ach.state, ach.impact = "confirmed", "cut re-test cycles from 3 to 1"
    store.save(ach)
    texts = [b.text for _, _, bs in cv_engine.generate(store).experience for b in bs]
    assert any(t.startswith("Investigated and validated temperature test") and "cut re-test cycles from 3 to 1" in t for t in texts)


def test_cv_exports(seeded, tmp_path):
    store = MemoryStore(seeded)
    cv = cv_engine.generate(store)
    md = cv_engine.to_markdown(cv)
    assert md.startswith("# Alex Morgan") and "## Experience" in md
    assert cv_engine.to_dict(cv)["experience"][0]["bullets"][0]["evidence"]
    assert cv_engine.to_docx(cv, tmp_path / "cv.docx").stat().st_size > 5000
    pdf = cv_engine.to_pdf(cv, tmp_path / "cv.pdf")
    assert pdf.read_bytes()[:4] == b"%PDF"


def test_reports_today_and_insights(seeded):
    r = Reports(seeded)
    t = r.today(day.DAY)
    assert t["session_count"] == 12 and t["project_count"] == 4 and t["name"] == "Alex"
    assert len(t["week"]) == 7 and t["week_total_seconds"] >= t["active_seconds"]
    assert t["top_skills"][0]["name"] == "Python"
    ins = r.insights("week", day.DAY)
    assert ins["projects"][0]["name"] == "Supervisor"
    assert abs(sum(p["share"] for p in ins["projects"]) - 1) < 0.01
    assert any("testing sessions on Supervisor" in x for x in ins["repeated"])
    skill = r.skills(day.DAY)[0]
    assert len(skill["history"]) == 30 and set(skill["factors"]) == {"frequency", "duration", "complexity", "diversity",
                                                                     "evidence", "confirmation"}
    assert date.fromisoformat(r.project(MemoryStore(seeded).projects()[0])["last_active"]) == day.DAY
    assert AchievementRow


def test_profile_setup_time_keeps_timezone(home):
    from datetime import datetime, timezone

    from career.database.database import Database
    from career.profile.models import Profile

    store = MemoryStore(Database(home.database))
    store.save_profile(Profile(name="A", setup_at=datetime(2026, 10, 16, 11, 49, tzinfo=timezone.utc)))
    assert store.get_profile().setup_at == datetime(2026, 10, 16, 11, 49, tzinfo=timezone.utc)
