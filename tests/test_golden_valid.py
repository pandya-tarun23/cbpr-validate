"""Golden regression: a real, valid CBPR+ pacs.008 must validate clean.

The fixture is a live SWIFT CBPR+ message (`swift.cbprplus.03`): a business
envelope wrapping an AppHdr and a pacs.008.001.08, settling RON, with hybrid
postal addresses (AdrLine + TwnNm + Ctry) on both parties and a Romanian
creditor.

It once produced three ERROR findings, none of them real:

  * ``CBPR-STR-003`` - the mandatory-amount check tested the OPTIONAL InstdAmt
    instead of the mandatory IntrBkSttlmAmt.
  * ``CBPR-ADDR-004`` x2 - the ISO 3166-1 alpha-2 code set was a 10-country
    stub, so a Romanian address was "not a valid country".

This test is the backstop for both. If a future change makes a genuinely
compliant message non-compliant again, this fails first and says so.
"""

from __future__ import annotations

from pathlib import Path

from cbpr_validate import validate_bytes
from cbpr_validate.model.finding import Severity
from cbpr_validate.model.validation_result import ValidationResult

FIXTURE = Path(__file__).parent / "fixtures" / "pacs008_valid_hybrid_ro.xml"


def _result() -> ValidationResult:
    return validate_bytes(FIXTURE.read_bytes())


def test_golden_message_is_compliant() -> None:
    result = _result()
    assert result.is_compliant, [
        f"{f.rule_id}: {f.message}" for f in result.errors
    ]


def test_golden_message_has_zero_error_findings() -> None:
    assert _result().errors == []


def test_golden_message_has_zero_warnings() -> None:
    assert _result().warnings == []


def test_golden_message_exit_equivalent_is_zero() -> None:
    """`is_compliant` is exactly what the CLI turns into exit 0."""
    assert (0 if _result().is_compliant else 1) == 0


def test_golden_message_yields_exactly_the_two_hybrid_classifications() -> None:
    findings = _result().findings
    assert len(findings) == 2
    assert all(f.severity is Severity.INFO for f in findings)
    assert all(f.rule_id == "CBPR-ADDR-005" for f in findings)
    assert {f.location for f in findings} == {"Dbtr.PstlAdr", "Cdtr.PstlAdr"}
    assert all("hybrid" in f.message for f in findings)


def test_golden_message_does_not_trip_the_two_fixed_rules() -> None:
    """Named explicitly, so a regression points straight at the cause."""
    rule_ids = {f.rule_id for f in _result().findings}
    assert "CBPR-STR-003" not in rule_ids  # optional InstdAmt vs mandatory IntrBkSttlmAmt
    assert "CBPR-ADDR-004" not in rule_ids  # country code-set stub


def test_golden_fixture_still_has_the_shape_this_test_depends_on() -> None:
    """Guards the fixture: if it is edited into something that trivially
    passes, the assertions above stop proving anything."""
    raw = FIXTURE.read_bytes()
    assert b'Ccy="RON"' in raw  # a currency outside the old 7-currency table
    assert b"<pacs:Ctry>RO</pacs:Ctry>" in raw  # outside the old 10-country stub
    assert b"IntrBkSttlmAmt" in raw and b"InstdAmt" not in raw  # mandatory only
    assert raw.count(b"<pacs:AdrLine>") == 2  # hybrid, not fully structured
    assert raw.count(b"<pacs:TwnNm>") == 2
