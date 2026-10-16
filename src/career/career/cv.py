"""CV Engine (roadmap §36–37). Every bullet maps to evidence; nothing is invented.

Bullets come from two places per project:
  * achievements the user confirmed (or put on the CV), with user-entered impact
  * clusters of analysed work by category ("Testing" sessions → a testing bullet)

Wording is template-based; an AI provider may polish it, but a polished bullet that
adds a number, percentage or new claim is thrown away. Edited bullets are kept as the
user wrote them on every regeneration. Rejected facts never appear.
"""

import hashlib
import json
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from career.ai.base import AIError, AIProvider
from career.career.evidence import TruthState
from career.career.skills import LANGUAGES, TOOLS, score_skills
from career.career.topics import file_topics as _file_topics
from career.career.store import MemoryStore, new_id
from career.database.models import AnalysisRow, CVBulletRow, ProjectRow

log = logging.getLogger(__name__)

_NUMBERS = re.compile(r"\d+(?:[.,]\d+)?")
_MIN_SECONDS = 30 * 60


@dataclass
class Bullet:
    id: str
    key: str
    text: str
    confidence: float
    state: str
    evidence: list[dict]
    weak: bool
    project: str


@dataclass
class CV:
    name: str
    title: str
    summary: str
    experience: list[tuple[str, int, list[Bullet]]] = field(default_factory=list)  # (project, color, bullets)
    skills: list[str] = field(default_factory=list)
    generated_at: datetime | None = None


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else ""


def _cluster_text(category: str, rows: list[AnalysisRow], project: str) -> str | None:
    topics = _file_topics(rows)
    topic = _join(topics)
    skills = Counter(s for a in rows for s in (a.skills or []))
    langs = [s for s, _ in skills.most_common() if s in LANGUAGES][:1]
    tools = [s for s, _ in skills.most_common() if s in TOOLS and s not in LANGUAGES][:2]
    tickets = {e["value"] for a in rows for e in (a.evidence or []) if e["type"] == "ticket"}
    if category == "Testing":
        what = f"{topic} testing workflows" if topic else "testing workflows"
        return f"Designed and executed {what}" + (f" with {_join(langs + tools)}" if langs or tools else "") + "."
    if category == "Development":
        return f"Built and maintained {project}" + (f" in {langs[0]}" if langs else "") + (
            f" with {_join(tools)}" if tools else "") + "."
    if category == "Investigation":
        return "Investigated and documented software issues" + (" across multiple tickets" if len(tickets) > 1 else "") + (
            f" using {_join(tools)}" if tools else "") + "."
    if category == "Analysis":
        return f"Analyzed {topic + ' ' if topic else ''}logs and test results" + (f" with {_join(langs + tools)}" if langs or tools else "") + "."
    if category == "Operations":
        return f"Operated and maintained {topic or 'deployed systems'}" + (f" using {_join(tools)}" if tools else "") + "."
    if category == "Documentation":
        return "Prepared technical documentation and reports."
    if category == "Design":
        return f"Designed {topic or 'system components'}."
    return None


def _canonical(evidence: list[dict], limit: int = 10, max_commits: int = 3) -> list[dict]:
    """One entry per distinct thing (type + value), with a stable id, so the same file or
    ticket backing two bullets is one evidence item; a few commits are enough to show."""
    out: dict[str, dict] = {}
    commits = 0
    for e in evidence:
        key = f"{e['type']}|{e['value']}"
        if key in out:
            continue
        if e["type"] == "git":
            if commits >= max_commits:
                continue
            commits += 1
        out[key] = {**e, "id": hashlib.sha1(key.encode()).hexdigest()[:12], "session_id": None}
    return list(out.values())[:limit]


