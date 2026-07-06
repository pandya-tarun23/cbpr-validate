from decimal import Decimal

from cbpr_validate.parsers.detect import detect_message_type
from cbpr_validate.parsers.pacs002 import parse_pacs002
from cbpr_validate.parsers.pacs004 import parse_pacs004
from cbpr_validate.parsers.pacs009 import is_cov, parse_pacs009

PACS009_CORE = b"""
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08">
  <FICdtTrf>
    <GrpHdr>
      <InstgAgt><FinInstnId><BICFI>AAAAUS33</BICFI></FinInstnId></InstgAgt>
      <InstdAgt><FinInstnId><BICFI>BBBBGB22</BICFI></FinInstnId></InstdAgt>
    </GrpHdr>
    <CdtTrfTxInf>
      <PmtId><UETR>99999999-9999-4999-8999-999999999999</UETR></PmtId>
      <IntrBkSttlmAmt Ccy="USD">5000.00</IntrBkSttlmAmt>
      <DbtrAgt><FinInstnId><BICFI>DEUTDEFF</BICFI></FinInstnId></DbtrAgt>
      <CdtrAgt><FinInstnId><BICFI>BARCGB22</BICFI></FinInstnId></CdtrAgt>
    </CdtTrfTxInf>
  </FICdtTrf>
</Document>
"""

PACS009_COV = b"""
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08">
  <FICdtTrf>
    <CdtTrfTxInf>
      <PmtId><UETR>abababab-abab-4bab-8bab-abababababab</UETR></PmtId>
      <IntrBkSttlmAmt Ccy="EUR">7500.00</IntrBkSttlmAmt>
      <InstgRmbrsmntAgt><FinInstnId><BICFI>RMBRDEFF</BICFI></FinInstnId></InstgRmbrsmntAgt>
      <DbtrAgt><FinInstnId><BICFI>DEUTDEFF</BICFI></FinInstnId></DbtrAgt>
      <CdtrAgt><FinInstnId><BICFI>BARCGB22</BICFI></FinInstnId></CdtrAgt>
      <UndrlygCstmrCdtTrf>
        <PmtId><UETR>abababab-abab-4bab-8bab-abababababab</UETR></PmtId>
        <InstdAmt Ccy="EUR">7500.00</InstdAmt>
        <Dbtr><Nm>Alice</Nm><PstlAdr><TwnNm>Berlin</TwnNm><Ctry>DE</Ctry></PstlAdr></Dbtr>
        <DbtrAgt><FinInstnId><BICFI>DEUTDEFF</BICFI></FinInstnId></DbtrAgt>
        <CdtrAgt><FinInstnId><BICFI>BARCGB22</BICFI></FinInstnId></CdtrAgt>
        <Cdtr><Nm>Bob</Nm><PstlAdr><TwnNm>London</TwnNm><Ctry>GB</Ctry></PstlAdr></Cdtr>
      </UndrlygCstmrCdtTrf>
    </CdtTrfTxInf>
  </FICdtTrf>
</Document>
"""

PACS002 = b"""
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10">
  <FIToFIPmtStsRpt>
    <TxInfAndSts>
      <OrgnlUETR>12121212-1212-4212-8212-121212121212</OrgnlUETR>
      <OrgnlTxId>TX-ORIG-1</OrgnlTxId>
      <TxSts>RJCT</TxSts>
      <StsRsnInf><Rsn><Cd>AC04</Cd></Rsn></StsRsnInf>
    </TxInfAndSts>
  </FIToFIPmtStsRpt>
</Document>
"""

