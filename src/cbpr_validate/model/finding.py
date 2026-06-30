from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class Severity(str, Enum):
    ERROR = "ERROR"
    WARN = "WARN"
    INFO = "INFO"


class Finding(BaseModel):
    rule_id: str
    severity: Severity
    message: str
    location: Optional[str] = None
    party: Optional[str] = None
    remediation: Optional[str] = None
    spec_reference: Optional[str] = None
