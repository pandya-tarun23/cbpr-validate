from __future__ import annotations

from typing import List

from pydantic import BaseModel

from cbpr_validate.model.finding import Finding, Severity


class ValidationResult(BaseModel):
    findings: List[Finding] = []

    @property
    def errors(self):
        return [f for f in self.findings if f.severity == Severity.ERROR]

    @property
    def warnings(self):
        return [f for f in self.findings if f.severity == Severity.WARN]

    @property
    def is_compliant(self) -> bool:
        return len(self.errors) == 0
