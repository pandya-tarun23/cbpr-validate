"""Guard-branch coverage for the Phase 4 parser helpers and detection."""

from lxml import etree

from cbpr_validate.parsers._common import (
    find_text,
    parse_address,
    parse_agent,
    parse_amount,
    parse_party,
)
from cbpr_validate.parsers.detect import detect_message_type


def test_common_helpers_handle_none_and_empty() -> None:
    assert parse_amount(None) is None
    assert find_text(None, "{*}X") is None
    assert parse_address(None) is None
    assert parse_party(None) is None
    assert parse_agent(None, "DbtrAgt") is None

    # amount with no currency attribute -> None
    amt = etree.fromstring(b"<InstdAmt>10.00</InstdAmt>")
    assert parse_amount(amt) is None

    # amount with non-numeric text -> None
    bad = etree.fromstring(b'<InstdAmt Ccy="USD">not-a-number</InstdAmt>')
    assert parse_amount(bad) is None

    # empty party / agent -> None
    empty_party = etree.fromstring(b"<Dbtr></Dbtr>")
    assert parse_party(empty_party) is None
    empty_agent_parent = etree.fromstring(b"<Wrap><DbtrAgt></DbtrAgt></Wrap>")
    assert parse_agent(empty_agent_parent, "DbtrAgt") is None


def test_detect_handles_malformed_xml() -> None:
    assert detect_message_type(b"<not-valid-xml") is None


def test_detect_scans_child_namespaces() -> None:
    # Root is a neutral envelope; the pacs.004 namespace only appears on a child.
    envelope = (
        b'<Envelope xmlns="urn:example:envelope">'
        b'<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.004.001.09"/>'
        b"</Envelope>"
    )
    assert detect_message_type(envelope) == "pacs.004"


def test_detect_unknown_child_returns_none() -> None:
    envelope = (
        b'<Envelope xmlns="urn:example:envelope">'
        b'<Inner xmlns="urn:example:inner"/>'
        b"</Envelope>"
    )
    assert detect_message_type(envelope) is None
