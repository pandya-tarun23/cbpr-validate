"""Regression tests for CBPR-STR-003's amount check.

The rule used to test `payment.amount`, which the pacs.008 parser sources from
`InstdAmt`. In pacs.008 `IntrBkSttlmAmt` is the mandatory amount (1..1) and
`InstdAmt` is OPTIONAL (0..1), so a genuinely compliant message carrying only
`IntrBkSttlmAmt` was reported NOT COMPLIANT.

These tests pin both directions of the fix: the rule must fire on a missing
`IntrBkSttlmAmt`, and must stay silent on a missing `InstdAmt`.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from cbpr_validate import validate_bytes
from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.model.payment import Amount, Party, Payment, PostalAddress
from cbpr_validate.rules.structural import cbpr_str_003_mandatory_elements

FIXTURE = Path(__file__).parent / "fixtures" / "pacs008_valid_hybrid_ro.xml"

_ADDRESS = PostalAddress(adr_line=["High Street"], twn_nm="Epping", ctry="GB")


def _payment(**overrides: object) -> Payment:
    """A pacs.008 that satisfies STR-003, unless an override removes something."""
    fields: dict[str, object] = {
        "message_type": "pacs.008",
        "dbtr": Party(name="Debtor Co", postal_address=_ADDRESS),
        "cdtr": Party(name="Ardent Finance", postal_address=_ADDRESS),
        "interbank_settlement_amount": Amount(value=Decimal("591636"), currency="RON"),
        "amount": Amount(value=Decimal("591636"), currency="RON"),
    }
    fields.update(overrides)
    return Payment(**fields)  # type: ignore[arg-type]


def _amount_findings(payment: Payment) -> list[Finding]:
    return [
        f
        for f in cbpr_str_003_mandatory_elements(payment)
        if f.location == "IntrBkSttlmAmt"
    ]


# --- the rule fires on the mandatory field ---------------------------------


def test_str003_fires_when_interbank_settlement_amount_is_absent() -> None:
    findings = _amount_findings(_payment(interbank_settlement_amount=None))
    assert len(findings) == 1
    assert findings[0].rule_id == "CBPR-STR-003"
    assert findings[0].severity is Severity.ERROR
    assert findings[0].message == "Mandatory IntrBkSttlmAmt is missing for pacs.008"
    assert findings[0].location == "IntrBkSttlmAmt"


def test_str003_fires_even_when_instd_amt_is_present() -> None:
    """InstdAmt must not satisfy the mandatory-amount check."""
    payment = _payment(
        interbank_settlement_amount=None,
        amount=Amount(value=Decimal("591636"), currency="RON"),
    )
    assert len(_amount_findings(payment)) == 1


# --- and stays silent on the optional one ----------------------------------


def test_str003_does_not_fire_when_only_instd_amt_is_absent() -> None:
    """The false positive this fix removes. InstdAmt is 0..1, not 1..1."""
    assert _amount_findings(_payment(amount=None)) == []


def test_str003_does_not_fire_when_both_amounts_are_present() -> None:
    assert _amount_findings(_payment()) == []


def test_str003_never_reports_instd_amt_as_a_missing_mandatory_element() -> None:
    """No STR-003 finding may point at InstdAmt, whatever is missing."""
    for payment in (
        _payment(amount=None),
        _payment(interbank_settlement_amount=None),
        _payment(amount=None, interbank_settlement_amount=None),
        _payment(dbtr=None, cdtr=None, amount=None),
    ):
        locations = {f.location for f in cbpr_str_003_mandatory_elements(payment)}
        assert "InstdAmt" not in locations


# --- the other STR-003 branches are untouched ------------------------------


def test_str003_still_checks_debtor_and_creditor() -> None:
    locations = {f.location for f in cbpr_str_003_mandatory_elements(_payment(dbtr=None))}
    assert locations == {"Dbtr"}
    locations = {f.location for f in cbpr_str_003_mandatory_elements(_payment(cdtr=None))}
    assert locations == {"Cdtr"}


def test_str003_only_applies_to_pacs008() -> None:
    other = _payment(message_type="pacs.009", interbank_settlement_amount=None)
    assert cbpr_str_003_mandatory_elements(other) == []


# --- proven end to end on a real CBPR+ message -----------------------------


def test_real_cbpr_plus_message_does_not_trip_str003() -> None:
    """A live SWIFT CBPR+ pacs.008 (envelope + AppHdr, IntrBkSttlmAmt in RON,
    no InstdAmt) - exactly the shape the old rule wrongly rejected."""
    result = validate_bytes(FIXTURE.read_bytes())
    assert not any(f.rule_id == "CBPR-STR-003" for f in result.findings)


def test_real_message_fixture_has_the_shape_the_bug_needed() -> None:
    """Guards the fixture itself: if someone adds an InstdAmt to it, the test
    above stops proving anything."""
    raw = FIXTURE.read_bytes()
    assert b"IntrBkSttlmAmt" in raw
    assert b"InstdAmt" not in raw
