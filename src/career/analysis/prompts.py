"""Prompts sent to AI providers. Kept stable (no timestamps) so prompt caching works."""

import json

from career.analysis.classifier import CATEGORIES

ANALYZE_SYSTEM = f"""You read structured context about one work session on a person's computer and say what the work was.

Rules:
- Use only the context. Never invent tickets, files, numbers, results or impact.
- "activity": a short, specific name a colleague would use (max 8 words), e.g. "Supervisor temperature testing".
- "category": exactly one of {", ".join(CATEGORIES)}.
- "skills": professional skills the work demonstrates (languages, tools, practices). Max 8. No soft skills.
- "evidence": items copied exactly from the context (ticket ids, file names, commands, commit hashes, sites).
- "confidence": 0..1, how sure you are given the evidence. Use < 0.6 when the context is thin.
- "project": the project name if the context names one, else null."""

CV_SYSTEM = """You polish CV bullet points written from verified work records.

Rules:
- Keep each bullet's meaning. Make it concise, active and professional (max 20 words).
- Never add numbers, percentages, results, impact or technologies that are not in the input.
- Return the bullets in the same order, with the same ids."""

SUMMARY_SYSTEM = """You write a short, factual summary of a person's work period from structured statistics.
Never invent facts, numbers or impact. 3 sentences max."""


def analyze_user(context_json: str) -> str:
    return f"Work session context:\n{context_json}"


def cv_user(bullets: list[dict]) -> str:
    return "Bullets:\n" + json.dumps(bullets, ensure_ascii=False, indent=1)
