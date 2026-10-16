"""Local dashboard server: FastAPI + the built React app, on 127.0.0.1 only."""

import asyncio
import json
import tempfile
from datetime import date
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from career import __version__
from career.agent import pause, read_agent_info, read_pause, resume
from career.ai import get_provider
from career.ai.keys import has_key
from career.career import cv as cv_engine
from career.career.evidence import TruthState
from career.career.memory import MemoryEngine
from career.career.projects import ensure_profile_projects, merge_projects
from career.career.reports import Reports, iso
from career.career.review import learning_day, resolve
from career.career.store import MemoryStore
from career.collector import platform_name
from career.config import Paths, Settings, get_paths, load_settings, save_settings
from career.database.database import Database
from career.database.models import AchievementRow, AnalysisRow, ProjectRow, SkillRow
from career.events.models import EventType, utc_now
from career.profile.models import Profile
from career.server import schemas

STATIC = Path(__file__).parent / "static"


def _day(value: str | None) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(400, "Use a date like 2026-10-16.") from exc


def create_app(paths: Paths | None = None) -> FastAPI:
    paths = (paths or get_paths()).ensure()
    db = Database(paths.database)
    app = FastAPI(title="Career Agent", version=__version__, docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.paths, app.state.db = paths, db

    def settings() -> Settings:
        return load_settings(paths.config)

    def store() -> MemoryStore:
        return MemoryStore(db)

    # --- status -------------------------------------------------------------------
    _ai_cache: dict = {}

    def ai_available(s: Settings) -> bool:
        key = (s.ai.provider, s.ai.model)
        cached = _ai_cache.get(key)
        if cached and (utc_now() - cached[1]).total_seconds() < 60:
            return cached[0]
        provider = get_provider(s.ai)
        ok = bool(provider and provider.available())
        _ai_cache[key] = (ok, utc_now())
        return ok

    def status() -> dict:
        s = settings()
        info = read_agent_info(paths)
        until = read_pause(paths)
        today = date.today()
        from career.analysis.service import day_bounds

        since, _ = day_bounds(today)
        st = store()
        current = None
        if info and not until:
            last = db.last_event()
            focus = db.last_event(EventType.WINDOW_FOCUS)
            if focus and last and last.type not in (EventType.IDLE_STARTED, EventType.AGENT_STOPPED):
                open_session = next((x for x in reversed(db.list_sessions(since=since)) if x.is_open), None)
                project = None
                if open_session:
                    a = st.get(AnalysisRow, open_session.id)
                    ref = Reports(db).project_ref(a.project_id) if a else None
                    project = ref["name"] if ref else None
                current = {"application": focus.application, "title": focus.window_title, "project": project,
                           "since": iso(open_session.start if open_session else focus.timestamp)}
        last_update = st.get_state("last_update", {}) or {}
        day = learning_day(st, today)
        profile = st.get_profile()
        memory_count = (sum(1 for a in st.analyses() if a.state == TruthState.CONFIRMED)
                        + sum(1 for x in st.skills() if x.state in (TruthState.CONFIRMED, TruthState.OBSERVED))
                        + sum(1 for x in st.projects() if x.state == TruthState.CONFIRMED)
                        + sum(1 for x in st.achievements() if x.state == TruthState.CONFIRMED))
        return {
            "version": __version__, "platform": platform_name(),
            "state": "paused" if (info and until) else "running" if info else "stopped",
            "pid": info.pid if info else None,
            "uptime_seconds": round((utc_now() - info.started_at).total_seconds()) if info else None,
            "paused_until": iso(until), "events_today": db.count_events(since=since),
            "sessions_today": db.count_sessions(since=since), "review_count": len(Reports(db).review_items()),
            "memory_count": memory_count, "current": current,
            "ai": {"provider": s.ai.provider, "available": ai_available(s), "pending_sessions": last_update.get("pending_ai", 0)},
            "learning": {"active": day is not None, "day": day or 7, "days_total": 7},
            "profile_complete": profile.complete,
        }

    @app.get("/api/status")
    def get_status():
        return status()

    @app.post("/api/agent/pause")
    def post_pause(body: schemas.PauseBody = Body(default_factory=schemas.PauseBody)):
        pause(paths, body.minutes)
        return status()

    @app.post("/api/agent/resume")
    def post_resume():
        resume(paths)
        return status()

    # --- daily loop -------------------------------------------------------------------
    @app.get("/api/today")
    def get_today(date: str | None = None):
        return Reports(db).today(_day(date))

    @app.get("/api/sessions")
    def get_sessions(date: str | None = None):
        d = _day(date)
        return {"date": d.isoformat(), "sessions": Reports(db).sessions(d)}

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str):
        detail = Reports(db).session_detail(session_id)
        if detail is None:
            raise HTTPException(404, "That session no longer exists. It may have been merged into another one.")
        return detail

    @app.post("/api/sessions/{session_id}/review")
    def review_session(session_id: str, body: schemas.SessionReviewBody):
        st = store()
        row = st.get(AnalysisRow, session_id)
        if row is None:
            raise HTTPException(404, "This session hasn't been analyzed yet. Try again in a minute.")
        if body.action == "edit":
            if body.activity:
                row.activity = body.activity.strip()[:90]
            if body.project_id is not None:
                if body.project_id and st.get(ProjectRow, body.project_id) is None:
                    raise HTTPException(400, "Unknown project.")
                row.project_id = body.project_id or None
            if body.skills is not None:
                row.skills = [s.strip() for s in body.skills if s.strip()][:8]
            row.edited = True
        row.state = (TruthState.REJECTED if body.action == "reject" else TruthState.CONFIRMED).value
        row.updated_at = st.now()
        st.save(row)
        # a card that covered this session is done once all of its sessions are decided
        for r in st.reviews():
            ids = (r.data or {}).get("session_ids", [])
            if r.kind == "session" and session_id in ids:
                if all((st.get(AnalysisRow, i) or row).state != TruthState.INFERRED for i in ids):
                    resolve(st, r.id, body.action if body.action != "edit" else "confirm")
        detail = Reports(db).session_detail(session_id)
        return {k: v for k, v in detail.items() if k != "raw_events"} if detail else {}

    @app.get("/api/review")
    def get_review():
        return {"items": Reports(db).review_items()}

    @app.post("/api/review/{review_id}")
    def post_review(review_id: str, body: schemas.ReviewBody):
        try:
            remaining = resolve(store(), review_id, body.action, title=body.title, answer=body.answer)
        except KeyError as exc:
            raise HTTPException(404, "This item was already reviewed.") from exc
        return {"ok": True, "remaining": remaining}

    # --- memory ----------------------------------------------------------------------------
    @app.get("/api/projects")
    def get_projects():
        return {"projects": Reports(db).projects()}

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str):
        detail = Reports(db).project_detail(project_id)
        if detail is None:
            raise HTTPException(404, "Project not found.")
        return detail

    @app.patch("/api/projects/{project_id}")
    def patch_project(project_id: str, body: schemas.ProjectPatch):
        st = store()
        row = st.get(ProjectRow, project_id)
        if row is None:
            raise HTTPException(404, "Project not found.")
        if body.name:
            row.name = body.name.strip()
        if body.state:
            row.state = body.state
        st.save(row)
        return Reports(db).project(row)

    @app.post("/api/projects/{project_id}/merge")
    def post_merge(project_id: str, body: schemas.MergeBody):
        try:
            target = merge_projects(store(), project_id, body.into_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return Reports(db).project(target)

    @app.get("/api/skills")
    def get_skills():
        return {"skills": Reports(db).skills(date.today())}

    @app.patch("/api/skills/{skill_id}")
    def patch_skill(skill_id: str, body: schemas.SkillPatch):
        st = store()
        row = st.get(SkillRow, skill_id)
        if row is None:
            raise HTTPException(404, "Skill not found.")
        row.state = body.state
        st.save(row)
        skill = next((s for s in Reports(db).skills(date.today()) if s["id"] == skill_id), None)
        return skill or {"id": row.id, "name": row.name, "state": row.state}

    @app.get("/api/achievements")
    def get_achievements():
        return {"achievements": Reports(db).achievements()}

    @app.patch("/api/achievements/{achievement_id}")
    def patch_achievement(achievement_id: str, body: schemas.AchievementPatch):
        st = store()
        row = st.get(AchievementRow, achievement_id)
        if row is None:
            raise HTTPException(404, "Achievement not found.")
        fields = body.model_dump(exclude_unset=True)
        if "title" in fields and body.title:
            row.title, row.edited = body.title.strip(), True
        if "state" in fields and body.state:
            row.state = body.state
        if "impact" in fields:
            row.impact = (body.impact or "").strip() or None
        if "on_cv" in fields and body.on_cv is not None:
            row.on_cv = body.on_cv
            if body.on_cv and row.state == TruthState.INFERRED:
                row.state = TruthState.CONFIRMED.value
        row.updated_at = st.now()
        st.save(row)
        return Reports(db).achievement(row)

    @app.get("/api/memory")
    def get_memory(type: str | None = None, state: str | None = None):
        return Reports(db).memory(type or None, state or None)

    @app.get("/api/insights")
    def get_insights(period: str = "week"):
        if period not in ("week", "month"):
            raise HTTPException(400, "period must be week or month.")
        return Reports(db).insights(period)

    # --- cv -------------------------------------------------------------------------------
    @app.get("/api/cv")
    def get_cv():
        st = store()
        if not st.cv_bullets() and st.get_state("cv_generated_at") is None:
            return cv_engine.to_dict(cv_engine.generate(st))
        return cv_engine.to_dict(cv_engine.load(st))

    @app.post("/api/cv/regenerate")
    def post_cv():
        s = settings()
        return cv_engine.to_dict(cv_engine.generate(store(), get_provider(s.ai), polish=s.ai.polish_cv))

    @app.patch("/api/cv/bullets/{bullet_id}")
    def patch_bullet(bullet_id: str, body: schemas.BulletPatch):
        try:
            cv_engine.edit_bullet(store(), bullet_id, body.text)
        except KeyError as exc:
            raise HTTPException(404, "That bullet no longer exists. Regenerate the CV and try again.") from exc
        return cv_engine.to_dict(cv_engine.load(store()))

    @app.get("/api/cv/export")
    def export_cv(format: str = "md"):
        cv = cv_engine.load(store())
        stem = (cv.name or "cv").replace(" ", "_")
        out = Path(tempfile.mkdtemp(prefix="career-cv-"))
        if format == "md":
            path = out / f"{stem}_CV.md"
            path.write_text(cv_engine.to_markdown(cv), encoding="utf-8")
            media = "text/markdown"
        elif format == "json":
            path = out / f"{stem}_CV.json"
            path.write_text(cv_engine.to_json(cv), encoding="utf-8")
            media = "application/json"
        elif format == "docx":
            path = cv_engine.to_docx(cv, out / f"{stem}_CV.docx")
            media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif format == "pdf":
            path = cv_engine.to_pdf(cv, out / f"{stem}_CV.pdf")
            media = "application/pdf"
        else:
            raise HTTPException(400, "format must be md, docx, pdf or json.")
        return FileResponse(path, media_type=media, filename=path.name)

    # --- profile & settings -------------------------------------------------------------------
    @app.get("/api/profile")
    def get_profile():
        return store().get_profile().model_dump(mode="json")

    @app.put("/api/profile")
    def put_profile(profile: Profile):
        st = store()
        saved = st.save_profile(profile.model_copy(update={"setup_at": st.get_profile().setup_at or profile.setup_at}))
        ensure_profile_projects(st)
        s = settings()
        if saved.ai_provider in ("claude", "gemini", "openai", "local", "none") and s.ai.provider != saved.ai_provider:
            s.ai.provider = saved.ai_provider
        s.general.language = saved.language
        save_settings(s, paths.config)
        return saved.model_dump(mode="json")

    def settings_dict(s: Settings) -> dict:
        d = s.model_dump()
        d["ai"]["key_configured"] = s.ai.provider in ("local", "none") or has_key(s.ai.provider)
        return d

    @app.get("/api/settings")
    def get_settings():
        return settings_dict(settings())

    @app.put("/api/settings")
    def put_settings(body: dict = Body(...)):
        current = settings().model_dump()
        for section, values in body.items():
            if section in current and isinstance(values, dict):
                current[section].update({k: v for k, v in values.items() if k != "key_configured"})
        try:
            s = Settings.model_validate(current)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"Invalid settings: {exc}") from exc
        save_settings(s, paths.config)
        return settings_dict(s)

    @app.post("/api/analyze")
    def post_analyze(body: schemas.AnalyzeBody = Body(default_factory=schemas.AnalyzeBody)):
        s = settings()
        d = _day(body.date)
        open_until = utc_now() if read_agent_info(paths) and d == date.today() else None
        result = MemoryEngine(db, s, get_provider(s.ai)).update_day(d, open_until=open_until)
        return {"analyzed": result.analyzed, "pending": result.pending_ai}

    # --- live ----------------------------------------------------------------------------------
    @app.get("/api/stream")
    async def stream(request: Request):
        async def events():
            last = None
            while not await request.is_disconnected():
                payload = json.dumps(await asyncio.to_thread(status))
                if payload != last:
                    yield f"event: status\ndata: {payload}\n\n"
                    last = payload
                else:
                    yield ": keep-alive\n\n"
                await asyncio.sleep(5)

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.exception_handler(Exception)
    async def unexpected(_request: Request, exc: Exception):
        import logging

        logging.getLogger("career.server").exception("Unhandled error")
        return JSONResponse({"detail": f"Something went wrong: {exc}. Details are in the agent log."}, status_code=500)

    # --- dashboard (built React app) ---------------------------------------------------------------
    if (STATIC / "index.html").exists():
        if (STATIC / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                raise HTTPException(404, "Unknown API route.")
            file = (STATIC / path).resolve()
            if path and file.is_file() and STATIC.resolve() in file.parents:
                return FileResponse(file)
            return FileResponse(STATIC / "index.html")
    else:
        @app.get("/", include_in_schema=False)
        def no_dashboard():
            return JSONResponse({"detail": "The dashboard isn't built yet. Run `npm run build` in dashboard/."}, status_code=503)

    return app


def run(paths: Paths, settings: Settings, open_browser: bool = True) -> None:
    import threading
    import webbrowser

    import uvicorn

    url = f"http://{settings.server.host}:{settings.server.port}"
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(create_app(paths), host=settings.server.host, port=settings.server.port, log_level="warning")


__all__ = ["create_app", "run"]
