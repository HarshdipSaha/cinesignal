"""google-adk / Vertex AI Gemini configuration. Import this before touching
any google-genai or google-adk client so the right env vars are set."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")

# Resolve a relative GOOGLE_APPLICATION_CREDENTIALS (as set in .env) against
# the repo root, so auth doesn't depend on the process's CWD (uvicorn,
# pytest, and a plain `python scripts/x.py` all differ here).
_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if _creds and not os.path.isabs(_creds):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str((ROOT / _creds).resolve())

# Per the spec ("pin whatever's current at build time"). NOTE: "-latest"
# aliases (gemini-flash-latest / gemini-pro-latest) 404 against this
# project's Vertex AI Model Garden (verified live, 2026-09-03) even though
# they're documented for the Gemini Developer API — Vertex resolves publisher
# model IDs directly, no alias layer. `client.models.list()` also listed
# several newer models (gemini-3.x-flash, gemini-3.x-pro-preview) that
# themselves 404'd on generate_content for this project/region — listed in
# the catalog isn't the same as actually invokable. gemini-2.5-flash and
# gemini-2.5-pro are the newest models VERIFIED LIVE to actually work here
# (one real generate_content call each, 2026-09-03) — don't bump these
# without a live invocation test, not just a models.list() sighting.
FLASH_MODEL = os.environ.get("CINESIGNAL_FLASH_MODEL", "gemini-2.5-flash")
PRO_MODEL = os.environ.get("CINESIGNAL_PRO_MODEL", "gemini-2.5-pro")

APP_NAME = "cinesignal"
