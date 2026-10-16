"""Confidence bands (roadmap §20). Confidence is not truth: evidence is still required."""

BANDS = [(0.95, "Very strong"), (0.80, "Strong"), (0.60, "Possible"), (0.40, "Weak"), (0.0, "Unknown")]
WORDS = [(0.95, "Very likely"), (0.80, "Likely"), (0.60, "Possibly"), (0.0, "Unsure")]


def band(confidence: float) -> str:
    return next(name for threshold, name in BANDS if confidence >= threshold)


def word(confidence: float) -> str:
    return next(name for threshold, name in WORDS if confidence >= threshold)
