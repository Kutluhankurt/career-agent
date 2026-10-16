"""Command implementations, kept separate from Typer wiring for testability."""

from datetime import date, datetime, timedelta

from career import __version__
from career.agent import pause as pause_agent
from career.agent import read_agent_info, read_pause, run_foreground, spawn_background, stop_agent, wait_for_start
from career.agent import resume as resume_agent
from career.analysis.service import rebuild_day
from career.cli.output import console, duration, events_table, sessions_table, tilde
from career.collector import platform_name
from career.config import get_paths, load_settings, save_settings
from career.database.database import Database
from career.events.models import EventType, utc_now


def _today_start() -> datetime:
    return datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)


def version() -> None:
    console.print(f"Career Agent v{__version__}")


def status() -> None:
    paths = get_paths()
    info = read_agent_info(paths)
    console.print(f"[bold]Career Agent[/] v{__version__}")
    console.print(f"Platform: {platform_name()}")
    console.print(f"Database: {tilde(paths.database)}")
    paused_until = read_pause(paths)
    if info and paused_until:
        console.print(f"Status:   [bold yellow]PAUSED[/] until {paused_until.astimezone():%H:%M} (pid {info.pid})")
        console.print(f"Uptime:   {duration(utc_now() - info.started_at)}")
    elif info:
        console.print(f"Status:   [bold green]RUNNING[/] (pid {info.pid})")
        console.print(f"Uptime:   {duration(utc_now() - info.started_at)}")
    else:
        console.print("Status:   [dim]stopped[/]")
    if not paths.database.exists():
        return
    db = Database(paths.database)
    try:
        console.print(f"Events:   {db.count_events():,} total, {db.count_events(since=_today_start()):,} today")
        console.print(f"Sessions: {db.count_sessions(since=_today_start()):,} today")
        last_focus = db.last_event(EventType.WINDOW_FOCUS)
        last = db.last_event()
        if info and last and last.type == EventType.IDLE_STARTED:
            console.print("Current:  [yellow]idle[/]")
        elif info and last_focus:
            console.print(f"Current:  {last_focus.application or '?'} — {last_focus.window_title or ''}")
    finally:
        db.close()


def start(foreground: bool) -> None:
    paths = get_paths()
    info = read_agent_info(paths)
    if info:
        console.print(f"Career Agent is already running (pid {info.pid}).")
        return
    settings = load_settings(paths.config)
    if not paths.config.exists():
        save_settings(settings, paths.config)
    if not foreground and _first_run(paths):
        import sys

        if sys.stdin.isatty() and sys.stdout.isatty():  # only ask when a person is actually at a terminal
            from career.cli import career_cmds

            career_cmds.setup()
            settings = load_settings(paths.config)
        else:
            console.print("Tip: run `career setup` so the agent knows your role and projects.")
    if foreground:
        console.print("Career Agent running in the foreground. Press Ctrl+C to stop.")
        run_foreground(paths, settings, console=False)
        return
    spawn_background(paths)
    info = wait_for_start(paths)
    if info:
        console.print(f"[green]Career Agent started[/] (pid {info.pid}). Logs: {tilde(paths.log_file)}")
    else:
        console.print(f"[red]Career Agent did not start.[/] Check {tilde(paths.log_file)} or run `career start --foreground`.")
        raise SystemExit(1)


def _first_run(paths) -> bool:
    from career.career.store import MemoryStore

    db = Database(paths.database)
    try:
        return not MemoryStore(db).get_profile().complete
    finally:
        db.close()


def pause(minutes: int) -> None:
    paths = get_paths()
    until = pause_agent(paths, minutes)
    console.print(f"Tracking paused until {until.astimezone():%H:%M}. Resume any time with `career resume`.")


def resume() -> None:
    resume_agent(get_paths())
    console.print("Tracking resumed.")


def stop() -> None:
    paths = get_paths()
    if stop_agent(paths):
        console.print("Career Agent stopped.")
    else:
        console.print("Career Agent is not running.")


def events(today: bool, limit: int) -> None:
    paths = get_paths()
    if not paths.database.exists():
        console.print("No events yet. Start collecting with `career start`.")
        return
    db = Database(paths.database)
    try:
        since = _today_start() if today else None
        rows = list(reversed(db.list_events(since=since, limit=limit, newest_first=True)))
    finally:
        db.close()
    if not rows:
        console.print("No events for this period.")
        return
    console.print(events_table(rows))


def sessions(day: date | None) -> None:
    paths = get_paths()
    if not paths.database.exists():
        console.print("No events yet. Start collecting with `career start`.")
        return
    day = day or date.today()
    settings = load_settings(paths.config)
    running = read_agent_info(paths) is not None
    open_until = utc_now() if running and day == date.today() else None
    db = Database(paths.database)
    try:
        event_count, rows = rebuild_day(db, settings, day, open_until=open_until)
    finally:
        db.close()
    title = "Today" if day == date.today() else day.strftime("%A, %d %B %Y")
    if not rows:
        console.print(f"{title}: {event_count:,} events, no sessions yet.")
        return
    active = sum(s.active_seconds for s in rows)
    console.print(f"[bold]{title}[/]  {event_count:,} events → {len(rows)} session{"s" if len(rows) != 1 else ""} · {duration(timedelta(seconds=active))} active\n")
    console.print(sessions_table(rows))
