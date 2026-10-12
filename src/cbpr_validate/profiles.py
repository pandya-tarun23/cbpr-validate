"""Severity profiles: which rulebook a message is judged against.

SWIFT deferred every payments change in Standards Release 2026, including the
removal of fully unstructured postal addresses in CBPR+ (originally 14 Nov
2026). A new date is not yet confirmed. So two honest answers exist for the
same message, and which one you want depends on the question you are asking:

* ``current`` - what the network accepts **today**. An unstructured-only
  address is a readiness gap, not a rejection, so it is reported as WARN and
  the message can still be compliant.
* ``sr2026``  - the strict future behaviour. The same address is an ERROR and
  the message is not compliant.

A profile is **data, not logic**. Rules keep emitting their own declared
severity; a profile is a flat ``rule_id -> severity`` mapping applied once,
after every rule has run, by ``cbpr_validate.rules.registry.run_all``. No
rule's detection logic is profile-aware, and nothing here looks at message
content.

This module deliberately does not import ``ValidationResult``:
``apply_profile`` works on a list of findings so that
``model.validation_result`` can import ``Profile`` from here without a cycle.
"""

from __future__ import annotations

from enum import StrEnum

from cbpr_validate.model.finding import Finding, Severity


class Profile(StrEnum):
    """The rulebook a message is judged against."""

    CURRENT = "current"
    SR2026 = "sr2026"


#: What a caller gets when they ask for nothing. ``current`` is the default
#: because it describes the network as it actually behaves today; opting into
#: ``sr2026`` is opting into a future that has no confirmed date.
DEFAULT_PROFILE = Profile.CURRENT

#: ``rule_id -> severity`` per profile. ``sr2026`` repeats the severities the
#: address rules already declare. That is intentional: it costs two lines and
#: makes the profile readable as a rulebook in its own right, rather than
#: something that silently inherits whatever a rule happens to say today.
PROFILE_OVERRIDES: dict[Profile, dict[str, Severity]] = {
    Profile.CURRENT: {
        "CBPR-ADDR-001": Severity.WARN,
        "CBPR-ADDR-002": Severity.WARN,
    },
    Profile.SR2026: {
        "CBPR-ADDR-001": Severity.ERROR,
        "CBPR-ADDR-002": Severity.ERROR,
    },
}

VALID_PROFILES = tuple(p.value for p in Profile)


def resolve_profile(value: str | Profile | None) -> Profile:
    """Turn a caller's profile argument into a ``Profile``.

    Accepts the enum, the matching string (case-insensitively), or ``None``
    for the default. Anything else raises ``ValueError`` naming the valid
    profiles - the library's way of signalling an input error, which the CLI
    turns into exit 2 and the API into a 4xx.
    """
    if value is None:
        return DEFAULT_PROFILE
    if isinstance(value, Profile):
        return value
    try:
        return Profile(str(value).strip().lower())
    except ValueError as exc:
        valid = ", ".join(VALID_PROFILES)
        raise ValueError(
            f"unknown profile {value!r}. Valid profiles: {valid}"
        ) from exc


def apply_profile(findings: list[Finding], profile: Profile) -> list[Finding]:
    """Return ``findings`` with this profile's severity overrides applied.

    Findings the profile does not mention are returned untouched. An
    overridden finding keeps its original severity in ``base_severity``, so a
    report can still say "WARN under current, ERROR under sr2026".
    """
    overrides = PROFILE_OVERRIDES.get(profile, {})
    if not overrides:
        return findings

    adjusted: list[Finding] = []
    for finding in findings:
        target = overrides.get(finding.rule_id)
        # Compare against base_severity, not severity, so re-applying a
        # profile is idempotent and never records an override that is really
        # just the rule's own severity.
        if target is None or target is finding.base_severity:
            adjusted.append(finding)
        else:
            adjusted.append(finding.model_copy(update={"severity": target}))
    return adjusted
