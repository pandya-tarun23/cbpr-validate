"""Pairwise, stateless cross-message correlation (CBPR-COR-00x).

These checks are distinct from the rule groups in ``rules/``: a rule asks
"does this message comply with the guidelines?", a correlation asks "do these
two specific messages correctly reference each other?".

v1 is deliberately pairwise and stateless - you hand :func:`correlate` exactly
the two messages you want compared. There is no message store and no inference
about a stream of traffic over time (that is the v2 ``MessageStore``).

Matching is keyed on **UETR** first, because CBPR+ mandates the UETR persist
unchanged for the whole lifecycle of a payment; ``OrgnlTxId`` and
``OrgnlEndToEndId`` are used only when a UETR is absent on one side (legacy /
non-CBPR+ references), and that fallback is flagged on the result.
"""

from __future__ import annotations

from typing import NamedTuple

from cbpr_validate.match.result import (
    Direction,
    MatchKey,
    MatchResult,
    MessageRef,
    Scenario,
)
from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.model.payment import Amount, Payment

_SPEC_COV = (
    "CBPR+ Usage Guidelines - pacs.009 COV cover of an underlying "
    "customer credit transfer (UndrlygCstmrCdtTrf)"
)
_SPEC_STATUS = "CBPR+ Usage Guidelines - pacs.002 original references (OrgnlUETR/OrgnlTxId)"
_SPEC_RETURN = "CBPR+ Usage Guidelines - pacs.004 original references and returned amount"
_SPEC_UETR = "CBPR+ Usage Guidelines - UETR persists end-to-end across the payment lifecycle"


class UnsupportedPairError(ValueError):
    """Raised when the two messages are not one of the three v1 scenarios."""


class _Key(NamedTuple):
    matched: bool
    key: MatchKey
    value: str | None
    fallback_used: bool


def _resolve_key(
    ref_uetr: str | None,
    ref_tx_id: str | None,
    ref_end_to_end_id: str | None,
    original: Payment,
) -> _Key:
    """Decide whether the reference side points at ``original``, and on what.

    UETR wins whenever both sides carry one - including when they *disagree*,
    which is a genuine non-match rather than a reason to try a weaker key.
    """
    if ref_uetr and original.uetr:
        return _Key(ref_uetr == original.uetr, MatchKey.UETR, ref_uetr, False)
    if ref_tx_id and original.tx_id:
        return _Key(
            ref_tx_id == original.tx_id, MatchKey.ORGNL_TX_ID, ref_tx_id, True
        )
    if ref_end_to_end_id and original.end_to_end_id:
        return _Key(
            ref_end_to_end_id == original.end_to_end_id,
            MatchKey.ORGNL_END_TO_END_ID,
            ref_end_to_end_id,
            True,
        )
    return _Key(False, MatchKey.NONE, None, False)


def _no_link_finding(rule_id: str, key: _Key, spec: str) -> Finding:
    if key.key is MatchKey.NONE:
        message = (
            "The two messages share no identifier that can link them "
            "(no UETR, OrgnlTxId or OrgnlEndToEndId present on both sides)"
        )
        remediation = "Populate the UETR on both messages so they can be correlated"
    else:
        message = (
            f"{key.key.value} {key.value!r} on the referencing message does not match "
            f"the original - the two messages do not describe the same payment"
        )
        remediation = f"Check that the {key.key.value} was copied from the original message"
    return Finding(
        rule_id=rule_id,
        severity=Severity.ERROR,
        message=message,
        location=key.key.value if key.key is not MatchKey.NONE else None,
        remediation=remediation,
        spec_reference=spec if key.key is not MatchKey.NONE else _SPEC_UETR,
    )


def _comparable_amounts(a: Payment, b: Payment) -> tuple[Amount, Amount, str] | None:
    """Pick a like-for-like amount pair, or nothing.

    Never compares an interbank settlement amount against an instructed amount:
    once charges are deducted the two legitimately differ, so a cross-type
    comparison would manufacture a false mismatch.
    """
    if a.interbank_settlement_amount and b.interbank_settlement_amount:
        return (
            a.interbank_settlement_amount,
            b.interbank_settlement_amount,
            "IntrBkSttlmAmt",
        )
    if a.amount and b.amount:
        return a.amount, b.amount, "InstdAmt"
    return None


