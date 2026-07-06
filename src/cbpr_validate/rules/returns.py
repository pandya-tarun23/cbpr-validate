"""pacs.004 PaymentReturn rules (CBPR-RTN-00x)."""

from __future__ import annotations

from decimal import Decimal

from cbpr_validate.codesets.loader import is_valid
from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.model.payment import Payment
from cbpr_validate.rules.registry import register


def _is_return(payment: Payment) -> bool:
    return payment.message_type == "pacs.004"


@register
def cbpr_rtn_001_return_reason(payment: Payment) -> list[Finding]:
    """Return reason code must be in ExternalReturnReason1Code — ERROR."""
    if not _is_return(payment):
        return []
    findings: list[Finding] = []
    if payment.return_reason and not is_valid(
        "ExternalReturnReason1Code", payment.return_reason
    ):
        findings.append(
            Finding(
                rule_id="CBPR-RTN-001",
                severity=Severity.ERROR,
                message=(
                    f"Return reason '{payment.return_reason}' is not in "
                    f"ExternalReturnReason1Code"
                ),
                location="TxInf/RtrRsnInf/Rsn/Cd",
                remediation="Use a valid ExternalReturnReason1Code value",
                spec_reference="ExternalReturnReason1Code (ISO 20022 External Code Set)",
            )
        )
    return findings


@register
def cbpr_rtn_002_original_references(payment: Payment) -> list[Finding]:
    """The six mandatory original-reference fields must be present — ERROR."""
    if not _is_return(payment):
        return []
    required: list[tuple[str, object]] = [
        ("OrgnlMsgId", payment.orgnl_msg_id),
        ("OrgnlEndToEndId", payment.orgnl_end_to_end_id),
        ("OrgnlTxId", payment.orgnl_tx_id),
        ("OrgnlUETR", payment.orgnl_uetr),
        ("OrgnlIntrBkSttlmAmt", payment.orgnl_interbank_settlement_amount),
        ("OrgnlIntrBkSttlmDt", payment.orgnl_interbank_settlement_date),
    ]
    findings: list[Finding] = []
    for field, value in required:
        if not value:
            findings.append(
                Finding(
                    rule_id="CBPR-RTN-002",
                    severity=Severity.ERROR,
                    message=f"Mandatory original-reference field {field} is missing on the return",
                    location=f"TxInf/OrgnlTxRef/{field}",
                    remediation=f"Populate {field} from the original payment being returned",
                    spec_reference=(
                        "CBPR+ Usage Guidelines — pacs.004 PaymentReturn (original references)"
                    ),
                )
            )
    return findings


