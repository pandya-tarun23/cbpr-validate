"""Phase 5 definition of done: all three interfaces agree, byte for byte.

The library, the CLI and the API are three front doors onto one implementation.
These tests are the reason that claim is safe to make in the README - they
compare actual outputs rather than asserting each interface separately and
hoping. If someone later reimplements formatting inside the CLI or the API,
these fail.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from cbpr_validate.api.main import app as api_app
from cbpr_validate.cli import app as cli_app
from cbpr_validate.match.matcher import correlate
from cbpr_validate.parsers.parse import parse_message
from cbpr_validate.report.json_report import match_to_dict, validation_to_dict
from cbpr_validate.rules.registry import run_all
from tests.conftest import (
    PACS002,
    PACS004,
    PACS004_WRONG_UETR,
    PACS008_CLEAN,
    PACS008_UNSTRUCTURED,
    PACS009_COV,
)

runner = CliRunner()
client = TestClient(api_app)


def _library_validate(message: bytes) -> dict[str, Any]:
    return validation_to_dict(run_all(parse_message(message)))


def _cli_validate(path: Path) -> dict[str, Any]:
    result = runner.invoke(cli_app, ["check", str(path), "--format", "json"])
    assert result.exit_code in (0, 1), result.stdout
    parsed: dict[str, Any] = json.loads(result.stdout)
    return parsed


def _api_validate(message: bytes) -> dict[str, Any]:
    response = client.post("/validate", json={"message": message.decode()})
    assert response.status_code == 200
    parsed: dict[str, Any] = response.json()
    return parsed


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("pacs008_clean", PACS008_CLEAN),
        ("pacs008_unstructured", PACS008_UNSTRUCTURED),
        ("pacs009_cov", PACS009_COV),
        ("pacs002", PACS002),
        ("pacs004", PACS004),
    ],
)
def test_validate_is_identical_across_interfaces(
    name: str, message: bytes, tmp_path: Path
) -> None:
    path = tmp_path / f"{name}.xml"
    path.write_bytes(message)

    library = _library_validate(message)
    assert _cli_validate(path) == library
    assert _api_validate(message) == library


def _library_correlate(a: bytes, b: bytes, direction: str | None = None) -> dict[str, Any]:
    return match_to_dict(correlate(parse_message(a), parse_message(b), direction))


def _cli_correlate(a: Path, b: Path, direction: str | None = None) -> dict[str, Any]:
    args = ["match", str(a), str(b), "--format", "json"]
    if direction:
        args += ["--direction", direction]
    result = runner.invoke(cli_app, args)
    assert result.exit_code in (0, 1), result.stdout
    parsed: dict[str, Any] = json.loads(result.stdout)
    return parsed


def _api_correlate(a: bytes, b: bytes, direction: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"message_a": a.decode(), "message_b": b.decode()}
    if direction:
        body["direction"] = direction
    response = client.post("/correlate", json=body)
    assert response.status_code == 200
    parsed: dict[str, Any] = response.json()
    return parsed


@pytest.mark.parametrize(
    ("scenario", "a", "b", "direction"),
    [
        ("cov", PACS009_COV, PACS008_CLEAN, None),
        ("status", PACS002, PACS008_CLEAN, "outbound"),
        ("status_inbound", PACS002, PACS008_CLEAN, "inbound"),
        ("return", PACS004, PACS008_CLEAN, None),
        ("return_broken", PACS004_WRONG_UETR, PACS008_CLEAN, None),
    ],
)
def test_correlate_is_identical_across_interfaces(
    scenario: str, a: bytes, b: bytes, direction: str | None, tmp_path: Path
) -> None:
    path_a = tmp_path / f"{scenario}_a.xml"
    path_b = tmp_path / f"{scenario}_b.xml"
    path_a.write_bytes(a)
    path_b.write_bytes(b)

    library = _library_correlate(a, b, direction)
    assert _cli_correlate(path_a, path_b, direction) == library
    assert _api_correlate(a, b, direction) == library


def test_all_three_agree_on_the_verdict_not_just_the_payload(tmp_path: Path) -> None:
    """The CLI's exit code must track the same is_compliant the others report."""
    for message, compliant in ((PACS008_CLEAN, True), (PACS008_UNSTRUCTURED, False)):
        path = tmp_path / "m.xml"
        path.write_bytes(message)
        cli = runner.invoke(cli_app, ["check", str(path), "--format", "json"])
        assert (cli.exit_code == 0) is compliant
        assert _library_validate(message)["is_compliant"] is compliant
        assert _api_validate(message)["is_compliant"] is compliant
