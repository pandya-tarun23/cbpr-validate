from __future__ import annotations

from decimal import Decimal

from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.model.payment import Payment
from cbpr_validate.rules.registry import register

_FRACTION_DIGITS = {
    "AUD": 2,
    "CAD": 2,
    "CHF": 2,
    "EUR": 2,
    "GBP": 2,
    "JPY": 0,
    "USD": 2,
}


@register
def cbpr_amt_001_currency(payment: Payment) -> list[Finding]:
    findings: list[Finding] = []
    currency = payment.amount.currency if payment.amount else None
    if currency and currency not in _FRACTION_DIGITS:
        findings.append(
            Finding(
                rule_id="CBPR-AMT-001",
                severity=Severity.ERROR,
                message="Currency is not a recognised ISO 4217 currency",
                location="Amount.Currency",
                remediation="Use a supported ISO 4217 currency code",
                spec_reference="ISO 4217 currency code list",
            )
        )
    return findings


@register
def cbpr_amt_002_fractional_digits(payment: Payment) -> list[Finding]:
    findings: list[Finding] = []
    if not payment.amount:
        return findings
    currency = payment.amount.currency
    value = payment.amount.value
    expected_digits = _FRACTION_DIGITS.get(currency)
    if expected_digits is None:
        return findings
    if currency == "JPY" and value != int(value):
        findings.append(
            Finding(
                rule_id="CBPR-AMT-002",
                severity=Severity.ERROR,
                message="JPY amounts must be whole numbers without decimals",
                location="Amount",
                remediation="Use an integer amount for JPY",
                spec_reference="ISO 4217 / CBPR+ amount formatting",
            )
        )
    elif expected_digits == 2 and value != value.quantize(Decimal("0.01")):
        findings.append(
            Finding(
                rule_id="CBPR-AMT-002",
                severity=Severity.ERROR,
                message="Amount fractional digits do not match the currency convention",
                location="Amount",
                remediation="Use the expected number of decimal places for the currency",
                spec_reference="ISO 4217 / CBPR+ amount formatting",
            )
        )
    return findings


@register
def cbpr_amt_003_positive_amount(payment: Payment) -> list[Finding]:
    findings: list[Finding] = []
    if payment.amount and payment.amount.value <= 0:
        findings.append(
            Finding(
                rule_id="CBPR-AMT-003",
                severity=Severity.ERROR,
                message="Amount must be greater than zero",
                location="Amount",
                remediation="Use a positive payment amount",
                spec_reference="CBPR+ payment amount rules",
            )
        )
    return findings
