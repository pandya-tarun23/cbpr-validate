"""The output model for cross-message correlation.

A :class:`MatchResult` is deliberately *not* a ``ValidationResult``. A
``ValidationResult`` says whether one message complies with the guidelines; a
``MatchResult`` says whether **two specific messages correctly reference each
other**, which is a property of the relationship, not of either message.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.model.payment import Payment


class Scenario(StrEnum):
    """The correlation scenario, inferred from the pair of message types."""

    COV = "COV"  # pacs.009 COV  <-> originating pacs.008
    STATUS = "STATUS"  # pacs.002       <-> pacs.008 (bidirectional)
    RETURN = "RETURN"  # pacs.004       <-> original pacs.008


class Direction(StrEnum):
    """Whose pacs.008 it is, for the bidirectional pacs.002 scenario.

    Supplied explicitly by the caller. The tool deliberately does NOT infer
    identity from BICs — it has no notion of "you".
    """

    OUTBOUND = "outbound"  # we sent the pacs.008, the pacs.002 is the reply
    INBOUND = "inbound"  # we received the pacs.008 and sent the pacs.002


class MatchKey(StrEnum):
    """The field the match was decided on.

    UETR is always tried first: CBPR+ mandates it persist end-to-end across a
    payment's lifecycle. The other two are legacy fallbacks and set
    ``MatchResult.fallback_used``.
    """

    UETR = "UETR"
    ORGNL_TX_ID = "OrgnlTxId"
    ORGNL_END_TO_END_ID = "OrgnlEndToEndId"
    NONE = "NONE"  # no shared identifier on both sides — cannot be linked


class MessageRef(BaseModel):
    """A minimal handle on one side of the pair, for reporting."""

    message_type: str | None = None
    uetr: str | None = None
    tx_id: str | None = None
    msg_id: str | None = None

    @classmethod
    def from_payment(cls, payment: Payment) -> MessageRef:
        return cls(
            message_type=payment.message_type,
            uetr=payment.uetr,
            tx_id=payment.tx_id,
            msg_id=payment.msg_id,
        )


class MatchResult(BaseModel):
    matched: bool
    scenario: Scenario
    match_key: MatchKey
    uetr: str | None = None
    linked_fields: list[str] = []
    mismatches: list[Finding] = []
    message_a: MessageRef
    message_b: MessageRef
    # Set for the STATUS scenario; echoed back so a report records which way
    # round the caller said the pacs.008 travelled.
    direction: Direction | None = None
    # True when the pair had to be linked on OrgnlTxId/OrgnlEndToEndId because a
    # UETR was absent on one or both sides. Surfaced so a consumer can treat a
    # legacy linkage with less confidence than a UETR linkage.
    fallback_used: bool = False

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.mismatches if f.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.mismatches if f.severity == Severity.WARN]

    @property
    def is_consistent(self) -> bool:
        """The two messages are linked AND nothing about the link is in error."""
        return self.matched and not self.errors
