"""FastAPI service: ``POST /validate`` and ``POST /correlate``.

Like the CLI, this is a shell over the library. Both endpoints build their
response from the same ``report.json_report`` envelopes the CLI's ``--format
json`` prints, so the two interfaces cannot disagree about a message. The
response models below exist to give the OpenAPI document real schemas rather
than a bare ``object`` - their fields mirror those envelopes exactly, and a test
pins that correspondence.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from cbpr_validate import __version__
from cbpr_validate.match.matcher import UnsupportedPairError, correlate
from cbpr_validate.match.result import Direction, MatchKey, MessageRef, Scenario
from cbpr_validate.model.finding import Finding
from cbpr_validate.model.payment import Payment
from cbpr_validate.parsers.parse import UnsupportedMessageTypeError, parse_message
from cbpr_validate.report.json_report import match_to_dict, validation_to_dict
from cbpr_validate.rules.registry import run_all

app = FastAPI(
    title="cbpr-validate",
    version=__version__,
    summary="Validate ISO 20022 CBPR+ messages against the usage guidelines, not just the XSD.",
    description=(
        "Two operations. `/validate` runs every registered usage-guideline rule "
        "against a single message. `/correlate` checks whether two specific "
        "messages correctly reference each other (pairwise and stateless - no "
        "message store).\n\n"
        "**XSD-valid is not CBPR+-compliant.** The optional XSD layer is CLI-only: "
        "it needs schemas this project does not redistribute."
    ),
)


class ValidateRequest(BaseModel):
    message: str = Field(
        ...,
        description="The ISO 20022 message as XML (pacs.008, pacs.009, pacs.002 or pacs.004).",
    )


class CorrelateRequest(BaseModel):
    message_a: str = Field(..., description="First message, as XML.")
    message_b: str = Field(..., description="Second message, as XML. Order does not matter.")
    direction: Direction | None = Field(
        None,
        description=(
            "Required for a pacs.002 <-> pacs.008 pair: whether the caller sent the "
            "pacs.008 (outbound) or received it (inbound). Never inferred from BICs."
        ),
    )


class ValidationResponse(BaseModel):
    """Mirrors ``report.json_report.validation_to_dict``."""

    is_compliant: bool
    summary: dict[str, int]
    findings: list[Finding]


class MatchResponse(BaseModel):
    """Mirrors ``report.json_report.match_to_dict``."""

    matched: bool
    is_consistent: bool
    scenario: Scenario
    match_key: MatchKey
    uetr: str | None
    direction: Direction | None
    fallback_used: bool
    linked_fields: list[str]
    message_a: MessageRef
    message_b: MessageRef
    summary: dict[str, int]
    mismatches: list[Finding]


class HealthResponse(BaseModel):
    status: str
    version: str


def _parse(xml: str, label: str) -> Payment:
    try:
        return parse_message(xml.encode())
    except UnsupportedMessageTypeError as exc:
        raise HTTPException(status_code=400, detail=f"{label}: {exc}") from exc


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    """Liveness probe."""
    return HealthResponse(status="ok", version=__version__)


@app.post("/validate", response_model=ValidationResponse, tags=["validate"])
def validate(request: ValidateRequest) -> ValidationResponse:
    """Run every registered CBPR+ usage-guideline rule against one message."""
    payment = _parse(request.message, "message")
    return ValidationResponse(**validation_to_dict(run_all(payment)))


@app.post("/correlate", response_model=MatchResponse, tags=["correlate"])
def correlate_messages(request: CorrelateRequest) -> MatchResponse:
    """Check whether two specific messages correctly reference each other."""
    a = _parse(request.message_a, "message_a")
    b = _parse(request.message_b, "message_b")
    try:
        result = correlate(a, b, request.direction)
    except UnsupportedPairError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:  # missing direction for the pacs.002 scenario
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MatchResponse(**match_to_dict(result))
