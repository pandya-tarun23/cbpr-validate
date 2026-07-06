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


class Agent(BaseModel):
    bic: str | None = None
    name: str | None = None


class Payment(BaseModel):
    message_type: str | None = None
    uetr: str | None = None
    instr_id: str | None = None
    tx_id: str | None = None
    amount: Amount | None = None
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
