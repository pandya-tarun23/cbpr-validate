from __future__ import annotations

from typing import Callable, List

from cbpr_validate.model.finding import Finding
from cbpr_validate.model.validation_result import ValidationResult

Rule = Callable[..., List[Finding]]

_RULES: List[Rule] = []


def register(rule: Rule) -> Rule:
    """Decorator to register a rule function.

    The rule should accept a domain model (e.g., `Payment`) and return a list of Findings.
    """

    _RULES.append(rule)
    return rule


def run_all(*args, **kwargs) -> ValidationResult:
    result = ValidationResult(findings=[])
    for r in _RULES:
        try:
            findings = r(*args, **kwargs)
            if findings:
                result.findings.extend(findings)
        except Exception as exc:  # pragma: no cover - defensive
            # convert unexpected errors into an ERROR finding
            result.findings.append(
                Finding(
                    rule_id="REG-EXC",
                    severity="ERROR",
                    message=f"Rule {r.__name__} failed: {exc}",
                    location=None,
                )
            )
    return result


def list_rules() -> List[str]:
    return [r.__name__ for r in _RULES]


# Ensure common rule modules are imported so they register on package import.
try:  # pragma: no cover - defensive import
    from cbpr_validate.rules import address  # noqa: F401
except Exception:
    pass
