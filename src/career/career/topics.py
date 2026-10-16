"""Topic words from file names: 'temperature_test.py', 'Temperature_Result.xlsx' → ['temperature']."""

import re
from collections import Counter
from collections.abc import Iterable

GENERIC_STEMS = {"main", "utils", "util", "index", "app", "config", "setup", "init", "test", "tests", "parse", "run",
                 "script", "helpers", "common", "core", "readme", "notes", "result", "results", "data", "conftest",
                 "summary", "report", "final", "new", "copy", "draft"}


def stems(name: str) -> list[str]:
    stem = name.rsplit(".", 1)[0]
    stem = re.sub(r"([a-z])([A-Z])", r"\1 \2", stem)
    return [w.lower() for w in re.split(r"[_\-\s.]+", stem)
            if w and not w.isdigit() and len(w) > 2 and w.lower() not in GENERIC_STEMS]


def topics_from_names(names: Iterable[str], limit: int = 2) -> list[str]:
    words: Counter[str] = Counter()
    for name in names:
        for w in stems(name):
            words[w] += 1
    return [w for w, _ in words.most_common(limit)]


def file_topics(rows, limit: int = 2) -> list[str]:
    """From analysis rows' file evidence."""
    return topics_from_names((e["value"] for a in rows for e in (a.evidence or []) if e["type"] == "file"), limit)
