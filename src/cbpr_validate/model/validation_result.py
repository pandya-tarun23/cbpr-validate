from __future__ import annotations

from pydantic import BaseModel

from cbpr_validate.model.finding import Finding, Severity


class ValidationResult(BaseModel):
    findings: list[Finding] = []

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.WARN]

    @property
    def is_compliant(self) -> bool:
        return len(self.errors) == 0