def _check_amounts(
    a: Payment, b: Payment, rule_id: str, spec: str, linked: list[str]
) -> list[Finding]:
    pair = _comparable_amounts(a, b)
    if pair is None:
        return []
    left, right, label = pair
    if left.currency != right.currency:
        return [
            Finding(
                rule_id=rule_id,
                severity=Severity.ERROR,
                message=(
                    f"{label} currency differs between the two messages: "
                    f"{left.currency} vs {right.currency}"
                ),
                location=label,
                remediation="The linked messages must settle in the same currency",
                spec_reference=spec,
            )
        ]
    if left.value != right.value:
        return [
            Finding(
                rule_id=rule_id,
                severity=Severity.ERROR,
                message=(
                    f"{label} differs between the two messages: "
                    f"{left.value} vs {right.value} {left.currency}"
                ),
                location=label,
                remediation="The linked messages must carry the same settlement amount",
                spec_reference=spec,
            )
        ]
    linked.append(label)
    return []


def _norm(name: str | None) -> str | None:
    """Normalise a party name for comparison (whitespace + case only)."""
    if name is None:
        return None
    collapsed = " ".join(name.split())
    return collapsed.upper() or None


def _check_parties(
    a: Payment, b: Payment, rule_id: str, spec: str, linked: list[str]
) -> list[Finding]:
    """Compare Dbtr/Cdtr names across the pair.

    Graded WARN, not ERROR, on purpose: the name a cover message carries is
    routinely re-keyed or truncated relative to the original, so a difference is
    worth surfacing but is not by itself proof the messages are inconsistent.
    A name we cannot compare (absent on either side) produces no finding.
    """
    findings: list[Finding] = []
    for label, left_party, right_party in (
        ("Dbtr", a.dbtr, b.dbtr),
        ("Cdtr", a.cdtr, b.cdtr),
    ):
        left_raw = left_party.name if left_party else None
        right_raw = right_party.name if right_party else None
        left, right = _norm(left_raw), _norm(right_raw)
        if left is None or right is None:
            continue
        if left != right:
            findings.append(
                Finding(
                    rule_id=rule_id,
                    severity=Severity.WARN,
                    message=(
                        f"{label} name differs between the two messages: "
                        f"{left_raw!r} vs {right_raw!r}"
                    ),
                    location=f"{label}/Nm",
                    party=label,
                    remediation="Carry the original party details through unchanged",
                    spec_reference=spec,
                )
            )
        else:
            linked.append(f"{label}/Nm")
    return findings


def _check_references(
    ref: Payment, original: Payment, rule_id: str, spec: str, linked: list[str]
) -> list[Finding]:
    """Cross-check the Orgnl* reference fields a pacs.002/pacs.004 echoes back.

    Runs independently of which key the pair matched on: a message can match on
    UETR and still quote the wrong OrgnlTxId. Graded WARN because the linkage
    itself is already established by the match key - this is a data-quality
    inconsistency in the echoed references, not a broken link.
    """
    findings: list[Finding] = []
    for label, quoted, actual in (
        ("OrgnlMsgId", ref.orgnl_msg_id, original.msg_id),
        ("OrgnlTxId", ref.orgnl_tx_id, original.tx_id),
        ("OrgnlEndToEndId", ref.orgnl_end_to_end_id, original.end_to_end_id),
    ):
        if not quoted or not actual:
            continue
        if quoted != actual:
            findings.append(
                Finding(
                    rule_id=rule_id,
                    severity=Severity.WARN,
                    message=(
                        f"{label} {quoted!r} does not match the original message's "
                        f"value {actual!r}"
                    ),
                    location=label,
                    remediation=f"Echo {label} exactly as it appeared on the original message",
                    spec_reference=spec,
                )
            )
        else:
            linked.append(label)
    return findings


