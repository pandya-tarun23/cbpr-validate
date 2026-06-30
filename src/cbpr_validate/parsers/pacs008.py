from __future__ import annotations

from decimal import Decimal
from typing import Optional

from lxml import etree

from cbpr_validate.model.payment import Amount, Agent, Party, Payment, PostalAddress


NSMAP = {None: "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"}


def _text(node: Optional[etree._Element]) -> Optional[str]:
    if node is None:
        return None
    return node.text.strip() if node.text else None


def parse_pacs008(xml_bytes: bytes) -> Payment:
    root = etree.fromstring(xml_bytes)

    # find UETR anywhere under PmtId
    uetr = None
    uetr_node = root.find('.//{*}PmtId/{*}UETR')
    if uetr_node is None:
        # sometimes UETR is directly under Document -> PmtId
        uetr_node = root.find('.//{*}UETR')
    if uetr_node is not None:
        uetr = _text(uetr_node)

    # amount
    instd = root.find('.//{*}InstdAmt')
    amount = None
    if instd is not None and instd.text:
        currency = instd.get('Ccy') or instd.get('Ccy')
        try:
            value = Decimal(instd.text.strip())
        except Exception:
            value = Decimal('0')
        amount = Amount(value=value, currency=currency)

    # debtor/creditor
    dbtr_nm = _text(root.find('.//{*}Dbtr/{*}Nm'))
    cdtr_nm = _text(root.find('.//{*}Cdtr/{*}Nm'))

    # postal addresses
    def _parse_address(parent_tag: str) -> Optional[PostalAddress]:
        addr = root.find(f'.//{{*}}{parent_tag}/{{*}}PstlAdr')
        if addr is None:
            return None
        adr_lines = [_text(n) for n in addr.findall('{*}AdrLine') if _text(n)]
        twn = _text(addr.find('{*}TwnNm'))
        ctry = _text(addr.find('{*}Ctry'))
        return PostalAddress(adr_line=adr_lines or None, twn_nm=twn, ctry=ctry)

    dbtr = Party(name=dbtr_nm, postal_address=_parse_address('Dbtr'))
    cdtr = Party(name=cdtr_nm, postal_address=_parse_address('Cdtr'))

    # agents/BICs
    def _parse_agent(tag: str) -> Optional[Agent]:
        bic = _text(root.find(f'.//{{*}}{tag}/{{*}}FinInstnId/{{*}}BIC'))
        if bic:
            return Agent(bic=bic)
        return None

    dbtr_agt = _parse_agent('DbtrAgt')
    cdtr_agt = _parse_agent('CdtrAgt')

    payment = Payment(
        uetr=uetr,
        amount=amount,
        dbtr=dbtr,
        cdtr=cdtr,
        dbtr_agt=dbtr_agt,
        cdtr_agt=cdtr_agt,
    )

    return payment
