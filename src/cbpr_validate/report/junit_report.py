"""JUnit-XML output, so this validator can run as a gate in *other* pipelines.

Only ``ERROR`` findings become ``<failure>`` elements. WARN and INFO are emitted
as passing test cases carrying ``<system-out>``: a build should fail exactly when
the message is non-compliant, which is the same condition as
``ValidationResult.is_compliant`` / ``MatchResult.is_consistent``. A WARN that
broke someone's pipeline would make the warning severity useless.

Built with :mod:`xml.etree.ElementTree` so every value is escaped correctly -
findings quote message content, which routinely contains ``&`` and ``<``.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

from cbpr_validate.match.result import MatchResult
from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.model.validation_result import ValidationResult


def _classname(rule_id: str) -> str:
    """'CBPR-ADDR-002' -> 'CBPR-ADDR', so a CI report groups by rule family."""
    group = rule_id.rsplit("-", 1)[0]
    return group or rule_id


def _add_case(suite: ET.Element, finding: Finding) -> None:
    name = finding.rule_id
    if finding.location:
        name += f": {finding.location}"
    case = ET.SubElement(
        suite, "testcase", {"classname": _classname(finding.rule_id), "name": name}
    )
    detail = "\n".join(
        part
        for part in (
            finding.message,
            f"party: {finding.party}" if finding.party else None,
            f"fix: {finding.remediation}" if finding.remediation else None,
            f"spec: {finding.spec_reference}" if finding.spec_reference else None,
        )
        if part
    )
    if finding.severity is Severity.ERROR:
        failure = ET.SubElement(
            case, "failure", {"type": finding.severity.value, "message": finding.message}
        )
        failure.text = detail
    else:
        ET.SubElement(case, "system-out").text = f"{finding.severity.value}: {detail}"


def _build_suite(name: str, findings: list[Finding], passed_message: str) -> ET.Element:
    failures = sum(1 for f in findings if f.severity is Severity.ERROR)
    suites = ET.Element("testsuites")
    suite = ET.SubElement(
        suites,
        "testsuite",
        {
            "name": name,
            "tests": str(len(findings) or 1),
            "failures": str(failures),
            "errors": "0",
            "skipped": "0",
        },
    )
    if not findings:
        ET.SubElement(suite, "testcase", {"classname": name, "name": passed_message})
    else:
        for finding in findings:
            _add_case(suite, finding)
    return suites


def _serialise(suites: ET.Element) -> str:
    ET.indent(suites, space="  ")
    body = ET.tostring(suites, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{body}'


def validation_to_junit(result: ValidationResult, source: str | None = None) -> str:
    name = f"cbpr-validate.{source}" if source else "cbpr-validate"
    return _serialise(_build_suite(name, result.findings, "no findings"))


def match_to_junit(result: MatchResult) -> str:
    name = f"cbpr-validate.correlate.{result.scenario.value}"
    return _serialise(_build_suite(name, result.mismatches, "messages correlate cleanly"))
