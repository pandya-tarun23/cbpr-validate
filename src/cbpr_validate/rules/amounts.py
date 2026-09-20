from __future__ import annotations

from decimal import Decimal

from cbpr_validate.codesets.loader import is_valid
from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.model.payment import Payment
from cbpr_validate.rules.registry import register

# ISO 4217 minor units (decimal places). Default is 2; only the exceptions are
# listed here. Validity of the currency itself is a *separate* concern handled
# by CBPR-AMT-001 against the full ISO4217 code set — this map is only about how
# many decimals a (valid) currency is allowed.
_ZERO_DECIMAL = {
    "BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW",
    "PYG", "RWF", "UGX", "UYI", "VND", "VUV", "XAF", "XOF", "XPF",
}
_THREE_DECIMAL = {"BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"}


def _expected_decimals(currency: str) -> int:
    if currency in _ZERO_DECIMAL:
        return 0
    if currency in _THREE_DECIMAL:
        return 3
    return 2  # ISO 4217 default


@register
def cbpr_amt_001_currency(payment: Payment) -> list[Finding]:
    """Currency must be a recognised ISO 4217 code (full code set)."""
    findings: list[Finding] = []
    currency = payment.amount.currency if payment.amount else None
    if currency and not is_valid("ISO4217", currency):
        findings.append(
            Finding(
                rule_id="CBPR-AMT-001",
                severity=Severity.ERROR,
                message="Currency is not a recognised ISO 4217 currency",
                location="Amount.Currency",
                remediation="Use a valid ISO 4217 currency code",
                spec_reference="ISO 4217 currency code list",
            )
        )
    return findings


@register
def cbpr_amt_002_fractional_digits(payment: Payment) -> list[Finding]:
    """Amount must not carry more decimals than the currency's minor units."""
    findings: list[Finding] = []
    if not payment.amount:
        return findings
    currency = payment.amount.currency
    value = payment.amount.value
    # An unknown currency is already reported by CBPR-AMT-001; don't double-flag.
    if not currency or not is_valid("ISO4217", currency):
        return findings
    expected = _expected_decimals(currency)
    quantum = Decimal(1).scaleb(-expected)  # 1, 0.1, 0.01, 0.001 ...
    if value != value.quantize(quantum):
        findings.append(
            Finding(
                rule_id="CBPR-AMT-002",
                severity=Severity.ERROR,
                message=(
                    f"Amount has more decimal places than {currency} allows "
                    f"(max {expected})"
                ),
                location="Amount",
                remediation=f"Use at most {expected} decimal place(s) for {currency}",
                spec_reference="ISO 4217 minor units / CBPR+ amount formatting",
            )
        )
    return findings


@register
def cbpr_amt_003_positive_amount(payment: Payment) -> list[Finding]:
    """Amount must be greater than zero."""
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
