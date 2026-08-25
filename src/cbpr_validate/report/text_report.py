"""Human-readable output.

Plain text, no colour and no terminal detection, so the exact same string can be
asserted in a test, piped to a file, or printed by the CLI.
"""

from __future__ import annotations

from cbpr_validate.match.result import MatchKey, MatchResult
from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.model.validation_result import ValidationResult

_ORDER = {Severity.ERROR: 0, Severity.WARN: 1, Severity.INFO: 2}


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _tally(findings: list[Finding]) -> str:
    errors = sum(1 for f in findings if f.severity is Severity.ERROR)
    warnings = sum(1 for f in findings if f.severity is Severity.WARN)
    infos = sum(1 for f in findings if f.severity is Severity.INFO)
    return ", ".join(
        (_plural(errors, "error"), _plural(warnings, "warning"), _plural(infos, "info"))
    )


def _format_finding(finding: Finding) -> list[str]:
    head = f"  {finding.severity.value:<5}  {finding.rule_id}"
    if finding.party:
        head += f"  [{finding.party}]"
    lines = [head, f"         {finding.message}"]
    if finding.location:
        lines.append(f"         at {finding.location}")
    if finding.remediation:
        lines.append(f"         fix: {finding.remediation}")
    if finding.spec_reference:
        lines.append(f"         spec: {finding.spec_reference}")
    return lines


def _sorted(findings: list[Finding]) -> list[Finding]:
    """Most severe first; stable within a severity so rule order is preserved."""
    return sorted(findings, key=lambda f: _ORDER[f.severity])


def validation_to_text(result: ValidationResult, source: str | None = None) -> str:
    header = "cbpr-validate - usage-guideline validation"
    if source:
        header += f" - {source}"
    lines = [header, ""]
    if not result.findings:
        lines.append("  No findings.")
    else:
        for finding in _sorted(result.findings):
            lines.extend(_format_finding(finding))
            lines.append("")
        lines.pop()
    verdict = "COMPLIANT" if result.is_compliant else "NOT COMPLIANT"
    lines.extend(["", f"{_tally(result.findings)} - {verdict}"])
    return "\n".join(lines)


def match_to_text(result: MatchResult) -> str:
    a, b = result.message_a, result.message_b
    lines = [
        f"cbpr-validate - {result.scenario.value} correlation",
        "",
        f"  A: {a.message_type or 'unknown'}  UETR={a.uetr or '-'}",
        f"  B: {b.message_type or 'unknown'}  UETR={b.uetr or '-'}",
        "",
    ]
    if result.matched:
        linked_on = f"  Linked on {result.match_key.value}"
        if result.uetr:
            linked_on += f" = {result.uetr}"
        lines.append(linked_on)
        if result.fallback_used:
            lines.append(
                "  NOTE: matched on a legacy fallback key because a UETR was absent; "
                "treat this linkage with less confidence"
            )
        if result.linked_fields:
            lines.append(f"  Consistent fields: {', '.join(result.linked_fields)}")
    elif result.match_key is MatchKey.NONE:
        lines.append("  NOT LINKED - no shared identifier")
    else:
        lines.append(f"  NOT LINKED - {result.match_key.value} does not match")
    if result.direction:
        lines.append(f"  Direction: {result.direction.value} (supplied by caller)")
    lines.append("")

    if result.mismatches:
        for finding in _sorted(result.mismatches):
            lines.extend(_format_finding(finding))
            lines.append("")
        lines.pop()
        lines.append("")

    verdict = "CONSISTENT" if result.is_consistent else "INCONSISTENT"
    lines.append(f"{_tally(result.mismatches)} - {verdict}")
    return "\n".join(lines)
