"""Chooses rules or AI per session (roadmap §39: AI only where it adds something)."""

import logging

from career.ai.base import AIError, AIProvider
from career.analysis.classifier import ActivityAnalysis, classify_rules, validate_ai
from career.analysis.context import ContextPacket

log = logging.getLogger(__name__)

AI_THRESHOLD = 0.8  # rules at or above this are trusted without asking an AI
AI_FAILED = "ai-unavailable"  # model marker: the AI was asked and couldn't help


def analyze(ctx: ContextPacket, project: str | None, provider: AIProvider | None, deep: bool = False
            ) -> tuple[ActivityAnalysis, str, str | None]:
    """Returns (analysis, analyzed_by, model). When the AI was tried and failed, the rules
    result comes back with model AI_FAILED so the caller doesn't keep re-asking."""
    rules = classify_rules(ctx, project)
    if provider is None or (not deep and rules.confidence >= AI_THRESHOLD):
        return rules, "rules", None
    if not provider.available():
        return rules, "rules", None
    for attempt in (1, 2):
        try:
            result = validate_ai(provider.analyze(ctx), ctx, project)
        except AIError as exc:
            log.warning("AI analysis failed (attempt %s): %s", attempt, exc)
            if "invalid output" not in str(exc):
                break  # network/auth/refusal: retrying now won't help
            continue
        # observed skills (from files and commands) always stay
        skills = list(dict.fromkeys([*result.skills, *rules.skills]))[:8]
        evidence = list(dict.fromkeys([*result.evidence, *rules.evidence]))[:12]
        return result.model_copy(update={"skills": skills, "evidence": evidence}), provider.name, provider.model
    return rules, "rules", AI_FAILED
