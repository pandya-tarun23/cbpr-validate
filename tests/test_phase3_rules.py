from decimal import Decimal
from typing import Any

from cbpr_validate.model.payment import (
    Agent,
    Amount,
    Party,
    Payment,
    PostalAddress,
)
from cbpr_validate.rules.registry import run_all


def _make_payment(**overrides: Any) -> Payment:
    defaults: dict[str, Any] = {
        "message_type": "pacs.008",
        "uetr": "11111111-1111-4111-8111-111111111111",
        "amount": Amount(value=Decimal("100.00"), currency="EUR"),
        "dbtr": Party(name="Debtor", postal_address=PostalAddress(twn_nm="London", ctry="GB")),
        "cdtr": Party(name="Creditor", postal_address=PostalAddress(twn_nm="Paris", ctry="FR")),
        "dbtr_agt": Agent(bic="DEUTDEFF"),
        "cdtr_agt": Agent(bic="BARCGB22"),
        "purpose": "CORT",
        "category_purpose": "CASH",
        "charge_bearer": "SLEV",
        "status_reason": "ACCP",
        "settlement_method": "CLRG",
        "clearing_system": "RTGS",
    }
    defaults.update(overrides)
    return Payment(**defaults)


def test_code_rules_validate_against_snapshot() -> None:
    valid = _make_payment()
    result = run_all(valid)
    assert not any(f.rule_id == "CBPR-COD-001" for f in result.findings)
    assert not any(f.rule_id == "CBPR-COD-003" for f in result.findings)

    invalid = _make_payment(purpose="ZZZZ", charge_bearer="BOGUS")
    result = run_all(invalid)
    ids = {f.rule_id for f in result.findings}
    assert "CBPR-COD-001" in ids
    assert "CBPR-COD-003" in ids


def test_category_purpose_rule() -> None:
    invalid = _make_payment(category_purpose="BOGUS")
    result = run_all(invalid)
    ids = {f.rule_id for f in result.findings}
    assert "CBPR-COD-002" in ids
    # CBPR-COD-004 (status reason) is now exercised against a real parsed
    # pacs.002 in tests/test_cod004_pacs002.py — no direct-construction workaround.


def test_amount_rules() -> None:
    valid = _make_payment(amount=Amount(value=Decimal("100.00"), currency="EUR"))
    result = run_all(valid)
    assert not any(f.rule_id == "CBPR-AMT-001" for f in result.findings)
    assert not any(f.rule_id == "CBPR-AMT-002" for f in result.findings)

    invalid_currency = _make_payment(amount=Amount(value=Decimal("100.00"), currency="ZZZ"))
    currency_result = run_all(invalid_currency)
    assert any(f.rule_id == "CBPR-AMT-001" for f in currency_result.findings)

    invalid_jpy = _make_payment(amount=Amount(value=Decimal("100.50"), currency="JPY"))
    jpy_result = run_all(invalid_jpy)
    assert any(f.rule_id == "CBPR-AMT-002" for f in jpy_result.findings)

    zero_amount = _make_payment(amount=Amount(value=Decimal("0"), currency="EUR"))
    zero_result = run_all(zero_amount)
    assert any(f.rule_id == "CBPR-AMT-003" for f in zero_result.findings)


def test_structural_rules() -> None:
    valid = _make_payment()
    result = run_all(valid)
    assert not any(f.rule_id == "CBPR-STR-001" for f in result.findings)

    invalid_uetr = _make_payment(uetr="not-a-uuid")
    uetr_result = run_all(invalid_uetr)
    assert any(f.rule_id == "CBPR-STR-001" for f in uetr_result.findings)

    invalid_bic = _make_payment(dbtr_agt=Agent(bic="BADBIC"), cdtr_agt=Agent(bic="BADBIC"))
    bic_result = run_all(invalid_bic)
    assert any(f.rule_id == "CBPR-STR-002" for f in bic_result.findings)

    missing_field = _make_payment(dbtr=None)
    structural_result = run_all(missing_field)
    assert any(f.rule_id == "CBPR-STR-003" for f in structural_result.findings)

    missing_clearing = _make_payment(clearing_system=None)
    clearing_result = run_all(missing_clearing)
    assert any(f.rule_id == "CBPR-STR-004" for f in clearing_result.findings)


def test_address_country_rule() -> None:
    valid = _make_payment(
        dbtr=Party(name="Debtor", postal_address=PostalAddress(twn_nm="London", ctry="GB"))
    )
    result = run_all(valid)
    assert not any(f.rule_id == "CBPR-ADDR-004" for f in result.findings)

    invalid_country = _make_payment(
        dbtr=Party(
            name="Debtor",
            postal_address=PostalAddress(twn_nm="London", ctry="ZZ"),
        )
    )
    invalid_result = run_all(invalid_country)
    assert any(f.rule_id == "CBPR-ADDR-004" for f in invalid_result.findings)
