from __future__ import annotations

import json
from pathlib import Path

# Revision marker rather than a new date: the ISO 20022 External Code Set
# vintage is unchanged: only the ISO 3166-1 alpha-2 list was completed, from a
# 10-country stub to the full 249 officially assigned codes. Dating it 2026-08
# would claim a code-set release that did not happen.
SNAPSHOT_VERSION = "iso20022-codesets-2026-06-r2"
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
