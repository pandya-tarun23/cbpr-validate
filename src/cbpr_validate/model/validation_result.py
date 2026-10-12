from __future__ import annotations

from pydantic import BaseModel

from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.profiles import DEFAULT_PROFILE, Profile


class ValidationResult(BaseModel):
    findings: list[Finding] = []
    #: Which rulebook these findings were judged against. Recorded on the
    #: result so every reporter can state it, and so a stored result is not
    #: ambiguous after the fact.
    profile: Profile = DEFAULT_PROFILE

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.WARN]

    @property
    def is_compliant(self) -> bool:
        return len(self.errors) == 0

    @property
    def overridden(self) -> list[Finding]:
        """Findings whose severity the active profile changed.

        Under ``current`` these are the SR2026 readiness gaps: things that do
        not block the payment today but will once the strict rulebook lands.
        """
        return [f for f in self.findings if f.was_overridden]
