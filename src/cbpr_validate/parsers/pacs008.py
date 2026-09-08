from __future__ import annotations

from decimal import Decimal

from lxml import etree

from cbpr_validate.model.payment import (
    Agent,
    Amount,
    Party,
    Payment,
    PostalAddress,
)
from cbpr_validate.parsers._common import parse_agent_element

NSMAP = {None: "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"}


def _text(node: etree._Element | None) -> str | None:
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

    # interbank settlement amount - distinct from InstdAmt once charges apply,
    # and the amount cross-message correlation compares (Phase 4.5).
    sttlm = root.find('.//{*}IntrBkSttlmAmt')
    interbank_settlement_amount = None
    if sttlm is not None and sttlm.text and sttlm.get('Ccy'):
        try:
            interbank_settlement_amount = Amount(
                value=Decimal(sttlm.text.strip()), currency=sttlm.get('Ccy')
            )
        except Exception:
            interbank_settlement_amount = None

    # debtor/creditor
    dbtr_nm = _text(root.find('.//{*}Dbtr/{*}Nm'))
    cdtr_nm = _text(root.find('.//{*}Cdtr/{*}Nm'))

    # postal addresses
    def _parse_address(parent_tag: str) -> PostalAddress | None:
        addr = root.find(f'.//{{*}}{parent_tag}/{{*}}PstlAdr')
        if addr is None:
            return None
        adr_lines = [
            line
            for line in (_text(n) for n in addr.findall('{*}AdrLine'))
            if line is not None
        ]
        twn = _text(addr.find('{*}TwnNm'))
        ctry = _text(addr.find('{*}Ctry'))
        return PostalAddress(adr_line=adr_lines or None, twn_nm=twn, ctry=ctry)

    dbtr = Party(name=dbtr_nm, postal_address=_parse_address('Dbtr'))
    cdtr = Party(name=cdtr_nm, postal_address=_parse_address('Cdtr'))

    # Agents. This used to be a local BIC-only copy of the shared helper, so a
    # real CBPR+ message (which carries BICFI) produced no agent at all and
    # CBPR-STR-002 / CBPR-AGT-001 / CBPR-AGT-003 quietly never ran. Reuse the
    # shared extraction instead of keeping a second, weaker one in sync.
    def _parse_agent(tag: str) -> Agent | None:
        return parse_agent_element(root.find(f'.//{{*}}{tag}'))

    dbtr_agt = _parse_agent('DbtrAgt')
    cdtr_agt = _parse_agent('CdtrAgt')

    payment = Payment(
        # message_type identifies the message to the rule registry and to the
        # correlation engine; without it the pacs.008-specific rules never fire.
        message_type='pacs.008',
        uetr=uetr,
        msg_id=_text(root.find('.//{*}GrpHdr/{*}MsgId')),
        instr_id=_text(root.find('.//{*}PmtId/{*}InstrId')),
        tx_id=_text(root.find('.//{*}PmtId/{*}TxId')),
        end_to_end_id=_text(root.find('.//{*}PmtId/{*}EndToEndId')),
        amount=amount,
        interbank_settlement_amount=interbank_settlement_amount,
        dbtr=dbtr,
        cdtr=cdtr,
        dbtr_agt=dbtr_agt,
        cdtr_agt=cdtr_agt,
    )

    return payment
