"""Phase 5 - the Typer CLI.

Exit codes are part of the contract (this is meant to run as a CI gate), so
every test asserts one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from typer.testing import CliRunner

from cbpr_validate import __version__
from cbpr_validate.cli import EXIT_FINDINGS, EXIT_INPUT_ERROR, EXIT_OK, app, main
from cbpr_validate.config import ENV_XSD_DIR
from tests.test_schema_xsd import PERMISSIVE_XSD

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == EXIT_OK
    assert __version__ in result.stdout


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert "check" in result.stdout and "match" in result.stdout


# --- check -----------------------------------------------------------------


def test_check_clean_message_exits_zero(pacs008_clean: Path) -> None:
    result = runner.invoke(app, ["check", str(pacs008_clean)])
    assert result.exit_code == EXIT_OK
    assert "COMPLIANT" in result.stdout


def test_check_non_compliant_message_exits_one(pacs008_unstructured: Path) -> None:
    result = runner.invoke(app, ["check", str(pacs008_unstructured)])
    assert result.exit_code == EXIT_FINDINGS
    assert "NOT COMPLIANT" in result.stdout
    assert "CBPR-ADDR-001" in result.stdout


def test_check_json_format(pacs008_unstructured: Path) -> None:
    result = runner.invoke(app, ["check", str(pacs008_unstructured), "--format", "json"])
    assert result.exit_code == EXIT_FINDINGS
    payload = json.loads(result.stdout)
    assert payload["is_compliant"] is False


def test_check_junit_format(pacs008_unstructured: Path) -> None:
    result = runner.invoke(app, ["check", str(pacs008_unstructured), "-f", "junit"])
    assert result.exit_code == EXIT_FINDINGS
    root = ET.fromstring(result.stdout)
    assert root.findall(".//failure")


def test_check_fail_on_never_still_reports_but_exits_zero(pacs008_unstructured: Path) -> None:
    result = runner.invoke(
        app, ["check", str(pacs008_unstructured), "--fail-on", "never"]
    )
    assert result.exit_code == EXIT_OK
    assert "NOT COMPLIANT" in result.stdout


def test_check_fail_on_warn_ignores_info_findings(pacs008_clean: Path) -> None:
    # The clean pacs.008 emits only ADDR-005 INFO classifications, so tightening
    # the gate to WARN must still exit 0 - INFO is reporting, not a defect.
    result = runner.invoke(app, ["check", str(pacs008_clean), "--fail-on", "warn"])
    assert result.exit_code == EXIT_OK
    assert "INFO" in result.stdout


def test_check_rejects_an_unrecognised_message(not_a_message: Path) -> None:
    result = runner.invoke(app, ["check", str(not_a_message)])
    assert result.exit_code == EXIT_INPUT_ERROR
    assert "Could not determine the message type" in result.stderr


def test_check_rejects_a_missing_file(tmp_path: Path) -> None:
    result = runner.invoke(app, ["check", str(tmp_path / "nope.xml")])
    assert result.exit_code != EXIT_OK  # Typer's own exists=True check


def test_check_xsd_without_configuration_is_an_input_error(
    pacs008_clean: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ENV_XSD_DIR, raising=False)
    result = runner.invoke(app, ["check", str(pacs008_clean), "--xsd"])
    assert result.exit_code == EXIT_INPUT_ERROR
    assert "no schema directory is configured" in result.stderr


# --- match -----------------------------------------------------------------


def test_match_clean_return_exits_zero(pacs004: Path, pacs008_clean: Path) -> None:
    result = runner.invoke(app, ["match", str(pacs004), str(pacs008_clean)])
    assert result.exit_code == EXIT_OK
    assert "CONSISTENT" in result.stdout


def test_match_broken_link_exits_one(pacs004_wrong_uetr: Path, pacs008_clean: Path) -> None:
    result = runner.invoke(app, ["match", str(pacs004_wrong_uetr), str(pacs008_clean)])
    assert result.exit_code == EXIT_FINDINGS
    assert "NOT LINKED" in result.stdout


def test_match_cov(pacs009_cov: Path, pacs008_clean: Path) -> None:
    result = runner.invoke(app, ["match", str(pacs009_cov), str(pacs008_clean)])
    assert result.exit_code == EXIT_OK
    assert "COV correlation" in result.stdout


def test_match_status_requires_direction(pacs002: Path, pacs008_clean: Path) -> None:
    result = runner.invoke(app, ["match", str(pacs002), str(pacs008_clean)])
    assert result.exit_code == EXIT_INPUT_ERROR
    assert "direction is required" in result.stderr


def test_match_status_with_direction(pacs002: Path, pacs008_clean: Path) -> None:
    result = runner.invoke(
        app, ["match", str(pacs002), str(pacs008_clean), "--direction", "outbound"]
    )
    assert result.exit_code == EXIT_OK
    assert "Direction: outbound" in result.stdout


def test_match_rejects_an_unsupported_pair(pacs002: Path, pacs004: Path) -> None:
    result = runner.invoke(app, ["match", str(pacs002), str(pacs004)])
    assert result.exit_code == EXIT_INPUT_ERROR
    assert "Unsupported correlation pair" in result.stderr


def test_match_json_and_junit(pacs004: Path, pacs008_clean: Path) -> None:
    as_json = runner.invoke(
        app, ["match", str(pacs004), str(pacs008_clean), "--format", "json"]
    )
    assert json.loads(as_json.stdout)["scenario"] == "RETURN"
    as_junit = runner.invoke(
        app, ["match", str(pacs004), str(pacs008_clean), "--format", "junit"]
    )
    assert ET.fromstring(as_junit.stdout).find("testsuite") is not None


def test_match_rejects_an_unparseable_input(not_a_message: Path, pacs008_clean: Path) -> None:
    result = runner.invoke(app, ["match", str(not_a_message), str(pacs008_clean)])
    assert result.exit_code == EXIT_INPUT_ERROR


# --- the optional XSD layer, driven end to end -----------------------------


def test_check_with_xsd_dir_runs_both_layers(
    pacs008_unstructured: Path, tmp_path: Path
) -> None:
    """The point of the project in one test: the document is XSD-valid, and the
    usage-guideline layer still rejects it."""
    schemas = tmp_path / "schemas"
    schemas.mkdir()
    (schemas / "pacs.008.001.08.xsd").write_text(PERMISSIVE_XSD, encoding="utf-8")

    result = runner.invoke(
        app,
        ["check", str(pacs008_unstructured), "--xsd", "--xsd-dir", str(schemas), "-f", "json"],
    )
    assert result.exit_code == EXIT_FINDINGS
    payload = json.loads(result.stdout)
    rule_ids = {f["rule_id"] for f in payload["findings"]}
    assert not any(r.startswith("XSD-") for r in rule_ids)  # schema layer is clean
    assert "CBPR-ADDR-001" in rule_ids  # the guideline layer is not


def test_main_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["cbpr-validate", "version"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == EXIT_OK
