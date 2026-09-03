"""Deterministic SQL templating for playbooks.

Design constraint (the spec's "determinism contract"): the LLM never writes
or edits SQL. Every query is a versioned template string in playbooks/*.yaml
with `{{name}}` placeholders. Only *parameter values* are chosen at runtime
(by the resolver LLM, the user, or playbook code) — and every value is
type-checked and literal-escaped here before it ever touches a query string.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")

_WIKIDATA_ID_RE = re.compile(r"^Q[0-9]+$")
_TCONST_RE = re.compile(r"^tt[0-9]+$")
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.\- ]+$")


class ParamError(ValueError):
    pass


def _esc_str(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def bind_wikidata_id(value: str) -> str:
    if not _WIKIDATA_ID_RE.match(value):
        raise ParamError(f"not a valid wikidata id: {value!r}")
    return f"'{value}'"


def bind_wikidata_id_list(values: list[str]) -> str:
    for v in values:
        if not _WIKIDATA_ID_RE.match(v):
            raise ParamError(f"not a valid wikidata id: {v!r}")
    return "[" + ",".join(f"'{v}'" for v in values) + "]"


def bind_date(value: str | date) -> str:
    if isinstance(value, date):
        d = value
    else:
        try:
            d = datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError as exc:
            raise ParamError(f"not a valid ISO date: {value!r}") from exc
    return f"'{d.isoformat()}'"


def bind_int(value: Any) -> str:
    return str(int(value))


def bind_float(value: Any) -> str:
    return repr(float(value))


def bind_project(value: str) -> str:
    if not re.match(r"^[a-z]{2,3}\.(wikipedia|m\.wikipedia)$", value):
        raise ParamError(f"not a recognized project code: {value!r}")
    return f"'{_esc_str(value)}'"


def bind_safe_token(value: str) -> str:
    if not _SAFE_TOKEN_RE.match(value):
        raise ParamError(f"unsafe token value: {value!r}")
    return f"'{_esc_str(value)}'"


def bind_genre_list(values: list[str]) -> str:
    for v in values:
        if not _SAFE_TOKEN_RE.match(v):
            raise ParamError(f"unsafe genre token: {v!r}")
    return "[" + ",".join(f"'{_esc_str(v)}'" for v in values) + "]"


def bind_search_text(value: str) -> str:
    """For genuinely free-text user input (the search box) — escapes rather
    than restricts to a safe alphabet, since titles legitimately contain
    punctuation, accents, etc. Length-capped as a defensive measure."""
    if len(value) > 200:
        raise ParamError("search text too long")
    return f"'{_esc_str(value)}'"


BINDERS = {
    "wikidata_id": bind_wikidata_id,
    "wikidata_id_list": bind_wikidata_id_list,
    "date": bind_date,
    "int": bind_int,
    "float": bind_float,
    "project": bind_project,
    "safe_token": bind_safe_token,
    "genre_list": bind_genre_list,
    "search_text": bind_search_text,
}


def render(sql_template: str, params: dict[str, Any], param_types: dict[str, str]) -> str:
    """Substitute every `{{name}}` in `sql_template` with a type-validated,
    literal-escaped SQL fragment. Raises ParamError if a placeholder has no
    declared type, no supplied value, or fails validation."""

    def _sub(match: re.Match) -> str:
        name = match.group(1)
        if name not in param_types:
            raise ParamError(f"placeholder {{{{{name}}}}} has no declared type in this step")
        if name not in params:
            raise ParamError(f"missing required param: {name}")
        binder = BINDERS.get(param_types[name])
        if binder is None:
            raise ParamError(f"unknown param type: {param_types[name]}")
        return binder(params[name])

    return _PLACEHOLDER_RE.sub(_sub, sql_template)
