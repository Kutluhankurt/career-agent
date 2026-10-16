"""Export, import and backup (roadmap §56–58). The user owns their data.

Secrets are never included: API keys live in the OS keychain, not in these files.
"""

import csv
import json
import sqlite3
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from career import __version__
from career.config import Paths
from career.database.database import Database
from career.database.models import Base

EXPORT_TABLES = ["events", "sessions", "user_profile", "projects", "ai_analysis", "skills", "skill_scores",
                 "achievements", "review_items", "cv_bullets"]


def _rows(db: Database, table: str) -> list[dict[str, Any]]:
    t = Base.metadata.tables[table]
    with db.engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(select(t))]


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Not serializable: {type(value)}")


def export_json(db: Database, path: Path) -> Path:
    data = {"format": "career-agent-export", "version": __version__, "exported_at": datetime.now().astimezone().isoformat(),
            "tables": {t: _rows(db, t) for t in EXPORT_TABLES}}
    path.write_text(json.dumps(data, default=_json_default, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def export_csv(db: Database, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for table in EXPORT_TABLES:
        rows = _rows(db, table)
        columns = [c.name for c in Base.metadata.tables[table].columns]
        with (folder / f"{table}.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns)
            writer.writeheader()
            for r in rows:
                writer.writerow({k: json.dumps(v, default=_json_default, ensure_ascii=False) if isinstance(v, (dict, list))
                                 else (v.isoformat() if isinstance(v, (datetime, date)) else v) for k, v in r.items()})
    return folder


def export_markdown(db: Database, path: Path) -> Path:
    from career.career import cv as cv_engine
    from career.career.reports import Reports
    from career.career.store import MemoryStore

    reports, store = Reports(db), MemoryStore(db)
    profile = store.get_profile()
    lines = [f"# Career record — {profile.name or 'me'}", "", f"Exported {datetime.now():%d %B %Y} by Career Agent {__version__}.", ""]
    lines += ["## Projects", ""]
    for p in reports.projects():
        lines.append(f"- **{p['name']}** ({p['state']}): {round(p['active_seconds'] / 3600, 1)} h, {p['session_count']} sessions"
                     + (f", tickets {', '.join(p['tickets'][:5])}" if p["tickets"] else ""))
    lines += ["", "## Skills", ""]
    for s in reports.skills(date.today())[:25]:
        lines.append(f"- {s['name']} — {s['score']} ({s['category']}, {s['state']})")
    lines += ["", "## Achievements", ""]
    for a in reports.achievements():
        lines.append(f"- {a['title']} ({a['state']})" + (f" — impact: {a['impact']}" if a["impact"] else ""))
    lines += ["", "## CV", "", cv_engine.to_markdown(cv_engine.load(store))]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def import_json(db: Database, path: Path) -> dict[str, int]:
    """Adds rows that aren't already present (matched by primary key). Never overwrites."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "career-agent-export":
        raise ValueError("This file isn't a Career Agent export (expected `career export --format json` output).")
    counts: dict[str, int] = {}
    with db.engine.begin() as conn:
        for table, rows in data.get("tables", {}).items():
            if table not in EXPORT_TABLES:
                continue
            t = Base.metadata.tables[table]
            pk = [c.name for c in t.primary_key.columns]
            existing = {tuple(r) for r in conn.execute(select(*[t.c[k] for k in pk]))}
            added = 0
            for row in rows:
                if tuple(row.get(k) for k in pk) in existing:
                    continue
                values = {}
                for col in t.columns:
                    if col.name not in row:
                        continue
                    v = row[col.name]
                    if v is not None and col.type.python_type in (datetime,):
                        v = datetime.fromisoformat(v)
                    values[col.name] = v
                conn.execute(t.insert().values(**values))
                added += 1
            counts[table] = added
    return counts


def backup(paths: Paths, target_dir: Path | None = None) -> Path:
    """Consistent snapshot of the database plus config, as career-backup-YYYY-MM-DD.zip."""
    target_dir = target_dir or paths.backups
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    out = target_dir / f"career-backup-{stamp}.zip"
    n = 1
    while out.exists():
        n += 1
        out = target_dir / f"career-backup-{stamp}-{n}.zip"
    snapshot = target_dir / ".career-snapshot.db"
    src = sqlite3.connect(paths.database)
    dst = sqlite3.connect(snapshot)
    with dst:
        src.backup(dst)  # safe while the agent is writing
    src.close()
    dst.close()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(snapshot, "career.db")
        if paths.config.exists():
            zf.write(paths.config, "config.toml")
        zf.writestr("README.txt", f"Career Agent {__version__} backup, {datetime.now():%Y-%m-%d %H:%M}.\n"
                                  "Restore: career restore <this file>. API keys are not included (they stay in your keychain).\n")
    snapshot.unlink(missing_ok=True)
    return out


def restore(paths: Paths, archive: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        if "career.db" not in names:
            raise ValueError("This zip isn't a Career Agent backup (career.db missing).")
        paths.ensure()
        if paths.database.exists():
            paths.database.replace(paths.database.with_suffix(".db.before-restore"))
        for suffix in ("-wal", "-shm"):
            Path(str(paths.database) + suffix).unlink(missing_ok=True)
        with zf.open("career.db") as src, paths.database.open("wb") as dst:
            dst.write(src.read())
        if "config.toml" in names:
            with zf.open("config.toml") as src, paths.config.open("wb") as dst:
                dst.write(src.read())
    Database(paths.database).close()  # run migrations on the restored file


__all__ = ["backup", "export_csv", "export_json", "export_markdown", "import_json", "restore"]
