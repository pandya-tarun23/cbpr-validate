"""Phase 5 - the three output formatters."""

from __future__ import annotations

import json
from xml.etree import ElementTree as ET

from cbpr_validate.match.matcher import correlate
from cbpr_validate.match.result import MatchResult
from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.model.validation_result import ValidationResult
from cbpr_validate.parsers.parse import parse_message
from cbpr_validate.report.json_report import (
    match_to_dict,
    match_to_json,
    summarise,
    validation_to_dict,
    validation_to_json,
)
from cbpr_validate.report.junit_report import match_to_junit, validation_to_junit
from cbpr_validate.report.text_report import match_to_text, validation_to_text
from cbpr_validate.rules.registry import run_all
from tests.conftest import (
    PACS004,
    PACS004_WRONG_UETR,
    PACS008_CLEAN,
    PACS008_UNSTRUCTURED,
    UETR,
)


def _result(xml: bytes) -> ValidationResult:
    return run_all(parse_message(xml))


def _match(a: bytes, b: bytes) -> MatchResult:
    return correlate(parse_message(a), parse_message(b))


# --- JSON ------------------------------------------------------------------


def test_summarise_always_carries_every_severity() -> None:
    assert summarise([]) == {"ERROR": 0, "WARN": 0, "INFO": 0}


def test_validation_json_envelope() -> None:
    payload = json.loads(validation_to_json(_result(PACS008_UNSTRUCTURED)))
    assert payload["is_compliant"] is False
    assert payload["summary"]["ERROR"] >= 1
    assert sum(payload["summary"].values()) == len(payload["findings"])
    # severities serialise as plain strings, not enum reprs
    assert all(isinstance(f["severity"], str) for f in payload["findings"])


def test_validation_json_is_compliant_for_a_clean_message() -> None:
    payload = json.loads(validation_to_json(_result(PACS008_CLEAN)))
    assert payload["is_compliant"] is True
    assert payload["summary"]["ERROR"] == 0
    assert payload["summary"]["INFO"] >= 1  # ADDR-005 classifications


def test_match_json_envelope() -> None:
    payload = json.loads(match_to_json(_match(PACS004, PACS008_CLEAN)))
    assert payload["matched"] is True
    assert payload["is_consistent"] is True
    assert payload["scenario"] == "RETURN"
    assert payload["match_key"] == "UETR"
    assert payload["direction"] is None
    assert payload["message_a"]["message_type"] == "pacs.004"


def test_match_json_reports_a_broken_link() -> None:
    payload = json.loads(match_to_json(_match(PACS004_WRONG_UETR, PACS008_CLEAN)))
    assert payload["matched"] is False
    assert payload["is_consistent"] is False
    assert payload["summary"]["ERROR"] == 1


# --- text ------------------------------------------------------------------


def test_validation_text_reports_the_verdict_and_tally() -> None:
    text = validation_to_text(_result(PACS008_UNSTRUCTURED), source="msg.xml")
    assert "msg.xml" in text
    assert "NOT COMPLIANT" in text
    assert "CBPR-ADDR-001" in text
    assert "fix:" in text and "spec:" in text


def test_validation_text_orders_errors_before_info() -> None:
    text = validation_to_text(_result(PACS008_UNSTRUCTURED))
    assert text.index("ERROR") < text.index("INFO")


def test_validation_text_with_no_findings() -> None:
    text = validation_to_text(ValidationResult(findings=[]))
    assert "No findings." in text
    assert "0 errors, 0 warnings, 0 infos - COMPLIANT" in text


def test_validation_text_singular_tally() -> None:
    result = ValidationResult(
        findings=[Finding(rule_id="X-1", severity=Severity.ERROR, message="boom")]
    )
    assert "1 error, 0 warnings, 0 infos - NOT COMPLIANT" in validation_to_text(result)


def test_match_text_clean() -> None:
    text = match_to_text(_match(PACS004, PACS008_CLEAN))
    assert "RETURN correlation" in text
    assert "Linked on UETR" in text
    assert "CONSISTENT" in text


