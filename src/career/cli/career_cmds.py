"""Career commands: setup, today, review, analyze, skills, projects, achievements, memory, cv."""

import sys
from datetime import date, timedelta
from pathlib import Path

import click
import typer
from rich.panel import Panel
from rich.table import Table

from career.agent import read_agent_info
from career.ai import PROVIDERS, get_provider
from career.ai.keys import has_key, set_key
from career.analysis.confidence import band
from career.cli.output import console, duration
from career.config import get_paths, load_settings, save_settings
from career.database.database import Database
from career.events.models import utc_now
from career.profile.models import Profile


def _db() -> Database:
    return Database(get_paths().ensure().database)


def _h(seconds: float) -> str:
    return duration(timedelta(seconds=seconds))


def _bar(score: float, width: int = 14) -> str:
    filled = round(score / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


# --- setup (roadmap §15) ------------------------------------------------------
def _ask_list(question: str, default: list[str]) -> list[str]:
    answer = typer.prompt(question, default=", ".join(default) if default else "", show_default=bool(default))
    return [x.strip() for x in answer.split(",") if x.strip()]


def setup() -> None:
    from career import autostart
    from career.career.projects import ensure_profile_projects
    from career.career.store import MemoryStore

    paths = get_paths().ensure()
    db = _db()
    store = MemoryStore(db)
    current = store.get_profile()
    console.print(Panel.fit("[bold]Welcome to Career Agent.[/]\nIt quietly turns your daily work into a career record.\n"
                            "Everything stays on this computer. Keystrokes, passwords, screenshots,\n"
                            "microphone and camera are never recorded.", border_style="blue"))
    name = typer.prompt("What's your name?", default=current.name or "", show_default=bool(current.name))
    job = typer.prompt("What's your job title?", default=current.job_title or "", show_default=bool(current.job_title))
    focus = typer.prompt("What do you mainly work on?", default=current.focus or "", show_default=bool(current.focus))
    projects = _ask_list("What are your current projects? (comma separated)", current.projects)
    tools = _ask_list("Which tools do you use? (comma separated)", current.tools)
    screen = typer.confirm("Enable advanced screen understanding? (reads nothing until you turn it on)", default=False)
    console.print("\nAI provider for understanding sessions: " + " · ".join(PROVIDERS))
    console.print("[dim]'none' works fully offline with built-in rules. You can change this any time.[/]")
    provider = typer.prompt("Provider", default=current.ai_provider if current.ai_provider in PROVIDERS else "none",
                            type=click.Choice(PROVIDERS))
    if provider in ("claude", "openai", "gemini") and not has_key(provider):
        key = typer.prompt(f"{provider} API key (stored in your OS keychain, leave empty to skip)", default="",
                           hide_input=True, show_default=False)
        if key:
            try:
                set_key(provider, key)
                console.print("[green]Key saved to the keychain.[/]")
            except Exception as exc:  # noqa: BLE001
                console.print(f"[yellow]Couldn't save to the keychain ({exc}). Set the API key as an environment variable instead.[/]")
    start_at_login = typer.confirm("Start Career Agent when you log in?", default=current.autostart)

    profile = Profile(name=name, job_title=job, focus=focus, projects=projects, tools=tools, screen_understanding=screen,
                      autostart=start_at_login, ai_provider=provider, language=current.language, setup_at=current.setup_at)
    store.save_profile(profile)
    ensure_profile_projects(store)
    settings = load_settings(paths.config)
    settings.ai.provider = provider
    settings.privacy.screen_understanding = screen
    save_settings(settings, paths.config)
    if start_at_login:
        console.print(f"Autostart: {autostart.enable()}")
    else:
        autostart.disable()
    console.print("\n[bold green]You're set.[/] For the first 7 days I'll ask a few questions to learn your work.\n"
                  "Start observing with [bold]career start[/]; see your day with [bold]career today[/].")


# --- today (roadmap §29) ------------------------------------------------------------
def today(day: date | None = None) -> None:
    from career.career.memory import MemoryEngine
    from career.career.reports import Reports

    db = _db()
    settings = load_settings(get_paths().config)
    d = day or date.today()
    running = read_agent_info(get_paths()) is not None
    MemoryEngine(db, settings, None).update_day(d, open_until=utc_now() if running and d == date.today() else None)
    t = Reports(db).today(d)
    title = "TODAY" if d == date.today() else d.strftime("%A %d %B").upper()
    console.print(f"[bold]{title}[/]\n")
    rows = [("Meaningful work", _h(t["active_seconds"])), ("Sessions", str(t["session_count"])),
            ("Projects", str(t["project_count"]))]
    for k, v in rows:
        console.print(f"[dim]{k:<24}[/]{v}")
    if t["top_skills"]:
        console.print(f"[dim]{'Top skills':<24}[/]" + ", ".join(s["name"] for s in t["top_skills"][:3]))
    sessions = [s for s in Reports(db).sessions(d) if s["state"] != "rejected"]
    if sessions:
        main = max(sessions, key=lambda s: s["active_seconds"])
        console.print(f"[dim]{'Main activity':<24}[/]{main['activity']}")
    console.print(f"[dim]{'Potential achievements':<24}[/]{len([a for a in t['potential_achievements'] if a['state'] == 'inferred'])}")
    console.print(f"[dim]{'Unconfirmed':<24}[/]{t['review_count']}")
    if t["current_session"]:
        c = t["current_session"]
        console.print(f"\n[green]●[/] Now: {c['activity']} ({_h(c['active_seconds'])})")
    if t["review_count"]:
        console.print("\nRun [bold]career review[/] to confirm what I understood.")


# --- review (roadmap §28) --------------------------------------------------------------
def _key(prompt: str, allowed: str) -> str:
    if _interactive():
        console.print(prompt, end=" ")
        while True:
            ch = click.getchar().lower()
            if ch in allowed:
                console.print(ch.upper())
                return ch
    return typer.prompt(prompt, type=click.Choice(list(allowed)), show_choices=False).lower()


def review() -> None:
    from career.career.memory import MemoryEngine
    from career.career.reports import Reports
    from career.career.review import resolve
    from career.career.store import MemoryStore

    db = _db()
    MemoryEngine(db, load_settings(get_paths().config), None).update_day(date.today())
    items = Reports(db).review_items()
    store = MemoryStore(db)
    if not items:
        console.print("You're up to date. Nothing to review.")
        return
    console.print(f"[bold]Review[/] — {len(items)} item{'s' if len(items) != 1 else ''}\n")
    done = 0
    for i, item in enumerate(items, 1):
        lines = [f"[dim]{item['subtitle']}[/]", f"[bold]{item['title']}[/]"]
        if item["project"]:
            lines.append(f"Project: {item['project']['name']}")
        if item["skills"]:
            lines.append("Skills: " + ", ".join(item["skills"]))
        if item["evidence"]:
            lines.append("Evidence: " + ", ".join(e["value"] for e in item["evidence"][:6]))
        if item["kind"] != "question" and item["kind"] != "project":
            lines.append(f"Confidence: {band(item['confidence'])} ({round(item['confidence'] * 100)}%)")
        console.print(Panel("\n".join(lines), title=f"{i}/{len(items)}", title_align="left", border_style="blue"))
        if item["options"]:
            ch = _key("[Y] Yes  [N] No  [S] Skip  [Q] Quit", "ynsq")
            if ch == "q":
                break
            if ch in "yn":
                resolve(store, item["id"], "answer", answer="yes" if ch == "y" else "no")
                done += 1
            continue
        ch = _key("[Y] Confirm  [E] Edit  [N] Reject  [S] Skip  [Q] Quit", "yensq")
        if ch == "q":
            break
        if ch == "s":
            continue
        if ch == "e":
            title = typer.prompt("New name", default=item["title"])
            resolve(store, item["id"], "edit", title=title)
        else:
            resolve(store, item["id"], "confirm" if ch == "y" else "reject")
        done += 1
    console.print(f"\n{done} item{'s' if done != 1 else ''} reviewed. Confirmed items are now in your Career Memory.")


# --- analyze (roadmap §30, §31, §40) ------------------------------------------------------
def analyze(week: bool, month: bool, deep: bool, days: int) -> None:
    from career.career.memory import MemoryEngine
    from career.career.reports import Reports

    paths = get_paths()
    db = _db()
    settings = load_settings(paths.config)
    provider = get_provider(settings.ai)
    if provider and not provider.available():
        console.print(f"[yellow]{settings.ai.provider} isn't available right now; using built-in rules. "
                      "Run `career config ai` to fix it.[/]")
        provider = None
    if week or month:
        _period(Reports(db), "month" if month else "week")
        return
    end = date.today()
    running = read_agent_info(paths) is not None
    engine = MemoryEngine(db, settings, provider)
    with console.status("Analyzing…"):
        results = []
        for offset in range(days - 1, -1, -1):
            d = end - timedelta(days=offset)
            results.append(engine.update_day(d, open_until=utc_now() if running and d == end else None, deep=deep))
    sessions = sum(r.sessions for r in results)
    analyzed = sum(r.analyzed for r in results)
    ai = sum(r.ai_analyzed for r in results)
    console.print(f"Analyzed {analyzed} of {sessions} sessions over {days} day{'s' if days != 1 else ''}"
                  + (f" ({ai} with {provider.name})" if provider else " (built-in rules)") + ".")
    console.print(f"Waiting for review: {results[-1].review_count}. Run [bold]career review[/].")


def _period(r, period: str) -> None:
    ins = r.insights(period)
    title = "THIS WEEK" if period == "week" else "THIS MONTH"
    console.print(f"[bold]{title}[/]  [dim]{ins['start']} → {ins['end']}[/]\n")
    console.print(f"[dim]Meaningful work:[/] {_h(ins['active_seconds'])} in {ins['session_count']} sessions\n")
    if ins["projects"]:
        console.print("[bold]What did I work on?[/]")
        for p in ins["projects"]:
            console.print(f"  {p['name']:<24} {_h(p['seconds']):>8}  {round(p['share'] * 100):>3}%")
    if ins["top_activities"]:
        console.print("\n[bold]Main activities[/]")
        for a in ins["top_activities"]:
            console.print(f"  {a['name']:<36} {_h(a['seconds']):>8}  ×{a['count']}")
    if ins["skills_up"]:
        console.print("\n[bold]Which skills grew?[/]")
        for s in ins["skills_up"]:
            console.print(f"  [green]↑[/] {s['name']} (+{s['delta']})")
    if ins["skills_down"]:
        for s in ins["skills_down"]:
            console.print(f"  [yellow]↓[/] {s['name']} ({s['delta']})")
    if ins["achievements"]:
        console.print("\n[bold]What did I accomplish?[/]")
        for a in ins["achievements"]:
            console.print(f"  • {a['title']} [dim]({a['state']})[/]")
    if ins["repeated"]:
        console.print("\n[bold]What do I keep doing?[/]")
        for x in ins["repeated"]:
            console.print(f"  - {x}")
    if ins["stopped"]:
        console.print("\n[bold]What did I stop doing?[/]")
        for x in ins["stopped"]:
            console.print(f"  - {x}")
    console.print("\nSee what can go on your CV with [bold]career cv[/].")


# --- memory views ---------------------------------------------------------------------------
def skills() -> None:
    from career.career.reports import Reports

    rows = Reports(_db()).skills(date.today())
    if not rows:
        console.print("No skills yet. They appear after your first analyzed sessions.")
        return
    table = Table(box=None, show_header=True, header_style="bold")
    for col in ("Skill", "", "Score", "7d", "Kind", "State"):
        table.add_column(col)
    for s in rows[:30]:
        delta = s["score"] - s["previous_score"]
        table.add_row(s["name"], _bar(s["score"]), str(s["score"]), (f"[green]+{delta}[/]" if delta > 0 else str(delta) if delta else ""),
                      s["category"], s["state"])
    console.print(table)
    console.print("\n[dim]Scores come from frequency, complexity, project diversity, evidence and your confirmations, not just time.[/]")


def projects() -> None:
    from career.career.reports import Reports

    rows = Reports(_db()).projects()
    if not rows:
        console.print("No projects yet.")
        return
    for p in rows:
        console.print(f"[bold]{p['name']}[/] [dim]({p['state']})[/]")
        console.print("─" * max(14, len(p["name"])))
        console.print(f"Activity: {_h(p['active_seconds'])}   Sessions: {p['session_count']}   Tickets: {len(p['tickets'])}"
                      f"   Repositories: {len(p['repos'])}   Achievements: {p['achievement_count']}")
        if p["skills"]:
            console.print(f"Skills: {', '.join(p['skills'])}")
        console.print()


def achievements() -> None:
    from career.career.reports import Reports

    rows = Reports(_db()).achievements()
    if not rows:
        console.print("No achievements yet. They show up when work forms a full story: problem → fix → verified.")
        return
    for a in rows:
        steps = " → ".join(f"[green]{s['name']}[/]" if s["done"] else f"[dim]{s['name']}[/]" for s in a["steps"])
        console.print(f"[bold]{a['title']}[/] [dim]({a['state']}, {round(a['confidence'] * 100)}%)[/]")
        console.print(f"  {steps}")
        if a["impact"]:
            console.print(f"  Impact (yours): {a['impact']}")
        console.print()


def memory() -> None:
    from career.career.reports import Reports

    m = Reports(_db()).memory()
    c = m["counts"]
    console.print(f"[bold]Career Memory[/]  confirmed {c['confirmed']} · observed {c['observed']} · inferred {c['inferred']}"
                  f" · rejected {c['rejected']}\n")
    table = Table(box=None, show_header=True, header_style="bold")
    for col in ("Type", "Name", "State", "Project", "Detail"):
        table.add_column(col, overflow="ellipsis", no_wrap=True)
    for i in [x for x in m["items"] if x["type"] != "session"][:40]:
        table.add_row(i["type"], i["name"], i["state"], i["project"] or "", i["detail"])
    console.print(table)


def cv(fmt: str | None, output: Path | None, regenerate: bool) -> None:
    from career.career import cv as cv_engine
    from career.career.store import MemoryStore

    db = _db()
    settings = load_settings(get_paths().config)
    store = MemoryStore(db)
    provider = get_provider(settings.ai)
    if regenerate or not store.cv_bullets():
        with console.status("Writing your CV from Career Memory…"):
            result = cv_engine.generate(store, provider, polish=settings.ai.polish_cv)
    else:
        result = cv_engine.load(store)
    if fmt is None:
        console.print(cv_engine.to_markdown(result))
        weak = sum(1 for _, _, bullets in result.experience for b in bullets if b.weak)
        if weak:
            console.print(f"\n[yellow]{weak} line{'s' if weak != 1 else ''} need more evidence or your confirmation "
                          "(`career review`).[/]")
        console.print("[dim]Export: career cv --format pdf|docx|md|json[/]")
        return
    stem = (result.name or "cv").replace(" ", "_") + "_CV"
    path = output or Path.cwd() / f"{stem}.{fmt}"
    if fmt == "md":
        path.write_text(cv_engine.to_markdown(result), encoding="utf-8")
    elif fmt == "json":
        path.write_text(cv_engine.to_json(result), encoding="utf-8")
    elif fmt == "docx":
        cv_engine.to_docx(result, path)
    elif fmt == "pdf":
        cv_engine.to_pdf(result, path)
    console.print(f"Saved {path}")
