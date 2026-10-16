"""Rendering helpers for CLI output (Rich)."""

from datetime import datetime, timedelta

from rich.console import Console
from rich.table import Table

from career.analysis.models import WorkSession
from career.events.models import Event

console = Console()


def tilde(path) -> str:
    from pathlib import Path

    p = Path(path)
    try:
        return "~/" + str(p.relative_to(Path.home()))
    except ValueError:
        return str(p)


def duration(delta: timedelta) -> str:
    total = int(delta.total_seconds())
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m"
    return f"{seconds}s"


def local_time(ts: datetime) -> str:
    return ts.astimezone().strftime("%H:%M:%S")


def events_table(events: list[Event]) -> Table:
    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("Time", style="dim", no_wrap=True)
    table.add_column("Type", no_wrap=True)
    table.add_column("Application", no_wrap=True)
    table.add_column("Window", overflow="ellipsis", no_wrap=True, max_width=70)
    styles = {"idle_started": "yellow", "idle_ended": "green"}
    for e in events:
        detail = e.window_title or ""
        if e.type.value == "idle_started" and "idle_seconds" in e.metadata:
            detail = f"no input for {int(e.metadata['idle_seconds'])}s"
        table.add_row(local_time(e.timestamp), f"[{styles.get(e.type.value, 'cyan')}]{e.type.value}[/]", e.application or "", detail)
    return table


def _top(values: dict[str, float], n: int = 3) -> str:
    return ", ".join(list(values)[:n])


def sessions_table(sessions: list[WorkSession]) -> Table:
    # Time, duration, session name and score always fit; context columns appear when there's room.
    show_apps = console.width >= 80
    show_files = console.width >= 125
    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("Time", no_wrap=True)
    table.add_column("Active", justify="right", no_wrap=True)
    table.add_column("Session", no_wrap=True, overflow="ellipsis")
    if show_apps:
        table.add_column("Apps", style="dim", no_wrap=True, overflow="ellipsis", max_width=28)
    if show_files:
        table.add_column("Files", style="dim", no_wrap=True, overflow="ellipsis", max_width=40)
    table.add_column("Score", justify="right", no_wrap=True)
    for s in sessions:
        start = s.start.astimezone().strftime("%H:%M")
        end = "now" if s.is_open else s.end.astimezone().strftime("%H:%M")
        color = "green" if s.score >= 0.8 else "yellow" if s.score >= 0.6 else "dim"
        row = [f"{start}–{end}", duration(timedelta(seconds=s.active_seconds)), ("[green]● [/]" if s.is_open else "") + s.label]
        if show_apps:
            row.append(_top(s.applications))
        if show_files:
            row.append(_top(s.files, 2))
        row.append(f"[{color}]{s.score:.0%}[/]")
        table.add_row(*row)
    return table
