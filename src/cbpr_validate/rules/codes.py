from __future__ import annotations

from cbpr_validate.codesets.loader import is_valid
from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.model.payment import Payment
from cbpr_validate.rules.registry import register


@register
def cbpr_cod_001_purpose(payment: Payment) -> list[Finding]:
    findings: list[Finding] = []
    if payment.purpose and not is_valid("ExternalPurpose1Code", payment.purpose):
        findings.append(
            Finding(
                rule_id="CBPR-COD-001",
                severity=Severity.ERROR,
                message="Purpose code is not in ExternalPurpose1Code",
                location="Purpose",
                remediation="Use a valid ExternalPurpose1Code value",
                spec_reference="ExternalPurpose1Code (ISO 20022 code set)",
            )
        )
    return findings


@register
def cbpr_cod_002_category_purpose(payment: Payment) -> list[Finding]:
    findings: list[Finding] = []
    if payment.category_purpose and not is_valid(
        "ExternalCategoryPurpose1Code", payment.category_purpose
    ):
        findings.append(
            Finding(
                rule_id="CBPR-COD-002",
                severity=Severity.ERROR,
                message="Category purpose code is not in ExternalCategoryPurpose1Code",
                location="CategoryPurpose",
                remediation="Use a valid ExternalCategoryPurpose1Code value",
                spec_reference="ExternalCategoryPurpose1Code (ISO 20022 code set)",
            )
        )
    return findings


@register
def cbpr_cod_003_charge_bearer(payment: Payment) -> list[Finding]:
    findings: list[Finding] = []
    allowed = {"DEBT", "CRED", "SHAR", "SLEV"}
    if payment.charge_bearer and payment.charge_bearer not in allowed:
        findings.append(
            Finding(
                rule_id="CBPR-COD-003",
                severity=Severity.ERROR,
                message="Charge bearer is outside the CBPR+ allowed set",
                location="ChargeBearer",
                remediation="Use one of DEBT, CRED, SHAR, SLEV",
                spec_reference="CBPR+ usage guideline / charge-bearer code set",
            )
        )
    return findings


@register
def cbpr_cod_004_status_reason(payment: Payment) -> list[Finding]:
    findings: list[Finding] = []
    if payment.status_reason and not is_valid("ExternalStatusReason1Code", payment.status_reason):
        findings.append(
            Finding(
                rule_id="CBPR-COD-004",
                severity=Severity.WARN,
                message="Status reason code is not in ExternalStatusReason1Code",
                location="StatusReason",
                remediation="Use a valid ExternalStatusReason1Code value if available",
                spec_reference="ExternalStatusReason1Code (ISO 20022 code set)",
            )
        )
    return findings