def _correlate_cov(cov: Payment, original: Payment) -> MatchResult:
    """CBPR-COR-001 - pacs.009 COV <-> the originating pacs.008 it covers."""
    refs = (MessageRef.from_payment(cov), MessageRef.from_payment(original))
    underlying = cov.underlying
    if underlying is None:
        return MatchResult(
            matched=False,
            scenario=Scenario.COV,
            match_key=MatchKey.NONE,
            message_a=refs[0],
            message_b=refs[1],
            mismatches=[
                Finding(
                    rule_id="CBPR-COR-001",
                    severity=Severity.ERROR,
                    message=(
                        "The pacs.009 carries no UndrlygCstmrCdtTrf - it is a core "
                        "pacs.009, not a COV, so it cannot cover a pacs.008"
                    ),
                    location="FICdtTrf/CdtTrfTxInf/UndrlygCstmrCdtTrf",
                    remediation="Correlate a COV (pacs.009 carrying the underlying transfer)",
                    spec_reference=_SPEC_COV,
                )
            ],
        )

    key = _resolve_key(
        underlying.uetr, underlying.tx_id, underlying.end_to_end_id, original
    )
    linked: list[str] = []
    mismatches: list[Finding] = []
    if key.matched:
        linked.append(key.key.value)
        mismatches += _check_amounts(underlying, original, "CBPR-COR-001", _SPEC_COV, linked)
        mismatches += _check_parties(underlying, original, "CBPR-COR-001", _SPEC_COV, linked)
    else:
        mismatches.append(_no_link_finding("CBPR-COR-001", key, _SPEC_COV))

    return MatchResult(
        matched=key.matched,
        scenario=Scenario.COV,
        match_key=key.key,
        uetr=underlying.uetr if key.key is MatchKey.UETR else None,
        linked_fields=linked,
        mismatches=mismatches,
        message_a=refs[0],
        message_b=refs[1],
        fallback_used=key.fallback_used,
    )


def _correlate_status(
    status: Payment, original: Payment, direction: Direction
) -> MatchResult:
    """CBPR-COR-002 - pacs.002 <-> pacs.008, in either direction."""
    key = _resolve_key(
        status.orgnl_uetr, status.orgnl_tx_id, status.orgnl_end_to_end_id, original
    )
    linked: list[str] = []
    mismatches: list[Finding] = []
    if key.matched:
        linked.append(key.key.value)
        mismatches += _check_references(status, original, "CBPR-COR-002", _SPEC_STATUS, linked)
    else:
        mismatches.append(_no_link_finding("CBPR-COR-002", key, _SPEC_STATUS))

    return MatchResult(
        matched=key.matched,
        scenario=Scenario.STATUS,
        match_key=key.key,
        uetr=status.orgnl_uetr if key.key is MatchKey.UETR else None,
        linked_fields=linked,
        mismatches=mismatches,
        message_a=MessageRef.from_payment(status),
        message_b=MessageRef.from_payment(original),
        direction=direction,
        fallback_used=key.fallback_used,
    )