@register
def cbpr_rtn_003_returned_amount(payment: Payment) -> list[Finding]:
    """Returned interbank settlement amount vs original, net of charges — ERROR/WARN.

    CBPR+ requires the returned amount to equal the original interbank
    settlement amount less any charges the returning agents deduct and disclose
    in ChrgsInf. The *exact* permitted charge deduction / rounding tolerance is
    not stated unambiguously in the public guideline material available for this
    phase, so — rather than invent a numeric tolerance — we take the
    CONSERVATIVE reading (same discipline as CBPR-ADDR-003):

      * returned > original  -> ERROR. A return may never settle for *more* than
        the original; there is no interpretation under which this is valid.
      * returned < original  -> the shortfall must be explained by disclosed
        charges. If disclosed charges (ChrgsInf) do not account for it (or are
        absent), we raise a WARN rather than assert a hard numeric tolerance.
      * currency mismatch between returned and original -> ERROR.

    The precise tolerance is intentionally NOT hard-coded; see the WARN branch.
    """
    if not _is_return(payment):
        return []
    original = payment.orgnl_interbank_settlement_amount
    returned = payment.returned_interbank_settlement_amount
    if original is None or returned is None:
        return []  # RTN-002 already flags missing original amount

    findings: list[Finding] = []
    if returned.currency != original.currency:
        findings.append(
            Finding(
                rule_id="CBPR-RTN-003",
                severity=Severity.ERROR,
                message=(
                    f"Returned amount currency {returned.currency} differs from original "
                    f"{original.currency}"
                ),
                location="TxInf/RtrdIntrBkSttlmAmt",
                remediation="Return in the original settlement currency",
                spec_reference="CBPR+ Usage Guidelines — pacs.004 returned amount",
            )
        )
        return findings

    if returned.value > original.value:
        findings.append(
            Finding(
                rule_id="CBPR-RTN-003",
                severity=Severity.ERROR,
                message=(
                    f"Returned amount {returned.value} exceeds the original interbank "
                    f"settlement amount {original.value}"
                ),
                location="TxInf/RtrdIntrBkSttlmAmt",
                remediation="The returned amount must not exceed the original settlement amount",
                spec_reference="CBPR+ Usage Guidelines — pacs.004 returned amount ≤ original",
            )
        )
    elif returned.value < original.value:
        disclosed = _total_charges(payment)
        # Conservative: only accept the shortfall if disclosed charges account
        # for it exactly. Any unexplained reduction is a WARN, not silently OK.
        if disclosed is None or (returned.value + disclosed) != original.value:
            findings.append(
                Finding(
                    rule_id="CBPR-RTN-003",
                    severity=Severity.WARN,
                    message=(
                        f"Returned amount {returned.value} is less than the original "
                        f"{original.value} but the difference is not fully explained by "
                        f"disclosed charges"
                    ),
                    location="TxInf/RtrdIntrBkSttlmAmt",
                    remediation=(
                        "Disclose the deducted charges in ChrgsInf so the amounts reconcile"
                    ),
                    spec_reference=(
                        "CBPR+ Usage Guidelines — pacs.004 returned amount net of charges"
                    ),
                )
            )
    return findings


def _total_charges(payment: Payment) -> Decimal | None:
    if not payment.charges:
        return None
    total = Decimal("0")
    seen = False
    for charge in payment.charges:
        if charge.amount is not None:
            total += charge.amount.value
            seen = True
    return total if seen else None


@register
def cbpr_rtn_004_charges_reconcile(payment: Payment) -> list[Finding]:
    """If ChrgsInf is present, it must reconcile original vs returned — WARN."""
    if not _is_return(payment):
        return []
    original = payment.orgnl_interbank_settlement_amount
    returned = payment.returned_interbank_settlement_amount
    disclosed = _total_charges(payment)
    if original is None or returned is None or disclosed is None:
        return []
    if returned.currency != original.currency:
        return []  # currency mismatch handled by RTN-003
    findings: list[Finding] = []
    if returned.value + disclosed != original.value:
        findings.append(
            Finding(
                rule_id="CBPR-RTN-004",
                severity=Severity.WARN,
                message=(
                    f"ChrgsInf does not reconcile: returned {returned.value} + charges "
                    f"{disclosed} != original {original.value}"
                ),
                location="TxInf/ChrgsInf",
                remediation="Ensure returned amount + disclosed charges equals the original amount",
                spec_reference="CBPR+ Usage Guidelines — pacs.004 ChrgsInf reconciliation",
            )
        )
    return findings


@register
def cbpr_rtn_005_compensation(payment: Payment) -> list[Finding]:
    """Compensation/interest fields, if present, must be well-formed — INFO."""
    if not _is_return(payment):
        return []
    comp = payment.compensation_amount
    if comp is None:
        return []
    findings: list[Finding] = []
    if comp.value <= 0 or len(comp.currency) != 3:
        findings.append(
            Finding(
                rule_id="CBPR-RTN-005",
                severity=Severity.INFO,
                message=(
                    f"Compensation amount is not well-formed (value={comp.value}, "
                    f"currency={comp.currency})"
                ),
                location="TxInf/CompstnAmt",
                remediation="Provide a positive compensation amount with a 3-letter currency",
                spec_reference="CBPR+ Usage Guidelines — pacs.004 compensation/interest",
            )
        )
    return findings
