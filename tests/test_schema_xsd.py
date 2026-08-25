"""Phase 5 - the optional XSD layer.

This project never ships or commits SWIFT schemas, so these tests generate a
minimal schema for the pacs.008 namespace at run time. That is enough to prove
the layer loads a schema, finds it by message family, reports violations as
Findings, and fails loudly when it has nothing to validate against.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cbpr_validate.config import ENV_XSD_DIR, Settings, get_settings
from cbpr_validate.model.finding import Severity
from cbpr_validate.schema.xsd import (
    XsdUnavailableError,
    find_schema,
    validate_against_xsd,
)
from tests.conftest import PACS008_CLEAN

PACS008_NS = "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"

# Accepts a <Document> with any children; rejects any other root element.
PERMISSIVE_XSD = f"""<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="{PACS008_NS}"
           elementFormDefault="qualified">
  <xs:element name="Document">
    <xs:complexType>
      <xs:sequence>
        <xs:any processContents="skip" minOccurs="0" maxOccurs="unbounded"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""

STRICT_XSD = f"""<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="{PACS008_NS}"
           elementFormDefault="qualified">
  <xs:element name="SomethingElse" type="xs:string"/>
</xs:schema>
"""


@pytest.fixture
def xsd_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "schemas"
    directory.mkdir()
    (directory / "pacs.008.001.08.xsd").write_text(PERMISSIVE_XSD, encoding="utf-8")
    return directory


# --- config ----------------------------------------------------------------


def test_settings_read_the_env_var() -> None:
    assert Settings.from_env({ENV_XSD_DIR: "/schemas"}).xsd_dir == Path("/schemas")
    assert Settings.from_env({}).xsd_dir is None


def test_get_settings_reads_the_process_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_XSD_DIR, "/from/env")
    assert get_settings().xsd_dir == Path("/from/env")


# --- schema discovery ------------------------------------------------------


def test_find_schema_matches_by_message_family(xsd_dir: Path) -> None:
    assert find_schema("pacs.008", xsd_dir) == xsd_dir / "pacs.008.001.08.xsd"


def test_find_schema_prefers_the_highest_sorting_version(xsd_dir: Path) -> None:
    newer = xsd_dir / "pacs.008.001.12.xsd"
    newer.write_text(PERMISSIVE_XSD, encoding="utf-8")
    assert find_schema("pacs.008", xsd_dir) == newer


def test_find_schema_returns_none_for_an_unknown_family(xsd_dir: Path) -> None:
    assert find_schema("pacs.009", xsd_dir) is None
    assert find_schema(None, xsd_dir) is None


# --- validation ------------------------------------------------------------


def test_valid_document_produces_no_findings(xsd_dir: Path) -> None:
    assert validate_against_xsd(PACS008_CLEAN, "pacs.008", xsd_dir=xsd_dir) == []


def test_schema_violations_become_error_findings(tmp_path: Path) -> None:
    directory = tmp_path / "strict"
    directory.mkdir()
    (directory / "pacs.008.001.08.xsd").write_text(STRICT_XSD, encoding="utf-8")
    findings = validate_against_xsd(PACS008_CLEAN, "pacs.008", xsd_dir=directory)
    assert findings
    assert all(f.severity is Severity.ERROR for f in findings)
    assert all(f.rule_id == "XSD-001" for f in findings)
    assert findings[0].spec_reference is not None
    assert "pacs.008.001.08.xsd" in findings[0].spec_reference


def test_malformed_xml_is_reported_not_raised(xsd_dir: Path) -> None:
    findings = validate_against_xsd(b"<Document><unclosed>", "pacs.008", xsd_dir=xsd_dir)
    assert [f.rule_id for f in findings] == ["XSD-000"]


def test_explicit_xsd_path_bypasses_discovery(xsd_dir: Path) -> None:
    path = xsd_dir / "pacs.008.001.08.xsd"
    assert validate_against_xsd(PACS008_CLEAN, "pacs.999", xsd_path=path) == []


def test_falls_back_to_the_configured_directory(
    xsd_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_XSD_DIR, str(xsd_dir))
    assert validate_against_xsd(PACS008_CLEAN, "pacs.008") == []


# --- failing loudly rather than silently passing ---------------------------


def test_unconfigured_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_XSD_DIR, raising=False)
    with pytest.raises(XsdUnavailableError, match="no schema directory is configured"):
        validate_against_xsd(PACS008_CLEAN, "pacs.008")


def test_missing_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(XsdUnavailableError, match="does not exist"):
        validate_against_xsd(PACS008_CLEAN, "pacs.008", xsd_dir=tmp_path / "absent")


def test_no_matching_schema_raises(xsd_dir: Path) -> None:
    with pytest.raises(XsdUnavailableError, match="No schema matching"):
        validate_against_xsd(PACS008_CLEAN, "pacs.004", xsd_dir=xsd_dir)


def test_unloadable_schema_raises(tmp_path: Path) -> None:
    directory = tmp_path / "broken"
    directory.mkdir()
    (directory / "pacs.008.001.08.xsd").write_text("not a schema", encoding="utf-8")
    with pytest.raises(XsdUnavailableError, match="Could not load schema"):
        validate_against_xsd(PACS008_CLEAN, "pacs.008", xsd_dir=directory)
