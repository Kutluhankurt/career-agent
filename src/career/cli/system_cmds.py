"""System commands: dashboard, config, export, import, backup, restore, autostart."""

from datetime import datetime
from pathlib import Path

import click
import typer

from career.ai import PROVIDERS, get_provider
from career.ai.keys import delete_key, has_key, set_key
from career.cli.output import console, tilde
from career.config import get_paths, load_settings, save_settings
from career.database.database import Database


def dashboard(open_browser: bool) -> None:
    from career.server.app import STATIC, run

    paths = get_paths().ensure()
    settings = load_settings(paths.config)
    url = f"http://{settings.server.host}:{settings.server.port}"
    if not (STATIC / "index.html").exists():
        console.print("[yellow]The dashboard UI isn't built in this install; the API is still available.[/]")
    console.print(f"Career Agent dashboard: [bold]{url}[/]  (Ctrl+C to stop)")
    run(paths, settings, open_browser=open_browser)


def config_show() -> None:
    paths = get_paths()
    settings = load_settings(paths.config)
    console.print(f"[dim]{tilde(paths.config)}[/]\n")
    for section, values in settings.model_dump().items():
        console.print(f"[bold][{section}][/]")
        for k, v in values.items():
            console.print(f"  {k} = {v!r}")
    provider = settings.ai.provider
    if provider in ("claude", "openai", "gemini"):
        console.print(f"\nAPI key for {provider}: {'configured' if has_key(provider) else '[yellow]missing[/]'} (OS keychain)")


def config_set(key: str, value: str) -> None:
    paths = get_paths()
    settings = load_settings(paths.config).model_dump()
    if "." not in key:
        raise typer.BadParameter("Use section.key, for example collector.idle_threshold")
    section, name = key.split(".", 1)
    if section not in settings or name not in settings[section]:
        raise typer.BadParameter(f"Unknown setting {key}. See `career config`.")
    current = settings[section][name]
    if isinstance(current, bool):
        parsed = value.lower() in ("1", "true", "yes", "on")
    elif isinstance(current, (int, float)):
        parsed = type(current)(value)
    elif isinstance(current, list):
        parsed = [v.strip() for v in value.split(",") if v.strip()]
    else:
        parsed = value
    settings[section][name] = parsed
    from career.config.settings import Settings

    save_settings(Settings.model_validate(settings), paths.config)
    console.print(f"{key} = {parsed!r}. Restart the agent for collector changes to apply.")


def config_ai() -> None:
    paths = get_paths()
    settings = load_settings(paths.config)
    console.print("Select AI provider:")
    for i, p in enumerate(PROVIDERS, 1):
        note = {"none": "built-in rules, fully offline", "local": "Ollama on this computer"}.get(p, "")
        console.print(f"  {i}. {p}" + (f" [dim]({note})[/]" if note else ""))
    choice = typer.prompt("Number", type=click.IntRange(1, len(PROVIDERS)),
                          default=PROVIDERS.index(settings.ai.provider) + 1 if settings.ai.provider in PROVIDERS else 5)
    provider = PROVIDERS[choice - 1]
    settings.ai.provider = provider
    if provider in ("claude", "openai", "gemini"):
        if has_key(provider) and not typer.confirm("A key is already configured. Replace it?", default=False):
            pass
        else:
            key = typer.prompt(f"{provider} API key", hide_input=True, default="", show_default=False)
            if key:
                try:
                    set_key(provider, key)
                    console.print("[green]Saved to the OS keychain.[/]")
                except Exception as exc:  # noqa: BLE001
                    console.print(f"[red]Couldn't use the keychain: {exc}[/]\nSet the environment variable instead "
                                  f"({'ANTHROPIC_API_KEY' if provider == 'claude' else provider.upper() + '_API_KEY'}).")
    model = typer.prompt("Model (empty = provider default)", default=settings.ai.model or "", show_default=False)
    settings.ai.model = model.strip()
    save_settings(settings, paths.config)
    p = get_provider(settings.ai)
    if p is None:
        console.print("Using built-in rules. No data leaves this computer.")
    else:
        extra = {"claude": "claude", "openai": "openai", "gemini": "gemini"}.get(provider)
        ok = p.available()
        console.print(f"{provider} ({p.model}): " + ("[green]ready[/]" if ok else "[yellow]not available[/]"))
        if not ok and extra:
            console.print(f"[dim]Make sure the SDK is installed: uv pip install 'career-agent[{extra}]'[/]")
        if not ok and provider == "local":
            console.print(f"[dim]Start Ollama and pull the model: ollama pull {p.model}[/]")


def config_forget_key(provider: str) -> None:
    delete_key(provider)
    console.print(f"Removed the {provider} key from the keychain.")


def export(fmt: str, output: Path | None) -> None:
    from career import data

    db = Database(get_paths().ensure().database)
    stamp = datetime.now().strftime("%Y-%m-%d")
    if fmt == "json":
        path = data.export_json(db, output or Path.cwd() / f"career-export-{stamp}.json")
    elif fmt == "csv":
        path = data.export_csv(db, output or Path.cwd() / f"career-export-{stamp}")
    else:
        path = data.export_markdown(db, output or Path.cwd() / f"career-export-{stamp}.md")
    console.print(f"Exported to {path}")


def import_(file: Path) -> None:
    from career import data

    counts = data.import_json(Database(get_paths().ensure().database), file)
    total = sum(counts.values())
    console.print(f"Imported {total:,} new records" + (": " + ", ".join(f"{k} {v}" for k, v in counts.items() if v) if total else "."))


def backup(output: Path | None) -> None:
    from career import data

    path = data.backup(get_paths().ensure(), output)
    console.print(f"Backup saved: {path}\n[dim]Contains the database and configuration. API keys are not included.[/]")


def restore(file: Path) -> None:
    from career import data
    from career.agent import read_agent_info

    paths = get_paths()
    if read_agent_info(paths):
        raise typer.BadParameter("Stop the agent first: career stop")
    if not typer.confirm(f"Replace the current data with {file.name}? The current database is kept as career.db.before-restore",
                         default=False):
        return
    data.restore(paths, file)
    console.print("Restored.")


def autostart(action: str) -> None:
    from career import autostart as auto

    if action == "on":
        console.print(f"Career Agent will start at login ({auto.enable()}).")
    elif action == "off":
        console.print("Autostart removed." if auto.disable() else "Autostart wasn't enabled.")
    else:
        console.print("Autostart: " + ("on" if auto.is_enabled() else "off"))