def _key(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


def generate(store: MemoryStore, provider: AIProvider | None = None, polish: bool = True) -> CV:
    projects = {p.id: p for p in store.projects() if p.state != TruthState.REJECTED}
    analyses = [a for a in store.analyses() if a.state != TruthState.REJECTED and a.project_id in projects]
    achievements = [a for a in store.achievements() if a.state != TruthState.REJECTED and a.project_id in projects]
    existing = {b.key: b for b in store.cv_bullets()}

    by_project: dict[str, list[AnalysisRow]] = defaultdict(list)
    for a in analyses:
        by_project[a.project_id].append(a)
    order = sorted(by_project, key=lambda pid: -sum(a.active_seconds for a in by_project[pid]))

    drafted: list[Bullet] = []
    for pid in order:
        rows, project = by_project[pid], projects[pid]
        if sum(a.active_seconds for a in rows) < _MIN_SECONDS:
            continue
        for ach in [x for x in achievements if x.project_id == pid]:
            if ach.state == TruthState.INFERRED and not ach.on_cv:
                continue  # unconfirmed achievements wait for review
            ev = _canonical([e for step in (ach.steps or {}).values() for e in step])
            text = ach.title.rstrip(".") + (f", {ach.impact.strip().rstrip('.')}" if ach.impact else "") + "."
            drafted.append(Bullet(new_id(), _key("ach", ach.id), text, ach.confidence,
                                  ach.state, ev, len(ev) < 2, project.name))
        by_cat: dict[str, list[AnalysisRow]] = defaultdict(list)
        for a in rows:
            by_cat[a.category].append(a)
        for category, cat_rows in sorted(by_cat.items(), key=lambda kv: -sum(a.active_seconds for a in kv[1])):
            if len(cat_rows) < 2 and sum(a.active_seconds for a in cat_rows) < 3600:
                continue
            text = _cluster_text(category, cat_rows, project.name)
            if not text:
                continue
            ev = _canonical([e for a in cat_rows for e in (a.evidence or [])], limit=12)
            states = {a.state for a in cat_rows}
            state = TruthState.CONFIRMED if states == {TruthState.CONFIRMED} else (
                TruthState.OBSERVED if TruthState.CONFIRMED in states else TruthState.INFERRED)
            conf = round(sum(a.confidence for a in cat_rows) / len(cat_rows), 2)
            drafted.append(Bullet(new_id(), _key("cat", pid, category), text, conf, state.value, ev,
                                  len(ev) < 2 or state == TruthState.INFERRED, project.name))

    for b in drafted:  # keep ids stable and the user's own wording
        old = existing.get(b.key)
        if old:
            b.id = old.id
            if old.edited:
                b.text, b.state = old.text, TruthState.CONFIRMED.value

    if provider and polish and provider.available():
        _polish(provider, [b for b in drafted if not (existing.get(b.key) and existing[b.key].edited)])

    now = store.now()
    keep = {b.key for b in drafted}
    store.remove(CVBulletRow, CVBulletRow.key.not_in(keep) if keep else CVBulletRow.key.is_not(None))
    store.save(*[CVBulletRow(id=b.id, key=b.key, project_id=next((p.id for p in projects.values() if p.name == b.project), None),
                             project_name=b.project, text=b.text, evidence=b.evidence, confidence=b.confidence, state=b.state,
                             edited=bool(existing.get(b.key) and existing[b.key].edited), position=i, generated_at=now)
                 for i, b in enumerate(drafted)])
    store.set_state("cv_generated_at", now.isoformat())
    return load(store)


def _polish(provider: AIProvider, bullets: list[Bullet]) -> None:
    if not bullets:
        return
    try:
        polished = {p.id: p.text for p in provider.generate_cv([{"id": b.id, "text": b.text} for b in bullets])}
    except AIError as exc:
        log.warning("CV polish skipped: %s", exc)
        return
    for b in bullets:
        new = polished.get(b.id, "").strip()
        if not new or len(new) > 220:
            continue
        allowed = set(_NUMBERS.findall(b.text)) | set(_NUMBERS.findall(b.project))
        if set(_NUMBERS.findall(new)) - allowed:
            continue  # a number appeared from nowhere: not allowed
        b.text = new if new.endswith(".") else new + "."


def load(store: MemoryStore) -> CV:
    profile = store.get_profile()
    projects = {p.id: p for p in store.all(ProjectRow)}
    rows = store.cv_bullets()
    grouped: dict[str, list[Bullet]] = {}
    colors: dict[str, int] = {}
    for r in rows:
        grouped.setdefault(r.project_name, []).append(Bullet(
            r.id, r.key, r.text, r.confidence, r.state, r.evidence or [],
            len(r.evidence or []) < 2 or r.state == TruthState.INFERRED, r.project_name))
        colors[r.project_name] = projects[r.project_id].color if r.project_id in projects else 0
    from datetime import date

    scores = score_skills(store.analyses(), {s.name: s.state for s in store.skills()}, date.today())
    skills = [n for n, _ in sorted(scores.items(), key=lambda kv: -kv[1].score)][:12]
    generated = store.get_state("cv_generated_at")
    top_projects = list(grouped)[:3]
    summary_bits = [profile.job_title or "Engineer"]
    if profile.focus:
        summary_bits.append(f"focused on {profile.focus}")
    summary = " ".join(summary_bits) + "."
    if top_projects:
        summary += f" Recent work spans {_join(top_projects)}"
        summary += f", with hands-on {_join(skills[:3])}." if skills else "."
    return CV(name=profile.name or "Your name", title=profile.job_title or "", summary=summary,
              experience=[(p, colors[p], b) for p, b in grouped.items()], skills=skills,
              generated_at=datetime.fromisoformat(generated) if generated else None)


def edit_bullet(store: MemoryStore, bullet_id: str, text: str) -> None:
    row = store.get(CVBulletRow, bullet_id)
    if row is None:
        raise KeyError(bullet_id)
    row.text, row.edited, row.state = text.strip(), True, TruthState.CONFIRMED.value
    store.save(row)


# --- exports -------------------------------------------------------------------
def to_dict(cv: CV) -> dict:
    return {
        "name": cv.name, "title": cv.title, "summary": cv.summary,
        "experience": [{"project": p, "color": c, "bullets": [
            {"id": b.id, "text": b.text, "confidence": b.confidence, "state": b.state, "evidence": b.evidence, "weak": b.weak}
            for b in bullets]} for p, c, bullets in cv.experience],
        "skills": cv.skills,
        "generated_at": cv.generated_at.isoformat() if cv.generated_at else None,
    }


def to_markdown(cv: CV) -> str:
    lines = [f"# {cv.name}", "", f"**{cv.title}**" if cv.title else "", "", cv.summary, "", "## Experience", ""]
    for project, _, bullets in cv.experience:
        lines += [f"### {project}", ""] + [f"- {b.text}" for b in bullets] + [""]
    if cv.skills:
        lines += ["## Skills", "", " · ".join(cv.skills), ""]
    return "\n".join(line for line in lines if line is not None).replace("\n\n\n", "\n\n")


def to_json(cv: CV) -> str:
    return json.dumps(to_dict(cv), ensure_ascii=False, indent=2)


def to_docx(cv: CV, path: Path) -> Path:
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name, style.font.size = "Calibri", Pt(10.5)
    doc.add_heading(cv.name, level=0)
    if cv.title:
        doc.add_paragraph(cv.title).runs[0].bold = True
    doc.add_paragraph(cv.summary)
    doc.add_heading("Experience", level=1)
    for project, _, bullets in cv.experience:
        doc.add_heading(project, level=2)
        for b in bullets:
            doc.add_paragraph(b.text, style="List Bullet")
    if cv.skills:
        doc.add_heading("Skills", level=1)
        doc.add_paragraph(" · ".join(cv.skills))
    doc.save(path)
    return path


_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf", "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf", "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf",
]


