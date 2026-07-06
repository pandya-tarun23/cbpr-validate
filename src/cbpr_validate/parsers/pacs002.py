"""Parser for pacs.002 FIToFIPaymentStatusReport.

Extracts the original UETR (falling back to OrgnlTxId / OrgnlEndToEndId when a
UETR is absent on legacy references), the transaction status, and the status
reason code, into the version-agnostic :class:`Payment` model.
"""

from __future__ import annotations

from lxml import etree

from cbpr_validate.model.payment import Payment
from cbpr_validate.parsers._common import find_text


def parse_pacs002(xml_bytes: bytes) -> Payment:
    root = etree.fromstring(xml_bytes)

    tx = root.find(".//{*}TxInfAndSts")
    base = tx if tx is not None else root

    orgnl_uetr = find_text(base, ".//{*}OrgnlUETR")
    orgnl_tx_id = find_text(base, ".//{*}OrgnlTxId")
    orgnl_end_to_end_id = find_text(base, ".//{*}OrgnlEndToEndId")

    # Status reason code lives at StsRsnInf/Rsn/Cd.
    status_reason = find_text(base, ".//{*}StsRsnInf/{*}Rsn/{*}Cd")

    return Payment(
        message_type="pacs.002",
        uetr=orgnl_uetr,
        orgnl_uetr=orgnl_uetr,
        orgnl_tx_id=orgnl_tx_id,
        orgnl_end_to_end_id=orgnl_end_to_end_id,
        orgnl_msg_id=find_text(base, ".//{*}OrgnlGrpInf/{*}OrgnlMsgId")
        or find_text(root, ".//{*}OrgnlGrpInfAndSts/{*}OrgnlMsgId"),
        tx_status=find_text(base, ".//{*}TxSts") or find_text(base, ".//{*}GrpSts"),
        status_reason=status_reason,
    )