PACS004 = b"""
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.004.001.09">
  <PmtRtr>
    <TxInf>
      <OrgnlGrpInf><OrgnlMsgId>MSG-ORIG-1</OrgnlMsgId></OrgnlGrpInf>
      <OrgnlEndToEndId>E2E-1</OrgnlEndToEndId>
      <OrgnlTxId>TX-1</OrgnlTxId>
      <OrgnlUETR>34343434-3434-4434-8434-343434343434</OrgnlUETR>
      <OrgnlIntrBkSttlmAmt Ccy="USD">1000.00</OrgnlIntrBkSttlmAmt>
      <OrgnlIntrBkSttlmDt>2026-07-01</OrgnlIntrBkSttlmDt>
      <RtrdIntrBkSttlmAmt Ccy="USD">990.00</RtrdIntrBkSttlmAmt>
      <RtrRsnInf><Rsn><Cd>CANC</Cd></Rsn></RtrRsnInf>
      <ChrgsInf>
        <Amt Ccy="USD">10.00</Amt>
        <Agt><FinInstnId><BICFI>DEUTDEFF</BICFI></FinInstnId></Agt>
      </ChrgsInf>
    </TxInf>
  </PmtRtr>
</Document>
"""


def test_detect_all_phase4_types() -> None:
    assert detect_message_type(PACS009_CORE) == "pacs.009"
    assert detect_message_type(PACS009_COV) == "pacs.009"
    assert detect_message_type(PACS002) == "pacs.002"
    assert detect_message_type(PACS004) == "pacs.004"


def test_parse_pacs009_core() -> None:
    p = parse_pacs009(PACS009_CORE)
    assert p.message_type == "pacs.009"
    assert p.uetr == "99999999-9999-4999-8999-999999999999"
    assert p.amount is not None and p.amount.currency == "USD"
    assert p.instg_agt is not None and p.instg_agt.bic == "AAAAUS33"
    assert p.instd_agt is not None and p.instd_agt.bic == "BBBBGB22"
    assert not is_cov(p)


def test_parse_pacs009_cov_captures_underlying() -> None:
    p = parse_pacs009(PACS009_COV)
    assert is_cov(p)
    assert p.underlying is not None
    # embedded underlying customer credit transfer: parties, agents, UETR
    assert p.underlying.uetr == "abababab-abab-4bab-8bab-abababababab"
    assert p.underlying.dbtr is not None and p.underlying.dbtr.name == "Alice"
    assert p.underlying.cdtr is not None and p.underlying.cdtr.name == "Bob"
    assert p.underlying.dbtr_agt is not None and p.underlying.dbtr_agt.bic == "DEUTDEFF"
    assert p.underlying.cdtr_agt is not None and p.underlying.cdtr_agt.bic == "BARCGB22"
    assert p.underlying.amount is not None and p.underlying.amount.currency == "EUR"


def test_parse_pacs002() -> None:
    p = parse_pacs002(PACS002)
    assert p.message_type == "pacs.002"
    assert p.orgnl_uetr == "12121212-1212-4212-8212-121212121212"
    assert p.uetr == p.orgnl_uetr  # UETR is the primary key
    assert p.orgnl_tx_id == "TX-ORIG-1"
    assert p.tx_status == "RJCT"
    assert p.status_reason == "AC04"


def test_parse_pacs002_falls_back_to_txid() -> None:
    xml = PACS002.replace(
        b"<OrgnlUETR>12121212-1212-4212-8212-121212121212</OrgnlUETR>", b""
    )
    p = parse_pacs002(xml)
    assert p.orgnl_uetr is None
    assert p.orgnl_tx_id == "TX-ORIG-1"


def test_parse_pacs004() -> None:
    p = parse_pacs004(PACS004)
    assert p.message_type == "pacs.004"
    assert p.return_reason == "CANC"
    assert p.orgnl_msg_id == "MSG-ORIG-1"
    assert p.orgnl_end_to_end_id == "E2E-1"
    assert p.orgnl_tx_id == "TX-1"
    assert p.orgnl_uetr == "34343434-3434-4434-8434-343434343434"
    assert p.orgnl_interbank_settlement_amount is not None
    assert p.orgnl_interbank_settlement_amount.value == Decimal("1000.00")
    assert p.orgnl_interbank_settlement_date == "2026-07-01"
    assert p.returned_interbank_settlement_amount is not None
    assert p.returned_interbank_settlement_amount.value == Decimal("990.00")
    assert p.charges is not None and len(p.charges) == 1
    assert p.charges[0].amount is not None and p.charges[0].amount.value == Decimal("10.00")
