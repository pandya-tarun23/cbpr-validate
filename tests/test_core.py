"""The library front door (`cbpr_validate.core`).

The contract worth testing here is the one that differs from the rest of the
package: these functions never raise. Every way of handing in a bad document
comes back as a ValidationResult carrying one ORCH-* ERROR.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import cbpr_validate
from cbpr_validate import validate_bytes, validate_file, validate_string
from cbpr_validate.core import (
    RULE_PARSE_ERROR,
    RULE_READ_ERROR,
    RULE_UNSUPPORTED,
)
from cbpr_validate.model.finding import Severity
from cbpr_validate.model.validation_result import ValidationResult
from tests.conftest import (
    NOT_A_MESSAGE,
    PACS002,
    PACS004,
    PACS008_CLEAN,
    PACS008_UNSTRUCTURED,
    PACS009_COV,
)


def _rule_ids(result: ValidationResult) -> set[str]:
    return {f.rule_id for f in result.findings}


# --- the public API is importable as documented -----------------------------


def test_package_exports_the_front_door() -> None:
    assert cbpr_validate.__version__
    for name in ("validate_file", "validate_string", "validate_bytes"):
        assert name in cbpr_validate.__all__
        assert callable(getattr(cbpr_validate, name))


# --- the happy path ---------------------------------------------------------


def test_clean_message_is_compliant() -> None:
    result = validate_bytes(PACS008_CLEAN)
    assert result.is_compliant
    assert result.errors == []
    # INFO classifications are reporting, not defects
    assert all(f.severity is Severity.INFO for f in result.findings)


@pytest.mark.parametrize("message", [PACS008_CLEAN, PACS009_COV, PACS002, PACS004])
def test_every_supported_family_runs_the_rules(message: bytes) -> None:
    result = validate_bytes(message)
    assert not _rule_ids(result) & {RULE_PARSE_ERROR, RULE_UNSUPPORTED, RULE_READ_ERROR}


# --- the adversarial fixture (CLAUDE.md rule 2) -----------------------------


def test_unstructured_address_is_caught_with_the_right_rule_and_severity() -> None:
    result = validate_bytes(PACS008_UNSTRUCTURED)
    assert not result.is_compliant
    by_id = {f.rule_id: f for f in result.findings}
    assert by_id["CBPR-ADDR-001"].severity is Severity.ERROR
    assert by_id["CBPR-ADDR-002"].severity is Severity.ERROR
    assert by_id["CBPR-ADDR-001"].location == "Cdtr.PstlAdr"


# --- the three entry points agree -------------------------------------------


def test_bytes_string_and_file_agree(tmp_path: Path) -> None:
    path = tmp_path / "m.xml"
    path.write_bytes(PACS008_UNSTRUCTURED)
    from_bytes = validate_bytes(PACS008_UNSTRUCTURED)
    assert validate_string(PACS008_UNSTRUCTURED.decode()).model_dump() == from_bytes.model_dump()
    assert validate_file(path).model_dump() == from_bytes.model_dump()
    assert validate_file(str(path)).model_dump() == from_bytes.model_dump()


def test_validate_string_accepts_an_encoding_declaration() -> None:
    """lxml rejects a str carrying an encoding declaration; going via UTF-8
    bytes is what makes this work at all."""
    assert PACS008_CLEAN.decode().startswith("<?xml")
    assert validate_string(PACS008_CLEAN.decode()).is_compliant


# --- bad input never raises -------------------------------------------------


def test_malformed_xml_returns_a_parse_error_finding() -> None:
    result = validate_bytes(b"<Document><unclosed>")
    assert [f.rule_id for f in result.findings] == [RULE_PARSE_ERROR]
    assert result.findings[0].severity is Severity.ERROR
    assert not result.is_compliant


def test_empty_input_returns_a_parse_error_finding() -> None:
    assert [f.rule_id for f in validate_bytes(b"").findings] == [RULE_PARSE_ERROR]


def test_wellformed_but_unrecognised_returns_unsupported() -> None:
    result = validate_bytes(NOT_A_MESSAGE)
    assert [f.rule_id for f in result.findings] == [RULE_UNSUPPORTED]
    assert result.findings[0].severity is Severity.ERROR
    assert "pacs.008" in result.findings[0].message  # lists what IS supported


def test_unsupported_is_distinct_from_malformed() -> None:
    """detect_message_type collapses both into None; core must not."""
    assert _rule_ids(validate_bytes(b"<x")) != _rule_ids(validate_bytes(NOT_A_MESSAGE))


def test_recognised_but_unparseable_returns_a_parse_error() -> None:
    # Well-formed pacs.008, but InstdAmt has no Ccy so the model rejects it.
    broken = PACS008_CLEAN.replace(
        b'<InstdAmt Ccy="EUR">1000.00</InstdAmt>', b"<InstdAmt>1000.00</InstdAmt>"
    )
    result = validate_bytes(broken)
    assert [f.rule_id for f in result.findings] == [RULE_PARSE_ERROR]
    assert "Recognised as pacs.008" in result.findings[0].message


def test_missing_file_returns_a_read_error_finding(tmp_path: Path) -> None:
    result = validate_file(tmp_path / "absent.xml")
    assert [f.rule_id for f in result.findings] == [RULE_READ_ERROR]
    assert result.findings[0].severity is Severity.ERROR


def test_directory_instead_of_a_file_returns_a_read_error(tmp_path: Path) -> None:
    assert [f.rule_id for f in validate_file(tmp_path).findings] == [RULE_READ_ERROR]


def test_orchestration_findings_are_namespaced_apart_from_guideline_rules() -> None:
    """An ORCH-* id must never be mistaken for a CBPR+ usage-guideline breach."""
    for result in (
        validate_bytes(b"<x"),
        validate_bytes(NOT_A_MESSAGE),
        validate_file("nope.xml"),
    ):
        assert all(f.rule_id.startswith("ORCH-") for f in result.findings)
        assert not any(f.rule_id.startswith("CBPR-") for f in result.findings)


def test_never_raises_even_for_the_wrong_type() -> None:
    """The no-raise contract must not depend on the caller respecting the hint.

    lxml rejects a str carrying an encoding declaration with ValueError rather
    than XMLSyntaxError, so passing a str to validate_bytes is the one way to
    reach that branch.
    """
    result = validate_bytes(PACS008_CLEAN.decode())  # type: ignore[arg-type]
    assert [f.rule_id for f in result.findings] == [RULE_PARSE_ERROR]
    assert "encoding declaration" in result.findings[0].message
