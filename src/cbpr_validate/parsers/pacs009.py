"""Parser for pacs.009 FinancialInstitutionCreditTransfer (core + COV).

Both the core financial-institution credit transfer and the COV variant share
the pacs.009 namespace and root element (``FICdtTrf``). The COV variant is
distinguished structurally by the presence of an embedded
``UndrlygCstmrCdtTrf`` (the underlying customer credit transfer being covered).

We capture that embedded transaction as a nested :class:`Payment` so that the
COV agent rule (``CBPR-AGT-002``) and later cross-message correlation can reach
its parties, agents and UETR.
"""

from __future__ import annotations

from lxml import etree

from cbpr_validate.model.payment import Payment
from cbpr_validate.parsers._common import (
    find_text,
    parse_agent,
    parse_amount,
    parse_party,
)


def _parse_underlying(tx: etree._Element) -> Payment | None:
    node = tx.find(".//{*}UndrlygCstmrCdtTrf")
    if node is None:
        return None
    return Payment(
        message_type="pacs.008",  # the underlying is a customer credit transfer
        uetr=find_text(node, ".//{*}PmtId/{*}UETR"),
        instr_id=find_text(node, ".//{*}PmtId/{*}InstrId"),
        tx_id=find_text(node, ".//{*}PmtId/{*}TxId"),
        end_to_end_id=find_text(node, ".//{*}PmtId/{*}EndToEndId"),
        amount=parse_amount(node.find(".//{*}InstdAmt"))
        or parse_amount(node.find(".//{*}IntrBkSttlmAmt")),
        interbank_settlement_amount=parse_amount(node.find(".//{*}IntrBkSttlmAmt")),
        dbtr=parse_party(node.find("{*}Dbtr")),
        cdtr=parse_party(node.find("{*}Cdtr")),
        dbtr_agt=parse_agent(node, "DbtrAgt"),
        cdtr_agt=parse_agent(node, "CdtrAgt"),
        intrmy_agt1=parse_agent(node, "IntrmyAgt1"),
        intrmy_agt2=parse_agent(node, "IntrmyAgt2"),
    )


def parse_pacs009(xml_bytes: bytes) -> Payment:
    root = etree.fromstring(xml_bytes)

    tx = root.find(".//{*}CdtTrfTxInf")
    base = tx if tx is not None else root
    # InstgAgt/InstdAgt live at the group-header level in pacs.009.
    grp = root.find(".//{*}GrpHdr")

    return Payment(
        message_type="pacs.009",
        uetr=find_text(base, ".//{*}PmtId/{*}UETR"),
        msg_id=find_text(grp, "{*}MsgId"),
        instr_id=find_text(base, ".//{*}PmtId/{*}InstrId"),
        tx_id=find_text(base, ".//{*}PmtId/{*}TxId"),
        end_to_end_id=find_text(base, ".//{*}PmtId/{*}EndToEndId"),
        amount=parse_amount(base.find(".//{*}IntrBkSttlmAmt")),
        interbank_settlement_amount=parse_amount(base.find(".//{*}IntrBkSttlmAmt")),
        dbtr=parse_party(base.find("{*}Dbtr")),
        cdtr=parse_party(base.find("{*}Cdtr")),
        dbtr_agt=parse_agent(base, "DbtrAgt"),
        cdtr_agt=parse_agent(base, "CdtrAgt"),
        instg_agt=parse_agent(base, "InstgAgt") or parse_agent(grp, "InstgAgt"),
        instd_agt=parse_agent(base, "InstdAgt") or parse_agent(grp, "InstdAgt"),
        intrmy_agt1=parse_agent(base, "IntrmyAgt1"),
        intrmy_agt2=parse_agent(base, "IntrmyAgt2"),
        instg_rmbrsmnt_agt=parse_agent(base, "InstgRmbrsmntAgt"),
        instd_rmbrsmnt_agt=parse_agent(base, "InstdRmbrsmntAgt"),
        thrd_rmbrsmnt_agt=parse_agent(base, "ThrdRmbrsmntAgt"),
        underlying=_parse_underlying(base) if tx is not None else None,
    )


def is_cov(payment: Payment) -> bool:
    """A parsed pacs.009 is a COV iff it carries an underlying customer transfer."""
    return payment.message_type == "pacs.009" and payment.underlying is not None
