"""Severity profiles: the same message judged against two rulebooks.

SWIFT deferred the SR2026 payments changes, so an unstructured postal address
is a readiness gap today and a rejection later. These tests pin both answers,
and pin that nothing *else* moves between the two profiles.

Each rule-affecting case has both a passing and an adversarial assertion
(CLAUDE.md rule 2): the clean message must stay compliant under the strict
profile, and the unstructured one must flip.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from cbpr_validate import validate_bytes, validate_file, validate_string
from cbpr_validate.api.main import app as api_app
from cbpr_validate.cli import EXIT_FINDINGS, EXIT_INPUT_ERROR, EXIT_OK
from cbpr_validate.cli import app as cli_app
from cbpr_validate.model.finding import Severity
from cbpr_validate.parsers.parse import parse_message
from cbpr_validate.profiles import (
    DEFAULT_PROFILE,
    PROFILE_OVERRIDES,
    Profile,
    apply_profile,
    resolve_profile,
)
from cbpr_validate.report.json_report import validation_to_json
from cbpr_validate.report.junit_report import validation_to_junit
from cbpr_validate.report.text_report import validation_to_text
from cbpr_validate.rules.registry import run_all
from tests.conftest import PACS008_CLEAN, PACS008_UNSTRUCTURED

runner = CliRunner()
client = TestClient(api_app)

#: Structured town+country *plus* an AdrLine. Allowed under both rulebooks, so
#: it must look identical in each - this is the fixture that would catch an
#: override accidentally keyed on "has an AdrLine at all".
PACS008_HYBRID = PACS008_CLEAN.replace(
    b"<PstlAdr><TwnNm>London</TwnNm><Ctry>GB</Ctry></PstlAdr>",
    b"<PstlAdr><AdrLine>221B Baker Street</AdrLine>"
    b"<TwnNm>London</TwnNm><Ctry>GB</Ctry></PstlAdr>",
)

#: An invalid ISO 3166 country. Trips CBPR-ADDR-004, which no profile mentions,
#: so its severity must be ERROR under both.
PACS008_BAD_COUNTRY = PACS008_CLEAN.replace(b"<Ctry>GB</Ctry>", b"<Ctry>XX</Ctry>")

ADDRESS_GAP_RULES = ("CBPR-ADDR-001", "CBPR-ADDR-002")


def _severities(message: bytes, profile: str | None = None) -> dict[str, Severity]:
    """rule_id -> severity for one message under one profile."""
    result = (
        run_all(parse_message(message), profile=profile)
        if profile
        else run_all(parse_message(message))
    )
    return {f.rule_id: f.severity for f in result.findings}


# --- the headline behaviour change ------------------------------------------


def test_current_reports_address_gaps_as_warnings_and_stays_compliant() -> None:
    result = validate_bytes(PACS008_UNSTRUCTURED, "current")
    by_id = {f.rule_id: f for f in result.findings}
    for rule_id in ADDRESS_GAP_RULES:
        assert by_id[rule_id].severity is Severity.WARN
        # the strict reading is still recoverable from the finding
        assert by_id[rule_id].base_severity is Severity.ERROR
        assert by_id[rule_id].was_overridden
    assert result.is_compliant
    assert len(result.overridden) == len(ADDRESS_GAP_RULES)


def test_sr2026_reports_address_gaps_as_errors_and_is_not_compliant() -> None:
    result = validate_bytes(PACS008_UNSTRUCTURED, "sr2026")
    by_id = {f.rule_id: f for f in result.findings}
    for rule_id in ADDRESS_GAP_RULES:
        assert by_id[rule_id].severity is Severity.ERROR
        # sr2026 restates the rule's own severity, so nothing was overridden
        assert by_id[rule_id].base_severity is Severity.ERROR
        assert not by_id[rule_id].was_overridden
    assert not result.is_compliant
    assert result.overridden == []


def test_the_default_profile_is_current() -> None:
    assert DEFAULT_PROFILE is Profile.CURRENT
    # ...and an omitted argument really does take that path, rather than
    # happening to agree with it.
    assert validate_bytes(PACS008_UNSTRUCTURED).profile is Profile.CURRENT
    assert validate_bytes(PACS008_UNSTRUCTURED).is_compliant
    assert run_all(parse_message(PACS008_UNSTRUCTURED)).profile is Profile.CURRENT


# --- nothing else moves between profiles ------------------------------------


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("structured", PACS008_CLEAN),
        ("hybrid", PACS008_HYBRID),
        ("bad_country", PACS008_BAD_COUNTRY),
    ],
)
def test_messages_without_address_gaps_are_identical_under_both_profiles(
    name: str, message: bytes
) -> None:
    assert _severities(message, "current") == _severities(message, "sr2026")


def test_non_address_rules_keep_their_severity_under_both_profiles() -> None:
    """A profile must not disturb any rule it does not name."""
    current = _severities(PACS008_UNSTRUCTURED, "current")
    sr2026 = _severities(PACS008_UNSTRUCTURED, "sr2026")
    assert set(current) == set(sr2026)
    for rule_id in set(current) - set(ADDRESS_GAP_RULES):
        assert current[rule_id] is sr2026[rule_id], rule_id


def test_only_the_address_gap_rules_are_ever_overridden() -> None:
    """Guards the profile tables themselves: a stray rule_id added to an
    override map would silently change a verdict."""
    for profile, overrides in PROFILE_OVERRIDES.items():
        assert set(overrides) == set(ADDRESS_GAP_RULES), profile


def test_hybrid_address_is_compliant_under_the_strict_profile() -> None:
    """The passing half of the pair: structured data present alongside an
    AdrLine is fine even under sr2026."""
    assert validate_bytes(PACS008_HYBRID, "sr2026").is_compliant
    assert validate_bytes(PACS008_CLEAN, "sr2026").is_compliant


def test_addr_004_stays_an_error_under_current() -> None:
    """An invalid country code is wrong today, not merely wrong from SR2026."""
    result = validate_bytes(PACS008_BAD_COUNTRY, "current")
    by_id = {f.rule_id: f for f in result.findings}
    assert by_id["CBPR-ADDR-004"].severity is Severity.ERROR
    assert not result.is_compliant


# --- the profile layer itself -----------------------------------------------


def test_resolve_profile_accepts_enum_string_and_none() -> None:
    assert resolve_profile(None) is DEFAULT_PROFILE
    assert resolve_profile(Profile.SR2026) is Profile.SR2026
    assert resolve_profile("sr2026") is Profile.SR2026
    assert resolve_profile("  SR2026  ") is Profile.SR2026


def test_unknown_profile_raises_and_names_the_valid_ones() -> None:
    with pytest.raises(ValueError, match="unknown profile") as exc:
        resolve_profile("sr2027")
    assert "current" in str(exc.value)
    assert "sr2026" in str(exc.value)


def test_applying_a_profile_twice_changes_nothing_further() -> None:
    """apply_profile compares against base_severity, so it is idempotent - a
    finding cannot be downgraded twice or record a bogus override."""
    once = apply_profile(
        run_all(parse_message(PACS008_UNSTRUCTURED), profile="sr2026").findings,
        Profile.CURRENT,
    )
    twice = apply_profile(once, Profile.CURRENT)
    assert [(f.rule_id, f.severity, f.base_severity) for f in once] == [
        (f.rule_id, f.severity, f.base_severity) for f in twice
    ]


def test_base_severity_is_always_populated() -> None:
    """Never null, for any finding, under any profile - including the
    ORCH-* findings produced when no rule ever ran."""
    for profile in Profile:
        for message in (PACS008_CLEAN, PACS008_UNSTRUCTURED, b"", b"<nope/>"):
            for finding in validate_bytes(message, profile).findings:
                assert finding.base_severity is not None


# --- the library entry points -----------------------------------------------


def test_all_library_entry_points_accept_the_profile(tmp_path: Path) -> None:
    path = tmp_path / "m.xml"
    path.write_bytes(PACS008_UNSTRUCTURED)
    for profile, compliant in (("current", True), ("sr2026", False)):
        assert validate_bytes(PACS008_UNSTRUCTURED, profile).is_compliant is compliant
        assert (
            validate_string(PACS008_UNSTRUCTURED.decode(), profile).is_compliant
            is compliant
        )
        assert validate_file(path, profile).is_compliant is compliant


def test_unparseable_input_still_records_the_profile() -> None:
    result = validate_bytes(b"", "sr2026")
    assert result.profile is Profile.SR2026
    assert not result.is_compliant
    assert result.findings[0].rule_id == "ORCH-PARSE-ERROR"


def test_library_rejects_an_unknown_profile() -> None:
    calls: list[Callable[[], object]] = [
        lambda: validate_bytes(PACS008_CLEAN, "nope"),
        lambda: validate_string(PACS008_CLEAN.decode(), "nope"),
        lambda: run_all(parse_message(PACS008_CLEAN), profile="nope"),
    ]
    for call in calls:
        with pytest.raises(ValueError, match="unknown profile"):
            call()


# --- the CLI ----------------------------------------------------------------


@pytest.mark.parametrize("command", ["validate", "check"])
@pytest.mark.parametrize(
    ("profile", "exit_code"),
    [("current", EXIT_OK), ("sr2026", EXIT_FINDINGS)],
)
def test_cli_exit_code_follows_the_profile(
    command: str, profile: str, exit_code: int, tmp_path: Path
) -> None:
    """Default --fail-on error: a WARN gap does not break the build today."""
    path = tmp_path / "m.xml"
    path.write_bytes(PACS008_UNSTRUCTURED)
    result = runner.invoke(cli_app, [command, str(path), "--profile", profile])
    assert result.exit_code == exit_code, result.stdout


@pytest.mark.parametrize("command", ["validate", "check"])
@pytest.mark.parametrize("fail_on", ["warn", "warning"])
def test_cli_fail_on_warn_gates_strictly_under_current(
    command: str, fail_on: str, tmp_path: Path
) -> None:
    """A CI team that wants to block on readiness gaps today still can - and
    both spellings of the threshold work on both commands."""
    path = tmp_path / "m.xml"
    path.write_bytes(PACS008_UNSTRUCTURED)
    result = runner.invoke(
        cli_app,
        [command, str(path), "--profile", "current", "--fail-on", fail_on],
    )
    assert result.exit_code == EXIT_FINDINGS, result.stdout


@pytest.mark.parametrize("command", ["validate", "check"])
def test_cli_rejects_an_unknown_profile_with_exit_two(
    command: str, tmp_path: Path
) -> None:
    path = tmp_path / "m.xml"
    path.write_bytes(PACS008_CLEAN)
    result = runner.invoke(cli_app, [command, str(path), "--profile", "sr2027"])
    assert result.exit_code == EXIT_INPUT_ERROR
    # the message has to say what the caller could have typed instead
    assert "current" in result.output
    assert "sr2026" in result.output


def test_cli_default_profile_is_current(tmp_path: Path) -> None:
    path = tmp_path / "m.xml"
    path.write_bytes(PACS008_UNSTRUCTURED)
    for args in (
        ["validate", str(path), "--json"],
        ["check", str(path), "--format", "json"],
    ):
        result = runner.invoke(cli_app, args)
        assert result.exit_code == EXIT_OK
        assert json.loads(result.stdout)["profile"] == "current"


def test_text_summary_makes_the_readiness_gap_obvious(tmp_path: Path) -> None:
    path = tmp_path / "m.xml"
    path.write_bytes(PACS008_UNSTRUCTURED)
    result = runner.invoke(cli_app, ["validate", str(path), "--profile", "current"])
    summary = result.stdout.strip().splitlines()[-1]
    assert summary == (
        "4 finding(s): 0 error, 2 warn, 2 info - COMPLIANT "
        "(profile: current) - 2 SR2026 address gaps"
    )
    # ASCII only: this gets printed to cp1252 consoles (CLAUDE.md).
    summary.encode("ascii")


def test_text_summary_omits_the_gap_note_when_there_is_no_gap(tmp_path: Path) -> None:
    path = tmp_path / "m.xml"
    path.write_bytes(PACS008_UNSTRUCTURED)
    result = runner.invoke(cli_app, ["validate", str(path), "--profile", "sr2026"])
    summary = result.stdout.strip().splitlines()[-1]
    assert "(profile: sr2026)" in summary
    assert "address gap" not in summary


# --- reporters --------------------------------------------------------------


@pytest.mark.parametrize("profile", ["current", "sr2026"])
def test_json_report_carries_the_profile_and_base_severity(profile: str) -> None:
    result = run_all(parse_message(PACS008_UNSTRUCTURED), profile=profile)
    payload = json.loads(validation_to_json(result))
    assert payload["profile"] == profile
    by_id = {f["rule_id"]: f for f in payload["findings"]}
    for rule_id in ADDRESS_GAP_RULES:
        assert by_id[rule_id]["base_severity"] == "ERROR"
        expected = "WARN" if profile == "current" else "ERROR"
        assert by_id[rule_id]["severity"] == expected


@pytest.mark.parametrize("profile", ["current", "sr2026"])
def test_junit_report_carries_the_profile_as_a_property(profile: str) -> None:
    result = run_all(parse_message(PACS008_UNSTRUCTURED), profile=profile)
    root = ET.fromstring(validation_to_junit(result, source="m.xml"))
    properties = root.findall(".//property")
    assert [(p.get("name"), p.get("value")) for p in properties] == [
        ("profile", profile)
    ]


def test_junit_only_fails_the_build_under_the_strict_profile() -> None:
    """WARN is a passing case, so a readiness gap does not break a pipeline
    until the team opts into sr2026."""
    parsed = parse_message(PACS008_UNSTRUCTURED)
    current = ET.fromstring(validation_to_junit(run_all(parsed, profile="current")))
    strict = ET.fromstring(validation_to_junit(run_all(parsed, profile="sr2026")))
    assert current.findall(".//failure") == []
    assert len(strict.findall(".//failure")) == len(ADDRESS_GAP_RULES)


@pytest.mark.parametrize("profile", ["current", "sr2026"])
def test_text_report_states_the_profile(profile: str) -> None:
    result = run_all(parse_message(PACS008_UNSTRUCTURED), profile=profile)
    text = validation_to_text(result, source="m.xml")
    assert f"(profile: {profile})" in text
    text.encode("ascii")


# --- the API ----------------------------------------------------------------


def _post(message: bytes, profile: str | None = None) -> Any:
    body: dict[str, Any] = {"message": message.decode()}
    if profile is not None:
        body["profile"] = profile
    return client.post("/validate", json=body)


@pytest.mark.parametrize(
    ("profile", "compliant"), [("current", True), ("sr2026", False)]
)
def test_api_honours_the_profile(profile: str, compliant: bool) -> None:
    response = _post(PACS008_UNSTRUCTURED, profile)
    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"] == profile
    assert payload["is_compliant"] is compliant


def test_api_defaults_to_current() -> None:
    payload = _post(PACS008_UNSTRUCTURED).json()
    assert payload["profile"] == "current"
    assert payload["is_compliant"] is True


def test_api_rejects_an_unknown_profile() -> None:
    response = _post(PACS008_CLEAN, "sr2027")
    assert 400 <= response.status_code < 500
    assert response.status_code == 422
