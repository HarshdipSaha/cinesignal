"""Small, dependency-free numeric helpers shared by the playbook implementations.
Everything here is plain arithmetic on already-fetched rows — deterministic,
no LLM involved."""
from __future__ import annotations

import statistics
from datetime import date, timedelta


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def series_to_map(rows: list[list], date_col: int = 0, value_col: int = 1) -> dict[date, float]:
    out: dict[date, float] = {}
    for r in rows:
        d = r[date_col]
        if isinstance(d, str):
            d = date.fromisoformat(d)
        out[d] = float(r[value_col])
    return out


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def stdev(values: list[float]) -> float:
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def percentile_rank(value: float, population: list[float]) -> float:
    """% of population <= value (inclusive), 0-100."""
    if not population:
        return 0.0
    below_or_eq = sum(1 for v in population if v <= value)
    return round(100.0 * below_or_eq / len(population), 1)


def zscores(values: list[float]) -> list[float]:
    m, s = mean(values), stdev(values)
    if s == 0:
        return [0.0 for _ in values]
    return [(v - m) / s for v in values]