def _pdf_font(pdf) -> str:
    for candidate in _FONT_CANDIDATES:
        p = Path(candidate)
        if p.exists():
            pdf.add_font("CV", "", str(p))
            bold = p.with_name(p.stem + "-Bold" + p.suffix)
            pdf.add_font("CV", "B", str(bold if bold.exists() else p))
            return "CV"
    return "helvetica"  # Latin-1 only; non-Latin characters are replaced


def to_pdf(cv: CV, path: Path) -> Path:
    from fpdf import FPDF

    pdf = FPDF(format="A4")
    pdf.set_margins(18, 18, 18)
    pdf.add_page()
    font = _pdf_font(pdf)

    def text(value: str) -> str:
        return value if font != "helvetica" else value.encode("latin-1", "replace").decode("latin-1")

    pdf.set_font(font, "B", 22)
    pdf.cell(0, 11, text(cv.name), new_x="LMARGIN", new_y="NEXT")
    if cv.title:
        pdf.set_font(font, "", 12)
        pdf.set_text_color(90, 90, 100)
        pdf.cell(0, 7, text(cv.title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(20, 20, 30)
    pdf.ln(3)
    pdf.set_font(font, "", 10.5)
    pdf.multi_cell(0, 5.5, text(cv.summary), new_x="LMARGIN", new_y="NEXT")

    def heading(label: str) -> None:
        pdf.ln(4)
        pdf.set_font(font, "B", 10)
        pdf.set_text_color(110, 110, 120)
        pdf.cell(0, 6, label.upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(220, 220, 228)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(2)
        pdf.set_text_color(20, 20, 30)

    heading("Experience")
    for project, _, bullets in cv.experience:
        pdf.set_font(font, "B", 11.5)
        pdf.cell(0, 7, text(project), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(font, "", 10.5)
        for b in bullets:
            pdf.set_x(pdf.l_margin + 3)
            pdf.multi_cell(0, 5.5, text("•  " + b.text if font != "helvetica" else "-  " + b.text), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1.5)
    if cv.skills:
        heading("Skills")
        pdf.set_font(font, "", 10.5)
        pdf.multi_cell(0, 5.5, text(" · ".join(cv.skills) if font != "helvetica" else ", ".join(cv.skills)))
    pdf.output(str(path))
    return path


__all__ = ["CV", "Bullet", "edit_bullet", "generate", "load", "to_dict", "to_docx", "to_json", "to_markdown", "to_pdf"]
