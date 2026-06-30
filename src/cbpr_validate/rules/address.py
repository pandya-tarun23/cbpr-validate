from __future__ import annotations

from typing import List, Optional

from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.model.payment import Payment, PostalAddress
from cbpr_validate.rules.registry import register


def _classify_address(addr: Optional[PostalAddress]) -> str:
    if addr is None:
        return "none"
    if addr.twn_nm and addr.ctry:
        if addr.adr_line:
            return "hybrid"
        return "structured"
    if addr.adr_line:
        return "unstructured"
    return "unknown"


@register
def cbpr_addr_005_classify(payment: Payment) -> List[Finding]:
    findings: List[Finding] = []
    for party_label, party in (("Dbtr", payment.dbtr), ("Cdtr", payment.cdtr)):
        addr = getattr(party, "postal_address", None) if party else None
        classification = _classify_address(addr)
        findings.append(
            Finding(
                rule_id="CBPR-ADDR-005",
                severity=Severity.INFO,
                message=f"Address classification for {party_label}: {classification}",
                location=f"{party_label}.PstlAdr",
                spec_reference="SR2026/CBPR+",
            )
        )
    return findings


@register
def cbpr_addr_001_unstructured_only(payment: Payment) -> List[Finding]:
    findings: List[Finding] = []
    for party_label, party in (("Dbtr", payment.dbtr), ("Cdtr", payment.cdtr)):
        addr = getattr(party, "postal_address", None) if party else None
        if addr and addr.adr_line and not addr.twn_nm and not addr.ctry:
            findings.append(
                Finding(
                    rule_id="CBPR-ADDR-001",
                    severity=Severity.ERROR,
                    message="Unstructured-only address (AdrLine without TwnNm/Ctry)",
                    location=f"{party_label}.PstlAdr",
                    remediation="Provide TownName and Country per SR2026",
                    spec_reference="SR2026",
                )
            )
    return findings


@register
def cbpr_addr_002_require_town_country(payment: Payment) -> List[Finding]:
    findings: List[Finding] = []
    for party_label, party in (("Dbtr", payment.dbtr), ("Cdtr", payment.cdtr)):
        addr = getattr(party, "postal_address", None) if party else None
        if addr and (not addr.twn_nm or not addr.ctry):
            findings.append(
                Finding(
                    rule_id="CBPR-ADDR-002",
                    severity=Severity.ERROR,
                    message="Minimum gate: TownName and Country must be present",
                    location=f"{party_label}.PstlAdr",
                    remediation="Include both TwnNm and Ctry for the postal address",
                    spec_reference="SR2026",
                )
            )
    return findings
