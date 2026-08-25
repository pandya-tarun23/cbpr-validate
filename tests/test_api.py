"""Phase 5 - the FastAPI service."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cbpr_validate import __version__
from cbpr_validate.api.main import MatchResponse, ValidationResponse, app
from cbpr_validate.match.matcher import correlate
from cbpr_validate.parsers.parse import parse_message
from cbpr_validate.report.json_report import match_to_dict, validation_to_dict
from cbpr_validate.rules.registry import run_all
from tests.conftest import (
    NOT_A_MESSAGE,
    PACS002,
    PACS004,
    PACS004_WRONG_UETR,
    PACS008_CLEAN,
    PACS008_UNSTRUCTURED,
    PACS009_COV,
)

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_openapi_document_is_served() -> None:
    schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) >= {"/validate", "/correlate", "/health"}
    # the response models must be real schemas, not a bare object
    assert "ValidationResponse" in schema["components"]["schemas"]
    assert "MatchResponse" in schema["components"]["schemas"]


# --- /validate -------------------------------------------------------------


def test_validate_clean_message() -> None:
    response = client.post("/validate", json={"message": PACS008_CLEAN.decode()})
    assert response.status_code == 200
    assert response.json()["is_compliant"] is True


def test_validate_reports_findings() -> None:
    response = client.post("/validate", json={"message": PACS008_UNSTRUCTURED.decode()})
    payload = response.json()
    assert payload["is_compliant"] is False
    assert {f["rule_id"] for f in payload["findings"]} >= {"CBPR-ADDR-001", "CBPR-ADDR-002"}


@pytest.mark.parametrize("message", [PACS009_COV, PACS002, PACS004])
def test_validate_accepts_every_supported_family(message: bytes) -> None:
    assert client.post("/validate", json={"message": message.decode()}).status_code == 200


def test_validate_rejects_an_unrecognised_message() -> None:
    response = client.post("/validate", json={"message": NOT_A_MESSAGE.decode()})
    assert response.status_code == 400
    assert "message:" in response.json()["detail"]


def test_validate_rejects_a_missing_field() -> None:
    assert client.post("/validate", json={}).status_code == 422


# --- /correlate ------------------------------------------------------------


def test_correlate_clean_return() -> None:
    response = client.post(
        "/correlate",
        json={"message_a": PACS004.decode(), "message_b": PACS008_CLEAN.decode()},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["matched"] is True and payload["is_consistent"] is True
    assert payload["scenario"] == "RETURN"


def test_correlate_broken_link_is_still_a_200() -> None:
    # A correlation that fails is a *result*, not an HTTP error.
    response = client.post(
        "/correlate",
        json={"message_a": PACS004_WRONG_UETR.decode(), "message_b": PACS008_CLEAN.decode()},
    )
    assert response.status_code == 200
    assert response.json()["is_consistent"] is False


def test_correlate_cov() -> None:
    response = client.post(
        "/correlate",
        json={"message_a": PACS009_COV.decode(), "message_b": PACS008_CLEAN.decode()},
    )
    assert response.json()["scenario"] == "COV"


def test_correlate_status_requires_direction() -> None:
    response = client.post(
        "/correlate",
        json={"message_a": PACS002.decode(), "message_b": PACS008_CLEAN.decode()},
    )
    assert response.status_code == 400
    assert "direction is required" in response.json()["detail"]


def test_correlate_status_with_direction() -> None:
    response = client.post(
        "/correlate",
        json={
            "message_a": PACS002.decode(),
            "message_b": PACS008_CLEAN.decode(),
            "direction": "inbound",
        },
    )
    assert response.status_code == 200
    assert response.json()["direction"] == "inbound"


def test_correlate_rejects_an_invalid_direction() -> None:
    response = client.post(
        "/correlate",
        json={
            "message_a": PACS002.decode(),
            "message_b": PACS008_CLEAN.decode(),
            "direction": "sideways",
        },
    )
    assert response.status_code == 422


def test_correlate_rejects_an_unsupported_pair() -> None:
    response = client.post(
        "/correlate", json={"message_a": PACS002.decode(), "message_b": PACS004.decode()}
    )
    assert response.status_code == 400
    assert "Unsupported correlation pair" in response.json()["detail"]


def test_correlate_rejects_an_unparseable_message() -> None:
    response = client.post(
        "/correlate",
        json={"message_a": NOT_A_MESSAGE.decode(), "message_b": PACS008_CLEAN.decode()},
    )
    assert response.status_code == 400
    assert "message_a:" in response.json()["detail"]


# --- the response models really do mirror the reporter envelopes -----------


def test_response_models_mirror_the_json_reporter_keys() -> None:
    validation = validation_to_dict(run_all(parse_message(PACS008_UNSTRUCTURED)))
    assert set(validation) == set(ValidationResponse.model_fields)

    match = match_to_dict(
        correlate(parse_message(PACS004), parse_message(PACS008_CLEAN))
    )
    assert set(match) == set(MatchResponse.model_fields)
