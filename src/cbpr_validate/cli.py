"""Typer CLI: ``cbpr-validate check`` and ``cbpr-validate match``.

The CLI is a thin shell. Parsing, rule execution, correlation and formatting all
live in the library, so the CLI and the API cannot drift apart in what they
report - only in how they are invoked.

Exit codes (stable, so this is usable as a CI gate):

* ``0`` - clean, or findings below the ``--fail-on`` threshold
* ``1`` - findings at or above the threshold / the two messages do not correlate
* ``2`` - the input could not be used (unreadable, unparseable, no XSD, bad pair)
"""

from __future__ import annotations

import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from cbpr_validate.match.matcher import UnsupportedPairError, correlate
from cbpr_validate.match.result import Direction
from cbpr_validate.model.payment import Payment
from cbpr_validate.model.validation_result import ValidationResult
from cbpr_validate.parsers.detect import detect_message_type
from cbpr_validate.parsers.parse import UnsupportedMessageTypeError, parse_message
from cbpr_validate.report.json_report import match_to_json, validation_to_json
from cbpr_validate.report.junit_report import match_to_junit, validation_to_junit
from cbpr_validate.report.text_report import match_to_text, validation_to_text
from cbpr_validate.rules.registry import run_all
from cbpr_validate.schema.xsd import XsdUnavailableError, validate_against_xsd

app = typer.Typer(
    help="cbpr-validate: ISO 20022 CBPR+ usage-guideline validator",
    no_args_is_help=True,
)

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_INPUT_ERROR = 2


class OutputFormat(StrEnum):
    TEXT = "text"
    JSON = "json"
    JUNIT = "junit"


class FailOn(StrEnum):
    ERROR = "error"
    WARN = "warn"
    NEVER = "never"


MessageArgument = Annotated[
    Path,
    typer.Argument(
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to an ISO 20022 message (XML).",
    ),
]
FormatOption = Annotated[
    OutputFormat, typer.Option("--format", "-f", help="Output format.")
]


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:  # pragma: no cover - argument callback catches most cases
        typer.echo(f"error: could not read {path}: {exc}", err=True)
        raise typer.Exit(EXIT_INPUT_ERROR) from exc


def _parse(path: Path) -> Payment:
    try:
        return parse_message(_read(path))
    except UnsupportedMessageTypeError as exc:
        typer.echo(f"error: {path}: {exc}", err=True)
        raise typer.Exit(EXIT_INPUT_ERROR) from exc


def _should_fail(result: ValidationResult, fail_on: FailOn) -> bool:
    if fail_on is FailOn.NEVER:
        return False
    if fail_on is FailOn.WARN:
        return bool(result.errors or result.warnings)
    return bool(result.errors)


@app.command()
def check(
    message: MessageArgument,
    output_format: FormatOption = OutputFormat.TEXT,
    xsd: Annotated[
        bool,
        typer.Option(
            "--xsd/--no-xsd",
            help="Also run the optional XSD structural layer (requires your own schemas).",
        ),
    ] = False,
    xsd_dir: Annotated[
        Path | None,
        typer.Option(
            "--xsd-dir",
            help="Directory holding your licensed ISO 20022 schemas. "
            "Defaults to $CBPR_VALIDATE_XSD_DIR.",
        ),
    ] = None,
    fail_on: Annotated[
        FailOn, typer.Option("--fail-on", help="Severity that makes this command exit 1.")
    ] = FailOn.ERROR,
) -> None:
    """Validate one message against the CBPR+ usage guidelines."""
    raw = _read(message)
    payment = _parse(message)
    result = run_all(payment)

    if xsd:
        try:
            result.findings.extend(
                validate_against_xsd(raw, detect_message_type(raw), xsd_dir=xsd_dir)
            )
        except XsdUnavailableError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(EXIT_INPUT_ERROR) from exc

    source = message.name
    if output_format is OutputFormat.JSON:
        typer.echo(validation_to_json(result))
    elif output_format is OutputFormat.JUNIT:
        typer.echo(validation_to_junit(result, source=source))
    else:
        typer.echo(validation_to_text(result, source=source))

    raise typer.Exit(EXIT_FINDINGS if _should_fail(result, fail_on) else EXIT_OK)


@app.command()
def match(
    message_a: MessageArgument,
    message_b: MessageArgument,
    direction: Annotated[
        Direction | None,
        typer.Option(
            "--direction",
            help="Required for pacs.002 <-> pacs.008: whether YOU sent the pacs.008 "
            "(outbound) or received it (inbound). Never inferred from BICs.",
        ),
    ] = None,
    output_format: FormatOption = OutputFormat.TEXT,
) -> None:
    """Correlate two related messages (COV<->008, 002<->008, 004<->008)."""
    a = _parse(message_a)
    b = _parse(message_b)

    try:
        result = correlate(a, b, direction)
    except (UnsupportedPairError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(EXIT_INPUT_ERROR) from exc

    if output_format is OutputFormat.JSON:
        typer.echo(match_to_json(result))
    elif output_format is OutputFormat.JUNIT:
        typer.echo(match_to_junit(result))
    else:
        typer.echo(match_to_text(result))

    raise typer.Exit(EXIT_OK if result.is_consistent else EXIT_FINDINGS)


@app.command()
def version() -> None:
    """Print the installed version."""
    from cbpr_validate import __version__

    typer.echo(__version__)


def main() -> None:
    # Findings quote message content verbatim, and a real payment can carry
    # characters the console encoding cannot represent (a non-Latin party name,
    # say). Degrade those to a placeholder rather than dying with
    # UnicodeEncodeError halfway through a report.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")
    app()


if __name__ == "__main__":  # pragma: no cover - console-script entry point
    main()
