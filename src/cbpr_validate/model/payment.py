from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class Amount(BaseModel):
    value: Decimal = Field(...)
    currency: str = Field(..., min_length=3, max_length=3)


class PostalAddress(BaseModel):
    adr_line: list[str] | None = None
    twn_nm: str | None = None
    ctry: str | None = None


class Party(BaseModel):
    name: str | None = None
    postal_address: PostalAddress | None = None
    lei: str | None = None


class Agent(BaseModel):
    bic: str | None = None
    name: str | None = None
    lei: str | None = None


class ChargeInfo(BaseModel):
    """A single ChrgsInf entry (charge amount + the agent that levied it)."""

    amount: Amount | None = None
    agent: Agent | None = None


class Payment(BaseModel):
    message_type: str | None = None
    uetr: str | None = None
    instr_id: str | None = None
    tx_id: str | None = None
    amount: Amount | None = None
    # --- Phase 4.5: identifiers/amount the correlation engine matches on ---
    # msg_id is the GrpHdr MsgId a pacs.002/pacs.004 echoes back as OrgnlMsgId;
    # end_to_end_id is the UETR fallback for legacy/non-CBPR+ references.
    # interbank_settlement_amount is kept distinct from `amount` (InstdAmt on a
    # pacs.008) so correlation only ever compares like with like.
    msg_id: str | None = None
    end_to_end_id: str | None = None
    interbank_settlement_amount: Amount | None = None
    dbtr: Party | None = None
    cdtr: Party | None = None
    dbtr_agt: Agent | None = None
    cdtr_agt: Agent | None = None
    purpose: str | None = None
    category_purpose: str | None = None
    charge_bearer: str | None = None
    status_reason: str | None = None
    settlement_method: str | None = None
    clearing_system: str | None = None

    # --- Phase 4: agent chain (pacs.009 core + COV) ---
    instg_agt: Agent | None = None
    instd_agt: Agent | None = None
    intrmy_agt1: Agent | None = None
    intrmy_agt2: Agent | None = None
    # Reimbursement (cover/settlement side) agents — distinct role from
    # intermediary agents. Conflating the two is the classic pacs.009 COV error.
    instg_rmbrsmnt_agt: Agent | None = None
    instd_rmbrsmnt_agt: Agent | None = None
    thrd_rmbrsmnt_agt: Agent | None = None
    # The embedded underlying customer credit transfer carried by a pacs.009 COV.
    underlying: Payment | None = None

    # --- Phase 4: status report (pacs.002) ---
    tx_status: str | None = None

    # --- Phase 4: return (pacs.004) ---
    return_reason: str | None = None
    orgnl_msg_id: str | None = None
    orgnl_end_to_end_id: str | None = None
    orgnl_tx_id: str | None = None
    orgnl_uetr: str | None = None
    orgnl_interbank_settlement_amount: Amount | None = None
    orgnl_interbank_settlement_date: str | None = None
    returned_interbank_settlement_amount: Amount | None = None
    charges: list[ChargeInfo] | None = None
    compensation_amount: Amount | None = None
