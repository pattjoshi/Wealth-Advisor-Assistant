from __future__ import annotations

import re
from typing import Any

# Excludes digits embedded in an identifier like "client_002" or "T002-A2a" by
# requiring no letter/digit/underscore immediately before or after the match.
_NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9_])-?\$?\d[\d,]*\.?\d*%?(?![A-Za-z0-9_])")


def numeric_vocabulary(anomalies: list[dict[str, Any]], risk_score: float | None) -> set[float]:
    """Every number that is legitimately allowed to appear in the narrative: pulled
    primarily from each finding's already-formatted `explanation` text (what a
    faithful paraphrase would reference), plus raw evidence values and their
    percentage-scaled form, so "0.86" and "86%" are both recognized as the same fact."""
    vocab: set[float] = set()
    if risk_score is not None:
        vocab.add(round(float(risk_score), 2))
    vocab.add(float(len(anomalies)))

    for finding in anomalies:
        vocab.update(extract_numbers(finding.get("explanation", "")))
        for value in finding.get("evidence", {}).values():
            if isinstance(value, bool) or not isinstance(value, int | float):
                continue
            vocab.add(round(float(value), 2))
            vocab.add(round(float(value)))
            if 0 <= value <= 1:
                vocab.add(round(value * 100))
                vocab.add(round(value * 100, 1))

    return vocab


def extract_numbers(text: str) -> list[float]:
    numbers = []
    for match in _NUMBER_PATTERN.findall(text):
        cleaned = match.replace("$", "").replace(",", "").replace("%", "")
        if not cleaned or cleaned == "-":
            continue
        try:
            numbers.append(float(cleaned))
        except ValueError:
            continue
    return numbers


def is_grounded(text: str, vocabulary: set[float], *, tolerance: float = 0.5) -> bool:
    """True only if every number mentioned in `text` is close to one already in the
    findings. A single invented or wrong number fails the whole narrative — the caller
    then falls back to the deterministic template instead of risking a fabricated
    figure in a finance product."""
    for number in extract_numbers(text):
        if not any(abs(number - allowed) <= tolerance for allowed in vocabulary):
            return False
    return True
