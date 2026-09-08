"""Shared XML-extraction helpers for the Phase 4 parsers.

Kept separate from ``pacs008.py`` so the Phase 0-3 parser stays untouched.
All helpers are namespace-agnostic (``{*}``) so they work across the
pacs.008/009/002/004 message families without hard-coding a version.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from lxml import etree

from cbpr_validate.model.payment import Agent, Amount, Party, PostalAddress


def text(node: etree._Element | None) -> str | None:
    if node is None:
        return None
    return node.text.strip() if node.text else None


def find_text(node: etree._Element | None, path: str) -> str | None:
    if node is None:
        return None
    return text(node.find(path))


def parse_amount(node: etree._Element | None) -> Amount | None:
    """Parse an ISO amount element (value text + ``Ccy`` attribute)."""
    if node is None or not node.text:
        return None
    currency = node.get("Ccy")
    if not currency:
        return None
    try:
        value = Decimal(node.text.strip())
    except (InvalidOperation, ValueError):
        return None
    return Amount(value=value, currency=currency)


def parse_address(party_node: etree._Element | None) -> PostalAddress | None:
    if party_node is None:
        return None
    addr = party_node.find(".//{*}PstlAdr")
    if addr is None:
        return None
    adr_lines = [
        line for line in (text(n) for n in addr.findall("{*}AdrLine")) if line is not None
    ]
    twn = find_text(addr, "{*}TwnNm")
    ctry = find_text(addr, "{*}Ctry")
    return PostalAddress(adr_line=adr_lines or None, twn_nm=twn, ctry=ctry)


def parse_party(party_node: etree._Element | None) -> Party | None:
    """Parse a party (customer or financial institution).

    Reads ``Nm`` and ``LEI`` from either the party element directly or from a
    nested ``FinInstnId`` (financial-institution parties in pacs.009).
    """
    if party_node is None:
        return None
    name = find_text(party_node, "{*}Nm") or find_text(party_node, ".//{*}FinInstnId/{*}Nm")
    lei = find_text(party_node, ".//{*}LEI")
    address = parse_address(party_node)
    if name is None and lei is None and address is None:
        return None
    return Party(name=name, postal_address=address, lei=lei)


def parse_agent_element(node: etree._Element | None) -> Agent | None:
    """Parse an agent from its own element, wherever it was found.

    Reads ``BICFI`` first and falls back to the legacy ``BIC``. Real CBPR+
    pacs.008 traffic carries ``BICFI``: a parser that only looks for ``BIC``
    silently yields no agent, which makes every agent rule a no-op instead of a
    failure - a false negative, and harder to notice than a false positive.
    """
    if node is None:
        return None
    fin = node.find(".//{*}FinInstnId")
    scope = fin if fin is not None else node
    bic = find_text(scope, "{*}BICFI") or find_text(scope, "{*}BIC")
    lei = find_text(scope, "{*}LEI")
    name = find_text(scope, "{*}Nm")
    if bic is None and lei is None and name is None:
        return None
    return Agent(bic=bic, name=name, lei=lei)


def parse_agent(parent: etree._Element | None, tag: str) -> Agent | None:
    """Parse a financial-institution agent found at ``parent/<tag>``."""
    if parent is None:
        return None
    return parse_agent_element(parent.find(f"{{*}}{tag}"))
