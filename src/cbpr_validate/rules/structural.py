from __future__ import annotations

import re

from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.model.payment import Payment
from cbpr_validate.rules.registry import register

_UUID4_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


@register
def cbpr_str_001_uetr(payment: Payment) -> list[Finding]:
    findings: list[Finding] = []
    if not payment.uetr or not _UUID4_RE.match(payment.uetr):
        findings.append(
            Finding(
                rule_id="CBPR-STR-001",
                severity=Severity.ERROR,
                message="UETR must be present and valid UUIDv4",
                location="UETR",
                remediation="Populate a valid UUIDv4 UETR",
                spec_reference="CBPR+ UETR guidance",
            )
        )
    return findings


@register
def cbpr_str_002_agent_bics(payment: Payment) -> list[Finding]:
    findings: list[Finding] = []
    for label, agent in (("DbtrAgt", payment.dbtr_agt), ("CdtrAgt", payment.cdtr_agt)):
        if agent and agent.bic and not re.fullmatch(
            r"[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?", agent.bic
        ):
            findings.append(
                Finding(
                    rule_id="CBPR-STR-002",
                    severity=Severity.ERROR,
                    message=f"{label} BIC is not in a valid ISO BIC format",
                    location=f"{label}.BIC",
                    remediation="Use a valid 8- or 11-character BIC",
                    spec_reference="ISO 9362 / BIC format",
                )
            )
    return findings


@register
def cbpr_str_003_mandatory_elements(payment: Payment) -> list[Finding]:
    findings: list[Finding] = []
    if payment.message_type != "pacs.008":
        return findings
    if not payment.dbtr:
        findings.append(
            Finding(
                rule_id="CBPR-STR-003",
                severity=Severity.ERROR,
                message="Mandatory debtor element is missing for pacs.008",
                location="Dbtr",
                remediation="Populate the debtor party details",
                spec_reference="CBPR+ pacs.008 mandatory elements",
            )
        )
    if not payment.cdtr:
        findings.append(
            Finding(
                rule_id="CBPR-STR-003",
                severity=Severity.ERROR,
                message="Mandatory creditor element is missing for pacs.008",
                location="Cdtr",
                remediation="Populate the creditor party details",
                spec_reference="CBPR+ pacs.008 mandatory elements",
            )
        )
    # IntrBkSttlmAmt is the mandatory amount on a pacs.008 (1..1). InstdAmt is
    # OPTIONAL (0..1), so its absence is not a defect - checking it here marked
    # genuinely compliant messages non-compliant. Any conditional InstdAmt
    # requirement is a separate rule, deliberately not folded in here.
    if not payment.interbank_settlement_amount:
        findings.append(
            Finding(
                rule_id="CBPR-STR-003",
                severity=Severity.ERROR,
                message="Mandatory IntrBkSttlmAmt is missing for pacs.008",
                location="IntrBkSttlmAmt",
                remediation="Populate the interbank settlement amount",
                spec_reference="CBPR+ pacs.008 mandatory elements",
            )
        )
    return findings


@register
def cbpr_str_004_settlement_consistency(payment: Payment) -> list[Finding]:
    findings: list[Finding] = []
    if payment.settlement_method and payment.clearing_system:
        if payment.settlement_method == "CLRG" and payment.clearing_system != "RTGS":
            findings.append(
                Finding(
                    rule_id="CBPR-STR-004",
                    severity=Severity.WARN,
                    message="Settlement method and clearing system are not aligned",
                    location="ClearingSystem",
                    remediation="Review the settlement and clearing-system values",
                    spec_reference="CBPR+ settlement guidance",
                )
            )
    elif payment.settlement_method or payment.clearing_system:
        findings.append(
            Finding(
                rule_id="CBPR-STR-004",
                severity=Severity.WARN,
                message="Settlement and clearing-system values are incomplete",
                location="ClearingSystem",
                remediation="Populate both settlement method and clearing system",
                spec_reference="CBPR+ settlement guidance",
            )
        )
    return findings
