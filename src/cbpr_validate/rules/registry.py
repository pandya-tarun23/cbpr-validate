from __future__ import annotations

from collections.abc import Callable

from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.model.validation_result import ValidationResult
from cbpr_validate.profiles import DEFAULT_PROFILE, Profile, apply_profile, resolve_profile

Rule = Callable[..., list[Finding]]

_RULES: list[Rule] = []


def register(rule: Rule) -> Rule:
    """Decorator to register a rule function.

    The rule should accept a domain model (e.g., `Payment`) and return a list of Findings.
    """

    _RULES.append(rule)
    return rule


def run_all(
    *args: object,
    profile: str | Profile | None = DEFAULT_PROFILE,
    **kwargs: object,
) -> ValidationResult:
    """Run every registered rule, then apply the severity profile.

    ``profile`` is keyword-only and is consumed here - it is never forwarded
    to the rule functions, which stay unaware of profiles and keep emitting
    their own declared severities.

    This is the one and only place a profile override is applied. Every front
    door (the library via ``core``, the CLI's ``check``, the API's
    ``/validate``) reaches the rules through this function, so they cannot
    disagree about what a profile means. The override lands after the last
    rule has run and before anything reads ``is_compliant``, which is what
    makes a profile able to change the verdict without touching a rule.

    Raises:
        ValueError: if ``profile`` is not a known profile name.
    """
    resolved = resolve_profile(profile)
    findings: list[Finding] = []
    for r in _RULES:
        try:
            produced = r(*args, **kwargs)
            if produced:
                findings.extend(produced)
        except Exception as exc:  # pragma: no cover - defensive
            # convert unexpected errors into an ERROR finding
            findings.append(
                Finding(
                    rule_id="REG-EXC",
                    severity=Severity.ERROR,
                    message=f"Rule {r.__name__} failed: {exc}",
                    location=None,
                )
            )
    return ValidationResult(
        findings=apply_profile(findings, resolved), profile=resolved
    )


def list_rules() -> list[str]:
    return [r.__name__ for r in _RULES]


# Ensure common rule modules are imported so they register on package import.
try:  # pragma: no cover - defensive import
    from cbpr_validate.rules import (  # noqa: F401
        address,
        agents,
        amounts,
        codes,
        returns,
        structural,
    )
except Exception:
    pass