def _check_returned_amount(rtn: Payment, original: Payment) -> list[Finding]:
    """Cross-check the pacs.004's amounts against the *actual* original.

    ``CBPR-RTN-003`` already checks returned <= original using the amounts the
    return itself declares. The cross-message value-add here is checking those
    declared amounts against the pacs.008 they claim to return - a return can be
    internally consistent and still misstate the original.

    Only compares against the pacs.008's interbank settlement amount; if the
    original does not carry one there is nothing like-for-like to compare an
    ``OrgnlIntrBkSttlmAmt`` with, and we emit nothing rather than guess.
    """
    actual = original.interbank_settlement_amount
    if actual is None:
        return []

    findings: list[Finding] = []
    declared = rtn.orgnl_interbank_settlement_amount
    if declared is not None and (
        declared.currency != actual.currency or declared.value != actual.value
    ):
        findings.append(
            Finding(
                rule_id="CBPR-COR-003",
                severity=Severity.ERROR,
                message=(
                    f"OrgnlIntrBkSttlmAmt on the return ({declared.value} "
                    f"{declared.currency}) does not match the original pacs.008 "
                    f"({actual.value} {actual.currency})"
                ),
                location="TxInf/OrgnlTxRef/OrgnlIntrBkSttlmAmt",
                remediation="Quote the original settlement amount exactly as it was sent",
                spec_reference=_SPEC_RETURN,
            )
        )

    returned = rtn.returned_interbank_settlement_amount
    if (
        returned is not None
        and returned.currency == actual.currency
        and returned.value > actual.value
    ):
        findings.append(
            Finding(
                rule_id="CBPR-COR-003",
                severity=Severity.ERROR,
                message=(
                    f"Returned amount {returned.value} {returned.currency} exceeds the "
                    f"original pacs.008 settlement amount {actual.value} {actual.currency}"
                ),
                location="TxInf/RtrdIntrBkSttlmAmt",
                remediation="A return may never settle for more than the original payment",
                spec_reference=_SPEC_RETURN,
            )
        )
    return findings


def _correlate_return(rtn: Payment, original: Payment) -> MatchResult:
    """CBPR-COR-003 - pacs.004 return <-> the original pacs.008."""
    key = _resolve_key(
        rtn.orgnl_uetr, rtn.orgnl_tx_id, rtn.orgnl_end_to_end_id, original
    )
    linked: list[str] = []
    mismatches: list[Finding] = []
    if key.matched:
        linked.append(key.key.value)
        mismatches += _check_references(rtn, original, "CBPR-COR-003", _SPEC_RETURN, linked)
        mismatches += _check_returned_amount(rtn, original)
    else:
        mismatches.append(_no_link_finding("CBPR-COR-003", key, _SPEC_RETURN))

    return MatchResult(
        matched=key.matched,
        scenario=Scenario.RETURN,
        match_key=key.key,
        uetr=rtn.orgnl_uetr if key.key is MatchKey.UETR else None,
        linked_fields=linked,
        mismatches=mismatches,
        message_a=MessageRef.from_payment(rtn),
        message_b=MessageRef.from_payment(original),
        fallback_used=key.fallback_used,
    )


def correlate(
    a: Payment, b: Payment, direction: Direction | str | None = None
) -> MatchResult:
    """Correlate two parsed messages.

    The scenario is inferred from the pair of message types, in either argument
    order:

    * pacs.009 COV + pacs.008 -> ``CBPR-COR-001``
    * pacs.002     + pacs.008 -> ``CBPR-COR-002`` (``direction`` required)
    * pacs.004     + pacs.008 -> ``CBPR-COR-003``

    ``direction`` is mandatory for the pacs.002 scenario and must be supplied by
    the caller: the tool does not infer whose pacs.008 it is from the BICs, so
    there is no safe default to fall back on.

    Raises :class:`UnsupportedPairError` for any other combination.
    """
    pair = {a.message_type, b.message_type}

    if pair == {"pacs.009", "pacs.008"}:
        cov, original = (a, b) if a.message_type == "pacs.009" else (b, a)
        return _correlate_cov(cov, original)

    if pair == {"pacs.002", "pacs.008"}:
        if direction is None:
            raise ValueError(
                "direction is required for a pacs.002 <-> pacs.008 correlation "
                "(outbound = we sent the pacs.008, inbound = we received it); "
                "identity is never inferred from BICs"
            )
        status, original = (a, b) if a.message_type == "pacs.002" else (b, a)
        return _correlate_status(status, original, Direction(direction))

    if pair == {"pacs.004", "pacs.008"}:
        rtn, original = (a, b) if a.message_type == "pacs.004" else (b, a)
        return _correlate_return(rtn, original)

    raise UnsupportedPairError(
        f"Unsupported correlation pair: {a.message_type} + {b.message_type}. "
        f"v1 supports pacs.009 COV/pacs.008, pacs.002/pacs.008 and pacs.004/pacs.008."
    )
