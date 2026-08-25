"""Optional XSD structural validation.

This layer is deliberately optional and deliberately empty by default. The whole
premise of the project is that **XSD-valid is not CBPR+-compliant** - the schema
is the floor, the usage guidelines are the bar. It is offered so a user can run
both layers in one pass.

No SWIFT schema is shipped with this package. The user points
``CBPR_VALIDATE_XSD_DIR`` at their own licensed copy of the ISO 20022 message
definitions; schema files are matched by message family (``pacs.008*.xsd``).
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from cbpr_validate.config import ENV_XSD_DIR, get_settings
from cbpr_validate.model.finding import Finding, Severity

_SPEC = "ISO 20022 message definition (XSD) - user-supplied, not redistributed"


class XsdUnavailableError(RuntimeError):
    """XSD validation was requested but no usable schema could be located."""


def find_schema(message_type: str | None, xsd_dir: Path) -> Path | None:
    """Locate a schema file for a message family in ``xsd_dir``.

    Matches on family (e.g. ``pacs.008``) because that is all the detector knows
    from the namespace. When a directory holds several versions of the same
    family the highest-sorting filename wins - a stable, documented choice, not
    a claim about which version the message actually is. Callers who care pass
    an explicit ``xsd_path``.
    """
    if message_type is None:
        return None
    matches = sorted(p for p in xsd_dir.glob(f"{message_type}*.xsd") if p.is_file())
    return matches[-1] if matches else None


def validate_against_xsd(
    xml_bytes: bytes,
    message_type: str | None,
    xsd_dir: Path | None = None,
    xsd_path: Path | None = None,
) -> list[Finding]:
    """Validate a document against its XSD, returning schema violations as Findings.

    Raises :class:`XsdUnavailableError` if no schema can be located - the caller
    asked for this layer, so silently returning "clean" would be a lie.
    """
    if xsd_path is None:
        directory = xsd_dir if xsd_dir is not None else get_settings().xsd_dir
        if directory is None:
            raise XsdUnavailableError(
                "XSD validation was requested but no schema directory is configured. "
                f"Set {ENV_XSD_DIR} (or pass --xsd-dir) to your own licensed copy of "
                "the ISO 20022 message definitions; none are shipped with this package."
            )
        if not directory.is_dir():
            raise XsdUnavailableError(f"XSD directory does not exist: {directory}")
        found = find_schema(message_type, directory)
        if found is None:
            raise XsdUnavailableError(
                f"No schema matching '{message_type}*.xsd' was found in {directory}"
            )
        xsd_path = found

    try:
        schema = etree.XMLSchema(etree.parse(str(xsd_path)))
    except etree.LxmlError as exc:
        raise XsdUnavailableError(f"Could not load schema {xsd_path}: {exc}") from exc

    try:
        document = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        return [
            Finding(
                rule_id="XSD-000",
                severity=Severity.ERROR,
                message=f"Document is not well-formed XML: {exc}",
                location=None,
                remediation="Fix the XML syntax before validating",
                spec_reference=_SPEC,
            )
        ]

    if schema.validate(document):
        return []

    return [
        Finding(
            rule_id="XSD-001",
            severity=Severity.ERROR,
            message=str(error.message),
            location=f"line {error.line}" if error.line and error.line > 0 else None,
            remediation="Correct the document so it conforms to the message definition",
            spec_reference=f"{_SPEC}: {Path(str(xsd_path)).name}",
        )
        for error in schema.error_log
    ]
