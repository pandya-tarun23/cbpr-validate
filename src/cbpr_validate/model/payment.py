from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class Amount(BaseModel):
    value: Decimal = Field(...)
    currency: str = Field(..., min_length=3, max_length=3)


class PostalAddress(BaseModel):
    adr_line: Optional[List[str]] = None
    twn_nm: Optional[str] = None
    ctry: Optional[str] = None


class Party(BaseModel):
    name: Optional[str] = None
    postal_address: Optional[PostalAddress] = None


class Agent(BaseModel):
    bic: Optional[str] = None
    name: Optional[str] = None


class Payment(BaseModel):
    uetr: Optional[str] = None
    instr_id: Optional[str] = None
    tx_id: Optional[str] = None
    amount: Optional[Amount] = None
    dbtr: Optional[Party] = None
    cdtr: Optional[Party] = None
    dbtr_agt: Optional[Agent] = None
    cdtr_agt: Optional[Agent] = None
