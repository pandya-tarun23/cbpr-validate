"""Detect-and-dispatch entry point shared by every interface.

The library, the CLI and the API all go through :func:`parse_message`, so a
message parses to exactly the same :class:`Payment` regardless of how it was
submitted.
"""

from __future__ import annotations

from collections.abc import Callable

from cbpr_validate.model.payment import Payment
from cbpr_validate.parsers.detect import detect_message_type
from cbpr_validate.parsers.pacs002 import parse_pacs002
from cbpr_validate.parsers.pacs004 import parse_pacs004
from cbpr_validate.parsers.pacs008 import parse_pacs008
from cbpr_validate.parsers.pacs009 import parse_pacs009

_PARSERS: dict[str, Callable[[bytes], Payment]] = {
    "pacs.008": parse_pacs008,
    "pacs.009": parse_pacs009,
    "pacs.002": parse_pacs002,
    "pacs.004": parse_pacs004,
}

SUPPORTED_MESSAGE_TYPES = tuple(sorted(_PARSERS))


class UnsupportedMessageTypeError(ValueError):
    """The document is not one of the message types this version supports."""


def parse_message(xml_bytes: bytes) -> Payment:
    """Detect the message type and parse it into the internal model.

    Raises :class:`UnsupportedMessageTypeError` when the document is not
    well-formed XML, carries no recognisable ISO 20022 namespace, or is a
    message family outside v1's scope.
    """
    message_type = detect_message_type(xml_bytes)
    if message_type is None:
        raise UnsupportedMessageTypeError(
            "Could not determine the message type: the document is not well-formed "
            "XML or carries no recognised ISO 20022 namespace. Supported: "
            + ", ".join(SUPPORTED_MESSAGE_TYPES)
        )
    parser = _PARSERS.get(message_type)
    if parser is None:  # pragma: no cover - detect only returns known families
        raise UnsupportedMessageTypeError(f"Unsupported message type: {message_type}")
    return parser(xml_bytes)
