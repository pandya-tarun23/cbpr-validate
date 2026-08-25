"""JSON output.

Both envelopes are built here and nowhere else, so the CLI's ``--format json``
and the API's response bodies are the same bytes for the same input. The API
response models mirror these keys exactly.
"""

from __future__ import annotations

import json
from typing import Any

from cbpr_validate.match.result import MatchResult
from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.model.validation_result import ValidationResult


def summarise(findings: list[Finding]) -> dict[str, int]:
    """Count findings by severity. Always carries all three keys, so a consumer
    can read ``summary["ERROR"]`` without a membership check."""
    counts = dict.fromkeys((s.value for s in Severity), 0)
    for finding in findings:
        counts[finding.severity.value] += 1
    return counts


def validation_to_dict(result: ValidationResult) -> dict[str, Any]:
    return {
        "is_compliant": result.is_compliant,
        "summary": summarise(result.findings),
        "findings": [f.model_dump(mode="json") for f in result.findings],
    }


def match_to_dict(result: MatchResult) -> dict[str, Any]:
    return {
        "matched": result.matched,
        "is_consistent": result.is_consistent,
        "scenario": result.scenario.value,
        "match_key": result.match_key.value,
        "uetr": result.uetr,
        "direction": result.direction.value if result.direction else None,
        "fallback_used": result.fallback_used,
        "linked_fields": list(result.linked_fields),
        "message_a": result.message_a.model_dump(mode="json"),
        "message_b": result.message_b.model_dump(mode="json"),
        "summary": summarise(result.mismatches),
        "mismatches": [f.model_dump(mode="json") for f in result.mismatches],
    }


def validation_to_json(result: ValidationResult, indent: int | None = 2) -> str:
    return json.dumps(validation_to_dict(result), indent=indent)


def match_to_json(result: MatchResult, indent: int | None = 2) -> str:
    return json.dumps(match_to_dict(result), indent=indent)
