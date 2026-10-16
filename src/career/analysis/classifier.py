"""Activity understanding (roadmap §19, §39).

Every session first gets a deterministic rule-based analysis: it works offline, costs
nothing and is often enough. An AI provider is asked only when the rules are unsure
(or for deep analysis), and its answer is validated before it is trusted:

  * strict schema (Pydantic); invalid → one retry → discarded
  * evidence must be things that are actually in the context packet
  * confidence is capped, and impact numbers are never accepted
"""

import logging
import re

from pydantic import BaseModel, Field, field_validator

from career.analysis.context import ContextPacket

log = logging.getLogger(__name__)

CATEGORIES = ["Development", "Testing", "Investigation", "Analysis", "Documentation", "Communication",
              "Operations", "Design", "Learning", "Planning", "Other"]


class ActivityAnalysis(BaseModel):
    """The strict JSON shape every analyzer must return."""

    activity: str = Field(min_length=3, max_length=90, description="Short name of the work, e.g. 'Supervisor temperature testing'")
    project: str | None = Field(default=None, max_length=80)
    category: str = Field(description="One of: " + ", ".join(CATEGORIES))
    confidence: float = Field(ge=0, le=1)
    skills: list[str] = Field(default_factory=list, max_length=8)
    evidence: list[str] = Field(default_factory=list, max_length=12, description="Items copied exactly from the context")

    @field_validator("category")
    @classmethod
    def _known_category(cls, v: str) -> str:
        match = next((c for c in CATEGORIES if c.lower() == v.strip().lower()), None)
        return match or "Other"

    @field_validator("skills")
    @classmethod
    def _clean_skills(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for s in v:
            s = s.strip()
            if 1 < len(s) <= 40 and len(s.split()) <= 4 and s.lower() not in {x.lower() for x in out}:
                out.append(s)
        return out


# --- rules ---------------------------------------------------------------------
_LANG_BY_EXT = {
    "py": "Python", "ipynb": "Python", "js": "JavaScript", "jsx": "JavaScript", "ts": "TypeScript", "tsx": "TypeScript",
    "vue": "Vue", "java": "Java", "kt": "Kotlin", "go": "Go", "rs": "Rust", "c": "C", "h": "C", "cpp": "C++",
    "cc": "C++", "hpp": "C++", "cs": "C#", "rb": "Ruby", "php": "PHP", "swift": "Swift", "sh": "Shell scripting",
    "ps1": "PowerShell", "sql": "SQL", "html": "HTML", "css": "CSS", "scss": "CSS", "yaml": "YAML", "yml": "YAML",
}
_TOOL_BY_EXT = {"xlsx": "Excel", "xls": "Excel", "docx": "Technical writing",
                "md": "Technical writing", "tm": "Log analysis", "log": "Log analysis", "pptx": "Presentations"}
_SKILL_BY_COMMAND = {
    "pytest": ["pytest", "Test automation"], "git": ["Git"], "docker": ["Docker"], "kubectl": ["Kubernetes"],
    "ssh": ["SSH", "Linux"], "scp": ["SSH", "Linux"], "systemctl": ["Linux"], "journalctl": ["Linux"],
    "npm": ["Node.js"], "cargo": ["Rust"], "go": ["Go"], "terraform": ["Terraform"], "ansible": ["Ansible"],
    "make": ["Build systems"], "cmake": ["Build systems"], "gcc": ["C"], "psql": ["SQL"], "mysql": ["SQL"],
    "adb": ["Android"], "minicom": ["Embedded systems"], "gstreamer": ["GStreamer"], "ffmpeg": ["Video processing"],
}
_SKILL_BY_SITE = {"Jira": "Jira", "Confluence": "Confluence", "GitHub": "GitHub", "GitLab": "GitLab", "Grafana": "Grafana",
                  "Figma": "Figma", "Kibana": "Kibana", "AWS": "AWS", "Azure DevOps": "Azure DevOps"}
_COMMS = {"Slack", "Teams", "Outlook", "Gmail", "Thunderbird", "Zoom", "Mail"}
_EDITORS = {"VS Code", "Cursor", "PyCharm", "IntelliJ IDEA", "WebStorm", "CLion", "GoLand", "Rider", "Xcode", "Android Studio", "vim"}
_DOCS_APPS = {"Word", "Excel", "PowerPoint", "Google Docs", "Google Sheets", "LibreOffice", "Notion", "Obsidian"}
_TEST_FILE_RE = re.compile(r"(^test_|_test\.|\.test\.|\.spec\.|tests?/)", re.IGNORECASE)
_NOUN = {"Development": "development", "Testing": "testing", "Investigation": "investigation", "Analysis": "analysis",
         "Documentation": "documentation", "Communication": "communication", "Operations": "operations",
         "Design": "design", "Learning": "research", "Planning": "planning", "Other": "work"}


def _share(ctx: ContextPacket, apps: set[str]) -> float:
    total = sum(ctx.applications.values()) or 1
    return sum(m for a, m in ctx.applications.items() if a in apps) / total


def classify_rules(ctx: ContextPacket, project: str | None = None) -> ActivityAnalysis:
    exts = {f.rsplit(".", 1)[-1].lower() for f in ctx.files if "." in f} | set(ctx.file_actions)
    test_files = [f for f in ctx.files if _TEST_FILE_RE.search(f)]
    commits = [c for g in ctx.git for c in g.commits]
    comms, editors, docs = _share(ctx, _COMMS), _share(ctx, _EDITORS), _share(ctx, _DOCS_APPS)
    log_work = bool(exts & {"log", "tm"}) or any("log" in f.lower() for f in ctx.files)

    if comms >= 0.6:
        category = "Communication"
    elif "pytest" in ctx.commands or test_files:
        category = "Testing"
    elif log_work and editors < 0.6:
        category = "Analysis"
    elif editors >= 0.35 or commits:
        category = "Development"
    elif {"ssh", "systemctl", "docker", "kubectl", "ansible", "terraform", "scp"} & set(ctx.commands):
        category = "Operations"
    elif ctx.tickets or {"Jira", "Confluence", "Stack Overflow", "GitHub"} & set(ctx.sites):
        category = "Investigation"
    elif docs >= 0.4:
        category = "Documentation"
    elif log_work:
        category = "Analysis"
    else:
        category = "Other"

    skills: list[str] = []
    for ext in sorted(exts):
        for table in (_LANG_BY_EXT, _TOOL_BY_EXT):
            if ext in table and table[ext] not in skills:
                skills.append(table[ext])
    for cmd in ctx.commands:
        skills += [s for s in _SKILL_BY_COMMAND.get(cmd, []) if s not in skills]
    for site in ctx.sites:
        if site in _SKILL_BY_SITE and _SKILL_BY_SITE[site] not in skills:
            skills.append(_SKILL_BY_SITE[site])
    if commits and "Git" not in skills:
        skills.append("Git")
    if category == "Testing" and "Test analysis" not in skills and {"xlsx", "csv"} & exts:
        skills.append("Test analysis")
    if category == "Investigation" and "Debugging" not in skills and ctx.tickets:
        skills.append("Debugging")
    if "Excel" in ctx.applications and "Excel" not in skills:
        skills.append("Excel")

    subject = project or (ctx.workspaces[0] if ctx.workspaces else None) or (ctx.tickets[0] if ctx.tickets else None)
    if category == "Communication":
        activity = "Team communication"
    elif subject:
        activity = f"{subject} {_NOUN[category]}"
    else:
        top_app = next(iter(ctx.applications), "Computer")
        activity = f"{_NOUN[category].capitalize()} in {top_app}"

    evidence = [*ctx.tickets, *ctx.files[:6], *ctx.commands, *[c.hash for c in commits[:3]], *ctx.sites[:2]]
    kinds = sum(bool(x) for x in (ctx.tickets, ctx.files, ctx.commands, commits, ctx.sites, ctx.workspaces))
    confidence = min(0.9, 0.45 + 0.07 * kinds + (0.1 if project else 0) + (0.05 if ctx.active_minutes >= 20 else 0))
    if category == "Other":
        confidence = min(confidence, 0.5)

    return ActivityAnalysis(
        activity=activity[:90].strip().capitalize() if activity[:1].islower() else activity[:90],
        project=project,
        category=category,
        confidence=round(confidence, 2),
        skills=skills[:8],
        evidence=list(dict.fromkeys(e for e in evidence if e))[:12],
    )


_NUMBER_CLAIM_RE = re.compile(r"\d+\s*(%|percent|x\b|times)", re.IGNORECASE)


def validate_ai(result: ActivityAnalysis, ctx: ContextPacket, known_project: str | None) -> ActivityAnalysis:
    """Keep only what the context can back up."""
    vocab = {v.lower(): v for v in ctx.evidence_vocabulary()}
    evidence = [vocab[e.lower()] for e in result.evidence if e.lower() in vocab]
    activity = result.activity
    if _NUMBER_CLAIM_RE.search(activity):
        activity = _NUMBER_CLAIM_RE.sub("", activity).strip()
    project = known_project or result.project
    confidence = min(result.confidence, 0.97)
    if not evidence:
        confidence = min(confidence, 0.5)  # a claim with no evidence is at best weak
    return result.model_copy(update={"activity": activity or result.activity, "evidence": evidence,
                                     "project": project, "confidence": round(confidence, 2)})