def test_validation_text_shows_the_party_on_a_finding() -> None:
    result = ValidationResult(
        findings=[
            Finding(
                rule_id="CBPR-ADDR-002",
                severity=Severity.ERROR,
                message="Town and country required",
                party="Cdtr",
            )
        ]
    )
    assert "[Cdtr]" in validation_to_text(result)


def test_match_text_unlinkable_pair() -> None:
    bare_status = b"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10">
  <FIToFIPmtStsRpt><TxInfAndSts><TxSts>ACSC</TxSts></TxInfAndSts></FIToFIPmtStsRpt>
</Document>
"""
    result = correlate(parse_message(bare_status), parse_message(PACS008_CLEAN), "outbound")
    text = match_to_text(result)
    assert "NOT LINKED - no shared identifier" in text
    assert "Direction: outbound (supplied by caller)" in text


def test_match_text_broken_link() -> None:
    text = match_to_text(_match(PACS004_WRONG_UETR, PACS008_CLEAN))
    assert "NOT LINKED - UETR does not match" in text
    assert "INCONSISTENT" in text


def test_match_text_flags_a_legacy_fallback() -> None:
    no_uetr = PACS004.replace(f"<OrgnlUETR>{UETR}</OrgnlUETR>".encode(), b"")
    text = match_to_text(_match(no_uetr, PACS008_CLEAN))
    assert "Linked on OrgnlTxId" in text
    assert "legacy fallback key" in text
    assert "Direction:" not in text  # a RETURN pair carries no direction


# --- JUnit -----------------------------------------------------------------


def test_junit_marks_only_errors_as_failures() -> None:
    xml = validation_to_junit(_result(PACS008_UNSTRUCTURED), source="msg.xml")
    root = ET.fromstring(xml)
    suite = root.find("testsuite")
    assert suite is not None
    failures = root.findall(".//failure")
    assert len(failures) >= 1
    assert len(failures) == int(suite.attrib["failures"])
    # INFO findings are present as passing cases carrying system-out
    assert root.findall(".//system-out")
    assert all(f.attrib["type"] == "ERROR" for f in failures)


def test_junit_groups_by_rule_family() -> None:
    root = ET.fromstring(validation_to_junit(_result(PACS008_UNSTRUCTURED)))
    classnames = {c.attrib["classname"] for c in root.findall(".//testcase")}
    assert "CBPR-ADDR" in classnames


def test_junit_clean_run_has_one_passing_case() -> None:
    root = ET.fromstring(validation_to_junit(ValidationResult(findings=[])))
    cases = root.findall(".//testcase")
    assert len(cases) == 1
    assert cases[0].attrib["name"] == "no findings"
    assert not root.findall(".//failure")


def test_junit_escapes_finding_text() -> None:
    result = ValidationResult(
        findings=[
            Finding(
                rule_id="X-1",
                severity=Severity.ERROR,
                message="a < b & c",
                location="Dbtr",
                party="Dbtr",
            )
        ]
    )
    xml = validation_to_junit(result)
    assert "a < b & c" not in xml  # must be escaped, never emitted raw
    failure = ET.fromstring(xml).find(".//failure")
    assert failure is not None
    assert failure.attrib["message"] == "a < b & c"  # and round-trips


def test_match_junit() -> None:
    root = ET.fromstring(match_to_junit(_match(PACS004_WRONG_UETR, PACS008_CLEAN)))
    suite = root.find("testsuite")
    assert suite is not None
    assert suite.attrib["name"] == "cbpr-validate.correlate.RETURN"
    assert len(root.findall(".//failure")) == 1


def test_match_junit_clean_pair_has_no_failures() -> None:
    root = ET.fromstring(match_to_junit(_match(PACS004, PACS008_CLEAN)))
    assert not root.findall(".//failure")
    assert root.findall(".//testcase")[0].attrib["name"] == "messages correlate cleanly"


# --- dict/JSON agreement ---------------------------------------------------


def test_json_helpers_agree_with_their_dicts() -> None:
    validation = _result(PACS008_CLEAN)
    assert json.loads(validation_to_json(validation)) == validation_to_dict(validation)
    match = _match(PACS004, PACS008_CLEAN)
    assert json.loads(match_to_json(match)) == match_to_dict(match)
