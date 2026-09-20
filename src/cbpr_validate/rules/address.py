from __future__ import annotations

from cbpr_validate.codesets.loader import is_valid
from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.model.payment import Payment, PostalAddress
from cbpr_validate.rules.registry import register


def _classify_address(addr: PostalAddress | None) -> str:
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
def cbpr_addr_005_classify(payment: Payment) -> list[Finding]:
    findings: list[Finding] = []
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
def cbpr_addr_001_unstructured_only(payment: Payment) -> list[Finding]:
    findings: list[Finding] = []
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
def cbpr_addr_002_require_town_country(payment: Payment) -> list[Finding]:
    findings: list[Finding] = []
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


@register
def cbpr_addr_004_country_code(payment: Payment) -> list[Finding]:
    findings: list[Finding] = []
    for party_label, party in (("Dbtr", payment.dbtr), ("Cdtr", payment.cdtr)):
        addr = getattr(party, "postal_address", None) if party else None
        if addr and addr.ctry and not is_valid("ISO3166-1-alpha-2", addr.ctry):
            findings.append(
                Finding(
                    rule_id="CBPR-ADDR-004",
                    severity=Severity.ERROR,
                    message="Country must be a valid ISO 3166-1 alpha-2 code",
                    location=f"{party_label}.PstlAdr.Ctry",
                    remediation="Use a valid two-letter country code",
                    spec_reference="ISO3166-1-alpha-2 code set",
                )
            )
    return findings


MAX_ADRLINE_LEN = 70  # ISO 20022 AdrLine = Max70Text
MAX_ADRLINE_CNT = 7   # AdrLine maxOccurs = 7


@register
def cbpr_addr_006_adrline_length(payment: Payment) -> list[Finding]:
    findings: list[Finding] = []
    for party_label, party in (("Dbtr", payment.dbtr), ("Cdtr", payment.cdtr)):
        addr = getattr(party, "postal_address", None) if party else None
        if not addr or not addr.adr_line:
            continue
        if len(addr.adr_line) > MAX_ADRLINE_CNT:
            findings.append(
                Finding(
                    rule_id="CBPR-ADDR-006",
                    severity=Severity.ERROR,
                    message=(
                        f"Too many address lines: {len(addr.adr_line)} "
                        f"(max {MAX_ADRLINE_CNT})"
                    ),
                    location=f"{party_label}.PstlAdr.AdrLine",
                    remediation=f"Use at most {MAX_ADRLINE_CNT} AdrLine elements",
                    spec_reference="ISO 20022 pacs.008.001.08 AdrLine maxOccurs=7",
                )
            )
        for idx, line in enumerate(addr.adr_line, start=1):
            if len(line) > MAX_ADRLINE_LEN:
                findings.append(
                    Finding(
                        rule_id="CBPR-ADDR-006",
                        severity=Severity.ERROR,
                        message=(
                            f"Address line {idx} is {len(line)} characters "
                            f"(max {MAX_ADRLINE_LEN})"
                        ),
                        location=f"{party_label}.PstlAdr.AdrLine[{idx}]",
                        remediation=f"Keep each AdrLine within {MAX_ADRLINE_LEN} characters",
                        spec_reference="ISO 20022 pacs.008.001.08 AdrLine = Max70Text",
                    )
                )
    return findings

# CBPR-ADDR-003 is intentionally not registered here because the cap value is
# ambiguous in the public CBPR+ guideline material available for this phase.
# We avoid guessing and leave the rule unregistered rather than hard-coding an
# uncertain threshold.
