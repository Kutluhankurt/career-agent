"""`career` command-line entry point."""

from datetime import datetime
from pathlib import Path

import click
import typer

from career.cli import career_cmds, commands, system_cmds

app = typer.Typer(
    name="career",
    help="Career Agent: turns your daily work into a career record. Everything stays on this computer.",
    no_args_is_help=True,
    add_completion=False,
)
config_app = typer.Typer(help="Show or change settings.", invoke_without_command=True)
app.add_typer(config_app, name="config")


@app.command()
def version() -> None:
    """Show the installed version."""
    commands.version()


@app.command()
def setup() -> None:
    """Answer a few questions so the agent understands your work."""
    career_cmds.setup()


@app.command()
def status() -> None:
    """Show whether the agent is running and what it has collected."""
    commands.status()


@app.command()
def start(
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run in this terminal instead of the background."),
) -> None:
    """Start observing activity in the background."""
    commands.start(foreground)


@app.command()
def stop() -> None:
    """Stop the background agent."""
    commands.stop()


@app.command()
def pause(minutes: int = typer.Argument(60, help="How long to pause, in minutes.")) -> None:
    """Pause tracking for a while (nothing is observed while paused)."""
    commands.pause(minutes)


@app.command()
def resume() -> None:
    """Resume tracking after a pause."""
    commands.resume()


@app.command()
def events(
    today: bool = typer.Option(False, "--today", help="Only show today's events."),
    limit: int = typer.Option(50, "--limit", "-n", min=1, help="Maximum number of events to show."),
) -> None:
    """Show the most recent raw events."""
    commands.events(today, limit)


@app.command()
def sessions(
    day: datetime = typer.Option(None, "--date", "-d", formats=["%Y-%m-%d"], help="Day to show (YYYY-MM-DD). Default: today."),
) -> None:
    """Group raw events into work sessions and show them."""
    commands.sessions(day.date() if day else None)


@app.command()
def today(
    day: datetime = typer.Option(None, "--date", "-d", formats=["%Y-%m-%d"], help="Another day (YYYY-MM-DD)."),
) -> None:
    """Today's meaningful work, projects, skills and what needs review."""
    career_cmds.today(day.date() if day else None)


@app.command()
def review() -> None:
    """Confirm, edit or reject what the agent understood (Y / E / N)."""
    career_cmds.review()


@app.command()
def analyze(
    week: bool = typer.Option(False, "--week", help="Summarize this week."),
    month: bool = typer.Option(False, "--month", help="Summarize this month."),
    deep: bool = typer.Option(False, "--deep", help="Ask the AI about every session (uses more tokens)."),
    days: int = typer.Option(7, "--days", min=1, max=90, help="How many recent days to (re)analyze."),
) -> None:
    """Analyze collected sessions, or summarize the week/month."""
    career_cmds.analyze(week, month, deep, days)


@app.command()
def skills() -> None:
    """Skills discovered from your work, with evidence-based scores."""
    career_cmds.skills()


@app.command()
def projects() -> None:
    """Projects discovered from your work."""
    career_cmds.projects()


@app.command()
def achievements() -> None:
    """Potential and confirmed achievements."""
    career_cmds.achievements()


@app.command()
def memory() -> None:
    """Everything in your Career Memory."""
    career_cmds.memory()


@app.command()
def cv(
    format: str = typer.Option(None, "--format", "-f", click_type=click.Choice(["md", "pdf", "docx", "json"]),
                               help="Save as a file instead of printing."),
    output: Path = typer.Option(None, "--output", "-o", help="Where to save the file."),
    regenerate: bool = typer.Option(False, "--regenerate", "-r", help="Rebuild from the latest Career Memory."),
) -> None:
    """Your CV, written from real work evidence."""
    career_cmds.cv(format, output, regenerate)


@app.command()
def dashboard(no_browser: bool = typer.Option(False, "--no-browser", help="Don't open a browser window.")) -> None:
    """Open the local dashboard (http://127.0.0.1:7342)."""
    system_cmds.dashboard(not no_browser)


@config_app.callback()
def config(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        system_cmds.config_show()


@config_app.command("ai")
def config_ai() -> None:
    """Choose the AI provider and store its API key in the OS keychain."""
    system_cmds.config_ai()


@config_app.command("set")
def config_set(key: str, value: str) -> None:
    """Change one setting, e.g. `career config set collector.idle_threshold 240`."""
    system_cmds.config_set(key, value)


@config_app.command("forget-key")
def config_forget_key(provider: str = typer.Argument(..., click_type=click.Choice(["claude", "openai", "gemini"]))) -> None:
    """Remove a stored API key from the keychain."""
    system_cmds.config_forget_key(provider)


@app.command()
def export(
    format: str = typer.Option("json", "--format", "-f", click_type=click.Choice(["json", "csv", "md"])),
    output: Path = typer.Option(None, "--output", "-o"),
) -> None:
    """Export all your data (JSON, CSV or Markdown)."""
    system_cmds.export(format, output)


@app.command("import")
def import_(file: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    """Import a JSON export (adds what's missing, never overwrites)."""
    system_cmds.import_(file)


@app.command()
def backup(output: Path = typer.Option(None, "--output", "-o", help="Folder for the backup zip.")) -> None:
    """Create career-backup-YYYY-MM-DD.zip (database + config, no secrets)."""
    system_cmds.backup(output)


@app.command()
def restore(file: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    """Restore a backup zip."""
    system_cmds.restore(file)


@app.command()
def autostart(action: str = typer.Argument("status", click_type=click.Choice(["on", "off", "status"]))) -> None:
    """Start Career Agent automatically when you log in."""
    system_cmds.autostart(action)


if __name__ == "__main__":
    app()
