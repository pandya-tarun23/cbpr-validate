"""The library front door: one call from a file (or bytes, or a string) to a result.

Everything under this module already existed; what was missing was a single
entry point tying detection, parsing and rule execution together. Callers had to
know to do ``run_all(parse_message(data))`` and to catch
``UnsupportedMessageTypeError`` themselves.

The contract here is deliberately different from ``parsers.parse.parse_message``:
these functions **never raise** for bad input. A document that cannot be read,
parsed, or recognised comes back as a ``ValidationResult`` carrying a single
``ORCH-*`` ERROR finding, so a caller has exactly one shape to handle and
``is_compliant`` is false either way. Rule IDs are namespaced ``ORCH-`` rather
than ``CBPR-`` precisely so "we could not evaluate this" is never mistaken for
"this message breaks a usage guideline".
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.model.validation_result import ValidationResult
from cbpr_validate.parsers.detect import detect_message_type
from cbpr_validate.parsers.parse import SUPPORTED_MESSAGE_TYPES, parse_message
from cbpr_validate.rules.registry import run_all

RULE_PARSE_ERROR = "ORCH-PARSE-ERROR"
RULE_UNSUPPORTED = "ORCH-UNSUPPORTED"
RULE_READ_ERROR = "ORCH-READ-ERROR"

_SUPPORTED = ", ".join(SUPPORTED_MESSAGE_TYPES)


def _failure(rule_id: str, message: str, remediation: str) -> ValidationResult:
    """A result carrying one orchestration-level ERROR, so is_compliant is False."""
    return ValidationResult(
        findings=[
            Finding(
                rule_id=rule_id,
                severity=Severity.ERROR,
                message=message,
                location=None,
                remediation=remediation,
                spec_reference=None,
            )
        ]
    )


def _wellformed_error(data: bytes) -> str | None:
    """Return the syntax error if ``data`` is not well-formed XML, else None.

    ``detect_message_type`` collapses "malformed" and "unrecognised" into a
    single ``None``. We probe well-formedness separately so the caller is told
    which of the two actually happened - they need very different fixes.
    """
    try:
        etree.fromstring(data)
    except etree.XMLSyntaxError as exc:
        return str(exc)
    except ValueError as exc:  # e.g. an encoding declaration on a str input
        return str(exc)
    return None


def validate_bytes(data: bytes) -> ValidationResult:
    """Validate a message already in memory as bytes.

    This is the real implementation; the string and file entry points normalise
    their input and delegate here.
    """
    syntax_error = _wellformed_error(data)
    if syntax_error is not None:
        return _failure(
            RULE_PARSE_ERROR,
            f"Document is not well-formed XML: {syntax_error}",
            "Fix the XML syntax before validating",
        )

    message_type = detect_message_type(data)
    if message_type is None:
        return _failure(
            RULE_UNSUPPORTED,
            "The document is well-formed XML but carries no recognised ISO 20022 "
            f"message namespace. Supported: {_SUPPORTED}",
            f"Supply one of: {_SUPPORTED}",
        )

    try:
        payment = parse_message(data)
    except Exception as exc:
        # Well-formed and recognised, but the parser still could not build a
        # Payment (a required attribute missing, a value the model rejects).
        # That is a defect in the message, not a crash the caller should wear.
        return _failure(
            RULE_PARSE_ERROR,
            f"Recognised as {message_type} but could not be parsed: {exc}",
            "Check the message against the ISO 20022 message definition",
        )

    return run_all(payment)


def validate_string(xml: str) -> ValidationResult:
    """Validate a message held as text.

    The text is encoded as UTF-8 before parsing. lxml refuses a ``str`` that
    carries an encoding declaration, so going via bytes is what makes
    ``<?xml version="1.0" encoding="UTF-8"?>`` work here at all.
    """
    return validate_bytes(xml.encode("utf-8"))


def validate_file(path: str | Path) -> ValidationResult:
    """Validate a message on disk.

    An unreadable path comes back as an ``ORCH-READ-ERROR`` finding rather than
    an ``OSError``, keeping the no-raise contract. The ``ORCH-`` prefix is what
    distinguishes "I never got to look at a message" from "the message is
    non-compliant".
    """
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        return _failure(
            RULE_READ_ERROR,
            f"Could not read {path}: {exc}",
            "Check the path exists and is readable",
        )
    return validate_bytes(data)
