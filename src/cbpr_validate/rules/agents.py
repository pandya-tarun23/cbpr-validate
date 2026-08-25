"""Agent-chain and pacs.009 COV rules (CBPR-AGT-00x).

The headline rule here is ``CBPR-AGT-002`` - the reimbursement-vs-intermediary
agent distinction on a pacs.009 COV, which most generic validators get wrong.
"""

from __future__ import annotations

import re

from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.model.payment import Agent, Payment
from cbpr_validate.rules.registry import register

# ISO 17442 LEI: 18 alphanumerics (prefix + entity) followed by 2 check digits.
_LEI_RE = re.compile(r"^[A-Z0-9]{18}[0-9]{2}$")


def _bic(agent: Agent | None) -> str | None:
    return agent.bic if agent and agent.bic else None


@register
def cbpr_agt_001_chain_consistency(payment: Payment) -> list[Finding]:
    """Agent-chain consistency across Dbtr/Instg/Intrmy/Cdtr agents - WARN.

    A coherent cross-border chain routes a payment *through* distinct agents.
    Re-using one BIC for two opposite ends of the chain (e.g. the same agent as
    both DbtrAgt and CdtrAgt, or as both InstgAgt and InstdAgt) collapses the
    chain and is almost always an assembly error rather than a real routing.
    """
    if payment.message_type not in ("pacs.008", "pacs.009"):
        return []

    findings: list[Finding] = []
    for label, a, b in (
        ("DbtrAgt/CdtrAgt", payment.dbtr_agt, payment.cdtr_agt),
        ("InstgAgt/InstdAgt", payment.instg_agt, payment.instd_agt),
    ):
        bic_a, bic_b = _bic(a), _bic(b)
        if bic_a and bic_b and bic_a == bic_b:
            findings.append(
                Finding(
                    rule_id="CBPR-AGT-001",
                    severity=Severity.WARN,
                    message=(
                        f"Agent chain collapses: {label} carry the same BIC "
                        f"({bic_a}); opposite ends of the chain should differ"
                    ),
                    location=label,
                    remediation="Verify the agent chain; opposite roles should be distinct agents",
                    spec_reference=(
                        "CBPR+ Usage Guidelines - agent chain "
                        "(Instg/Instd/Intrmy/Dbtr/Cdtr agents)"
                    ),
                )
            )
    return findings


@register
def cbpr_agt_002_cov_reimbursement_vs_intermediary(payment: Payment) -> list[Finding]:
    """pacs.009 COV: reimbursement agents must be distinct from intermediary agents - ERROR.

    On a pacs.009 COV the cover (interbank reimbursement) leg is conveyed via the
    reimbursement agents - InstgRmbrsmntAgt / InstdRmbrsmntAgt / ThrdRmbrsmntAgt -
    which settle between the debtor and creditor agents. Intermediary agents
    (IntrmyAgt1/2/3) belong to the *routing* path, including the underlying
    customer credit transfer. These are semantically different roles: an agent
    acting as a reimbursement (cover) institution must not simultaneously be
    presented as an intermediary agent, on the cover or in the embedded
    underlying transaction. Conflating them is the classic COV error.
    """
    if payment.message_type != "pacs.009" or payment.underlying is None:
        return []  # only meaningful for a COV (embedded underlying present)

    reimbursement = {
        _bic(payment.instg_rmbrsmnt_agt),
        _bic(payment.instd_rmbrsmnt_agt),
        _bic(payment.thrd_rmbrsmnt_agt),
    } - {None}

    intermediary = {
        _bic(payment.intrmy_agt1),
        _bic(payment.intrmy_agt2),
        _bic(payment.underlying.intrmy_agt1),
        _bic(payment.underlying.intrmy_agt2),
    } - {None}

    findings: list[Finding] = []
    collision = reimbursement & intermediary
    for bic in sorted(str(b) for b in collision):
        findings.append(
            Finding(
                rule_id="CBPR-AGT-002",
                severity=Severity.ERROR,
                message=(
                    f"Agent {bic} is used as both a reimbursement (cover) agent and an "
                    f"intermediary agent on a pacs.009 COV; these are distinct roles"
                ),
                location="FICdtTrf/CdtTrfTxInf (reimbursement vs intermediary agents)",
                remediation=(
                    "Convey the cover/settlement institution via InstgRmbrsmntAgt/"
                    "InstdRmbrsmntAgt and keep intermediary routing in IntrmyAgt#"
                ),
                spec_reference=(
                    "CBPR+ Usage Guidelines - pacs.009 COV (Financial Institution Credit "
                    "Transfer, cover); reimbursement agents vs intermediary agents"
                ),
            )
        )
    return findings


@register
def cbpr_agt_003_lei(payment: Payment) -> list[Finding]:
    """LEI present/valid where it may be required - INFO.

    CBPR+ encourages (and in a growing set of cases requires) an ISO 17442 LEI on
    financial-institution and organisation parties. We report, at INFO, any LEI
    that is present but malformed. Absence is not flagged as an error here.
    """
    findings: list[Finding] = []
    checks: list[tuple[str, str | None]] = [
        ("Dbtr", payment.dbtr.lei if payment.dbtr else None),
        ("Cdtr", payment.cdtr.lei if payment.cdtr else None),
        ("DbtrAgt", payment.dbtr_agt.lei if payment.dbtr_agt else None),
        ("CdtrAgt", payment.cdtr_agt.lei if payment.cdtr_agt else None),
    ]
    for label, lei in checks:
        if lei and not _LEI_RE.match(lei):
            findings.append(
                Finding(
                    rule_id="CBPR-AGT-003",
                    severity=Severity.INFO,
                    message=f"{label} LEI '{lei}' is not a well-formed ISO 17442 LEI",
                    location=f"{label}.LEI",
                    remediation="Use a valid 20-character ISO 17442 LEI",
                    spec_reference="ISO 17442 (LEI); CBPR+ LEI usage guideline",
                )
            )
    return findings
