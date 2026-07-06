from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class Severity(StrEnum):
    ERROR = "ERROR"
    WARN = "WARN"
    INFO = "INFO"


class Finding(BaseModel):
    rule_id: str
    severity: Severity
    message: str
    location: str | None = None
    party: str | None = None
    remediation: str | None = None
    spec_reference: str | None = None
