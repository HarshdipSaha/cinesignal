"""Loads playbooks/*.yaml — the versioned SQL template catalog."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PLAYBOOKS_DIR = ROOT / "playbooks"


@dataclass
class StepTemplate:
    id: str
    title: str
    sql: str
    param_types: dict[str, str]


@dataclass
class Playbook:
    id: str
    version: int
    name: str
    description: str
    steps: dict[str, StepTemplate]  # keyed by step id, for O(1) lookup by runner modules


def load_playbook(playbook_id: str) -> Playbook:
    path = PLAYBOOKS_DIR / f"{playbook_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no playbook template file: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    steps = {
        s["id"]: StepTemplate(
            id=s["id"], title=s["title"], sql=s["sql"].strip(), param_types=s.get("param_types", {})
        )
        for s in raw["steps"]
    }
    return Playbook(
        id=raw["id"],
        version=int(raw["version"]),
        name=raw["name"],
        description=raw.get("description", ""),
        steps=steps,
    )


_CACHE: dict[str, Playbook] = {}


def get_playbook(playbook_id: str) -> Playbook:
    if playbook_id not in _CACHE:
        _CACHE[playbook_id] = load_playbook(playbook_id)
    return _CACHE[playbook_id]
