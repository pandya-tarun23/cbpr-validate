from __future__ import annotations

import json
from pathlib import Path

SNAPSHOT_VERSION = "iso20022-codesets-2026-06"
_DATA_PATH = Path(__file__).resolve().parent / "data" / "iso20022_codesets.json"


def _load_snapshot() -> dict[str, set[str]]:
    if not _DATA_PATH.exists():
        return {}
    with _DATA_PATH.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return {name: set(values) for name, values in raw.items()}


_CODES = _load_snapshot()


def get_snapshot_version() -> str:
    return SNAPSHOT_VERSION


def is_valid(set_name: str, code: str) -> bool:
    values = _CODES.get(set_name, set())
    return code in values


def get_codes(set_name: str) -> set[str]:
    return set(_CODES.get(set_name, set()))
