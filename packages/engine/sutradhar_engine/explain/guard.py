"""The language guard (invariant I17): explanations describe what the data shows, never who someone is or what they
intend, and summaries are hedged. Used by the renderer at run time and by the test suite over every template."""

from __future__ import annotations

import re

# Phrases that state guilt, identity or intent. Matching any of them is a violation.
FORBIDDEN = [
    r"\b(is|are|was|were)\s+(a\s+|an\s+|the\s+)?(criminal|criminals|ransomware|launderer|money launderer|thief|scammer|fraudster|guilty|offender|perpetrator|terrorist)\b",
    r"\b(definitely|certainly|undoubtedly|proves?|proven|confirmed to be|clearly (is|are)|no doubt)\b",
    r"\b(owned by|belongs to)\s+(a\s+)?(criminal|gang|group)\b",
    r"\bidentity\b",
]
HEDGES = (
    "may",
    "might",
    "suggests",
    "likely",
    "appears",
    "consistent with",
    "can indicate",
    "can be",
    "lead for review",
    "could",
)
_COMPILED = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN]


def violations(text: str) -> list[str]:
    return [p.pattern for p in _COMPILED if p.search(text)]


def is_hedged(text: str) -> bool:
    lower = text.lower()
    return any(h in lower for h in HEDGES)


def check_reason(text: str) -> None:
    bad = violations(text)
    if bad:
        raise ValueError(f"explanation breaks the language guard: {text!r}")


def check_summary(text: str) -> None:
    check_reason(text)
    if not is_hedged(text):
        raise ValueError(f"summary is not hedged: {text!r}")
