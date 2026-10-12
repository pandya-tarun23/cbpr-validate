from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, model_validator


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
    # The severity the rule itself declared, before any severity profile was
    # applied. Rules never set this: it is filled in from ``severity`` on
    # construction, so a finding always carries both. ``severity !=
    # base_severity`` is therefore the signal that a profile changed this
    # finding - see ``cbpr_validate.profiles``.
    base_severity: Severity

    @model_validator(mode="before")
    @classmethod
    def _default_base_severity(cls, data: Any) -> Any:
        """Default ``base_severity`` to ``severity`` when it is not supplied.

        This runs before field validation, which is what lets every rule keep
        passing only ``severity=`` and still produce a finding with both
        fields populated.
        """
        if isinstance(data, dict) and "base_severity" not in data:
            severity = data.get("severity")
            if severity is not None:
                data = {**data, "base_severity": severity}
        return data

    @property
    def was_overridden(self) -> bool:
        """True when a severity profile changed this finding's severity."""
        return self.severity is not self.base_severity
