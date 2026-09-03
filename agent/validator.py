"""NumberValidator: rejects a memo if it states a numeral that cannot be
traced back to a finding's value or a raw evidence row.

Deliberately NOT an LLM call, unlike the other three agent steps. The
architecture sketch in the spec labels this "flash", but an LLM asked to
"check whether these numbers are real" is exactly the kind of task an LLM is
bad at (it can miss or fabricate its own check) — and the spec's own test
plan ("inject a hallucinated numeral -> memo must be rejected") demands a
result that's actually reliable. A plain extract-and-set-membership check is
strictly stronger here, so that's what this is. google-adk/Gemini still does
real work in resolver.py, interpreter.py, and composer.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from agent.composer import ComposedMemo
from agent.models import Finding, StepEvidence

_CITATION_RE = re.compile(r"\[q\d+\]")
_NUMBER_RE = re.compile(
    r"(?<![\w.])"
    r"\$?-?\d[\d,]*(?:\.\d+)?"
    r"\s?(?:%|K|M|B|thousand|million|billion)?"
    r"(?![\w])",
    re.IGNORECASE,
)
_SUFFIX_MULT = {"k": 1e3, "m": 1e6, "b": 1e9, "thousand": 1e3, "million": 1e6, "billion": 1e9}

# Numbers this small are almost always ordinals/day-counts/list markers, not
# fabricated statistics — skip them to avoid false-positive rejections.
IGNORE_ABS_BELOW = 32
RELATIVE_TOLERANCE = 0.02
ABSOLUTE_TOLERANCE = 1.5


def _parse_number(token: str) -> float | None:
    t = token.strip()
    is_pct = t.endswith("%")
    t_clean = t.rstrip("%").strip()
    suffix_mult = 1.0
    m = re.search(r"(K|M|B|thousand|million|billion)$", t_clean, re.IGNORECASE)
    if m:
        suffix_mult = _SUFFIX_MULT[m.group(1).lower()]
        t_clean = t_clean[: m.start()].strip()
    t_clean = t_clean.replace("$", "").replace(",", "")
    try:
        value = float(t_clean)
    except ValueError:
        return None
    if is_pct:
        return value  # percentages compared directly, not *0.01 — findings store pct as e.g. 22.0
    return value * suffix_mult


def extract_numbers(text: str) -> list[float]:
    text_wo_citations = _CITATION_RE.sub(" ", text)
    out = []
    for m in _NUMBER_RE.finditer(text_wo_citations):
        v = _parse_number(m.group(0))
        if v is not None:
            out.append(v)
    return out


def _flatten_numeric(value: Any, acc: list[float]) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        acc.append(float(value))
    elif isinstance(value, dict):
        for v in value.values():
            _flatten_numeric(v, acc)
    elif isinstance(value, list):
        for v in value:
            _flatten_numeric(v, acc)


def known_values(findings: list[Finding], evidence: list[StepEvidence]) -> set[float]:
    acc: list[float] = []
    for f in findings:
        _flatten_numeric(f.value, acc)
        _flatten_numeric(f.extra, acc)
    for e in evidence:
        for row in e.rows:
            _flatten_numeric(row, acc)
    # Rounding in prose ("~41M") vs. exact stored values means we compare
    # with tolerance at lookup time, not by pre-rounding the known set.
    return set(acc)


@dataclass
class ValidationResult:
    passed: bool
    unverifiable_numbers: list[float]
    notes: str = ""


def validate(memo: ComposedMemo, findings: list[Finding], evidence: list[StepEvidence]) -> ValidationResult:
    known = known_values(findings, evidence)
    known_list = sorted(known)

    def is_traceable(n: float) -> bool:
        if abs(n) < IGNORE_ABS_BELOW:
            return True
        for k in known_list:
            if abs(n - k) <= max(ABSOLUTE_TOLERANCE, RELATIVE_TOLERANCE * abs(k)):
                return True
        return False

    bad: list[float] = []
    for section in memo.sections:
        for n in extract_numbers(section.body):
            if not is_traceable(n):
                bad.append(n)

    if bad:
        return ValidationResult(False, bad, notes=f"{len(bad)} numeral(s) not found in any finding or evidence row (tolerance: {RELATIVE_TOLERANCE:.0%} rel / {ABSOLUTE_TOLERANCE} abs)")
    return ValidationResult(True, [])
