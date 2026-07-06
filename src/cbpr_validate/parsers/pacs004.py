"""Parser for pacs.004 PaymentReturn.

Extracts the return-reason code, the six mandatory original-reference fields,
the returned interbank settlement amount, any ChrgsInf breakdown, and
compensation/interest amounts, into the version-agnostic :class:`Payment`.
"""

from __future__ import annotations

from lxml import etree

from cbpr_validate.model.payment import ChargeInfo, Payment
from cbpr_validate.parsers._common import find_text, parse_agent, parse_amount


def _parse_charges(tx: etree._Element) -> list[ChargeInfo] | None:
    charges: list[ChargeInfo] = []
    for node in tx.findall(".//{*}ChrgsInf"):
        amount = parse_amount(node.find("{*}Amt"))
        agent = parse_agent(node, "Agt")
        if amount is not None or agent is not None:
            charges.append(ChargeInfo(amount=amount, agent=agent))
    return charges or None


def parse_pacs004(xml_bytes: bytes) -> Payment:
    root = etree.fromstring(xml_bytes)

    tx = root.find(".//{*}TxInf")
    base = tx if tx is not None else root
    grp = root.find(".//{*}OrgnlGrpInf")

    orgnl_msg_id = find_text(base, ".//{*}OrgnlMsgId") or find_text(grp, ".//{*}OrgnlMsgId")

    return Payment(
        message_type="pacs.004",
        uetr=find_text(base, ".//{*}OrgnlUETR"),
        return_reason=find_text(base, ".//{*}RtrRsnInf/{*}Rsn/{*}Cd"),
        orgnl_msg_id=orgnl_msg_id,
        orgnl_end_to_end_id=find_text(base, ".//{*}OrgnlEndToEndId"),
        orgnl_tx_id=find_text(base, ".//{*}OrgnlTxId"),
        orgnl_uetr=find_text(base, ".//{*}OrgnlUETR"),
        orgnl_interbank_settlement_amount=parse_amount(
            base.find(".//{*}OrgnlIntrBkSttlmAmt")
        ),
        orgnl_interbank_settlement_date=find_text(base, ".//{*}OrgnlIntrBkSttlmDt"),
        returned_interbank_settlement_amount=parse_amount(
            base.find(".//{*}RtrdIntrBkSttlmAmt")
        ),
        charges=_parse_charges(base),
        compensation_amount=parse_amount(base.find(".//{*}CompstnAmt")),
    )
