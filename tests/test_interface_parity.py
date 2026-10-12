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


PROFILES = ("current", "sr2026")


def _library_validate(message: bytes, profile: str = "current") -> dict[str, Any]:
    return validation_to_dict(run_all(parse_message(message), profile=profile))


def _cli_validate(path: Path, profile: str = "current") -> dict[str, Any]:
    result = runner.invoke(
        cli_app, ["check", str(path), "--format", "json", "--profile", profile]
    )
    assert result.exit_code in (0, 1), result.stdout
    parsed: dict[str, Any] = json.loads(result.stdout)
    return parsed


def _api_validate(message: bytes, profile: str = "current") -> dict[str, Any]:
    response = client.post(
        "/validate", json={"message": message.decode(), "profile": profile}
    )
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
@pytest.mark.parametrize("profile", PROFILES)
def test_validate_is_identical_across_interfaces(
    name: str, message: bytes, profile: str, tmp_path: Path
) -> None:
    path = tmp_path / f"{name}.xml"
    path.write_bytes(message)

    library = _library_validate(message, profile)
    assert library["profile"] == profile
    assert _cli_validate(path, profile) == library
    assert _api_validate(message, profile) == library


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


@pytest.mark.parametrize(
    ("profile", "message", "compliant"),
    [
        # The clean message is compliant under either rulebook.
        ("current", PACS008_CLEAN, True),
        ("sr2026", PACS008_CLEAN, True),
        # The unstructured address is the one that moves: a readiness gap
        # today, a rejection once SR2026 lands.
        ("current", PACS008_UNSTRUCTURED, True),
        ("sr2026", PACS008_UNSTRUCTURED, False),
    ],
)
def test_all_three_agree_on_the_verdict_not_just_the_payload(
    profile: str, message: bytes, compliant: bool, tmp_path: Path
) -> None:
    """The CLI's exit code must track the same is_compliant the others report."""
    path = tmp_path / "m.xml"
    path.write_bytes(message)
    cli = runner.invoke(
        cli_app, ["check", str(path), "--format", "json", "--profile", profile]
    )
    assert (cli.exit_code == 0) is compliant
    assert _library_validate(message, profile)["is_compliant"] is compliant
    assert _api_validate(message, profile)["is_compliant"] is compliant


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("message", [PACS008_CLEAN, PACS008_UNSTRUCTURED])
def test_check_and_validate_agree_on_the_verdict(
    profile: str, message: bytes, tmp_path: Path
) -> None:
    """``check`` and ``validate`` reach the rules by different roads - ``check``
    parses for itself while ``validate`` goes through ``core`` - so this pins
    that they still return the same verdict for the same profile. Deliberate
    guard while that divergence remains (see KNOWN_ISSUES.md)."""
    path = tmp_path / "m.xml"
    path.write_bytes(message)
    via_check = runner.invoke(
        cli_app, ["check", str(path), "--format", "json", "--profile", profile]
    )
    via_validate = runner.invoke(
        cli_app, ["validate", str(path), "--json", "--profile", profile]
    )
    assert via_check.exit_code == via_validate.exit_code
    assert json.loads(via_check.stdout) == json.loads(via_validate.stdout)
