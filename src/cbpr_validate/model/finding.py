from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


def _drop_schema_default(schema: dict[str, Any]) -> None:
    """Remove a field's ``default`` from the generated JSON schema."""
    schema.pop("default", None)


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
    # applied. Rules never set this: ``_default_base_severity`` below copies it
    # from ``severity`` on construction, so a finding always carries both and
    # the field is never null. ``severity != base_severity`` is therefore the
    # signal that a profile changed this finding - see
    # ``cbpr_validate.profiles``.
    #
    # The ``None`` default exists only so that callers (every rule) may omit
    # the argument; the pre-validator always replaces it, which is why the
    # declared type is a plain ``Severity`` rather than an optional one. The
    # ignore is the price of pydantic having no way to default one field from
    # another in the annotation itself.
    # ``json_schema_extra`` drops the null default from the generated schema:
    # the default is an implementation detail of construction, and advertising
    # it in the OpenAPI document would wrongly suggest the field can come back
    # null.
    base_severity: Severity = Field(
        default=None,  # type: ignore[assignment]
        json_schema_extra=_drop_schema_default,
    )

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
