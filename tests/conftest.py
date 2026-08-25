"""Shared message fixtures for the interface tests (Phase 5).

Kept here rather than in individual test modules so the CLI, API and parity
tests all drive the *same* bytes - that is what makes "all three interfaces
behave identically" a meaningful assertion rather than three similar fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

UETR = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER_UETR = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

# A pacs.008 with nothing wrong: valid UUIDv4 UETR, valid BICs, fully structured
# addresses, EUR to 2dp. Registered rules still emit two ADDR-005 INFO
# classifications - INFO is reporting, not a defect, so it stays compliant.
PACS008_CLEAN = f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
  <FIToFICstmrCdtTrf>
    <GrpHdr><MsgId>MSG-008-1</MsgId></GrpHdr>
    <CdtTrfTxInf>
      <PmtId>
        <InstrId>INSTR-1</InstrId>
        <EndToEndId>E2E-1</EndToEndId>
        <TxId>TX-1</TxId>
        <UETR>{UETR}</UETR>
      </PmtId>
      <IntrBkSttlmAmt Ccy="EUR">1000.00</IntrBkSttlmAmt>
      <Amt><InstdAmt Ccy="EUR">1000.00</InstdAmt></Amt>
      <Dbtr>
        <Nm>Alice Payer</Nm>
        <PstlAdr><TwnNm>Berlin</TwnNm><Ctry>DE</Ctry></PstlAdr>
      </Dbtr>
      <DbtrAgt><FinInstnId><BIC>DEUTDEFF</BIC></FinInstnId></DbtrAgt>
      <CdtrAgt><FinInstnId><BIC>BARCGB22</BIC></FinInstnId></CdtrAgt>
      <Cdtr>
        <Nm>Bob Payee</Nm>
        <PstlAdr><TwnNm>London</TwnNm><Ctry>GB</Ctry></PstlAdr>
      </Cdtr>
    </CdtTrfTxInf>
  </FIToFICstmrCdtTrf>
</Document>
""".encode()

# The headline failure: an unstructured-only creditor address. XSD-valid, and
# non-compliant from 14 Nov 2026 (CBPR-ADDR-001 + CBPR-ADDR-002).
PACS008_UNSTRUCTURED = PACS008_CLEAN.replace(
    b"<PstlAdr><TwnNm>London</TwnNm><Ctry>GB</Ctry></PstlAdr>",
    b"<PstlAdr><AdrLine>221B Baker Street, London</AdrLine></PstlAdr>",
)

PACS009_COV = f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08">
  <FICdtTrf>
    <GrpHdr><MsgId>MSG-009-1</MsgId></GrpHdr>
    <CdtTrfTxInf>
      <PmtId><UETR>{UETR}</UETR></PmtId>
      <IntrBkSttlmAmt Ccy="EUR">1000.00</IntrBkSttlmAmt>
      <InstgRmbrsmntAgt><FinInstnId><BICFI>RMBRDEFF</BICFI></FinInstnId></InstgRmbrsmntAgt>
      <DbtrAgt><FinInstnId><BICFI>DEUTDEFF</BICFI></FinInstnId></DbtrAgt>
      <CdtrAgt><FinInstnId><BICFI>BARCGB22</BICFI></FinInstnId></CdtrAgt>
      <UndrlygCstmrCdtTrf>
        <PmtId><EndToEndId>E2E-1</EndToEndId><TxId>TX-1</TxId><UETR>{UETR}</UETR></PmtId>
        <IntrBkSttlmAmt Ccy="EUR">1000.00</IntrBkSttlmAmt>
        <Dbtr><Nm>Alice Payer</Nm></Dbtr>
        <DbtrAgt><FinInstnId><BICFI>DEUTDEFF</BICFI></FinInstnId></DbtrAgt>
        <CdtrAgt><FinInstnId><BICFI>BARCGB22</BICFI></FinInstnId></CdtrAgt>
        <Cdtr><Nm>Bob Payee</Nm></Cdtr>
      </UndrlygCstmrCdtTrf>
    </CdtTrfTxInf>
  </FICdtTrf>
</Document>
""".encode()

PACS002 = f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10">
  <FIToFIPmtStsRpt>
    <TxInfAndSts>
      <OrgnlGrpInf><OrgnlMsgId>MSG-008-1</OrgnlMsgId></OrgnlGrpInf>
      <OrgnlEndToEndId>E2E-1</OrgnlEndToEndId>
      <OrgnlTxId>TX-1</OrgnlTxId>
      <OrgnlUETR>{UETR}</OrgnlUETR>
      <TxSts>ACSC</TxSts>
    </TxInfAndSts>
  </FIToFIPmtStsRpt>
</Document>
""".encode()

PACS004 = f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.004.001.09">
  <PmtRtr>
    <TxInf>
      <OrgnlGrpInf><OrgnlMsgId>MSG-008-1</OrgnlMsgId></OrgnlGrpInf>
      <OrgnlEndToEndId>E2E-1</OrgnlEndToEndId>
      <OrgnlTxId>TX-1</OrgnlTxId>
      <OrgnlUETR>{UETR}</OrgnlUETR>
      <OrgnlIntrBkSttlmAmt Ccy="EUR">1000.00</OrgnlIntrBkSttlmAmt>
      <OrgnlIntrBkSttlmDt>2026-07-01</OrgnlIntrBkSttlmDt>
      <RtrdIntrBkSttlmAmt Ccy="EUR">990.00</RtrdIntrBkSttlmAmt>
      <RtrRsnInf><Rsn><Cd>CANC</Cd></Rsn></RtrRsnInf>
      <ChrgsInf>
        <Amt Ccy="EUR">10.00</Amt>
        <Agt><FinInstnId><BICFI>DEUTDEFF</BICFI></FinInstnId></Agt>
      </ChrgsInf>
    </TxInf>
  </PmtRtr>
</Document>
""".encode()

# A return that quotes a UETR belonging to a different payment entirely.
PACS004_WRONG_UETR = PACS004.replace(UETR.encode(), OTHER_UETR.encode())

NOT_A_MESSAGE = b"<Document><Nope/></Document>"


def _write(directory: Path, name: str, content: bytes) -> Path:
    path = directory / name
    path.write_bytes(content)
    return path


@pytest.fixture
def pacs008_clean(tmp_path: Path) -> Path:
    return _write(tmp_path, "pacs008_clean.xml", PACS008_CLEAN)


@pytest.fixture
def pacs008_unstructured(tmp_path: Path) -> Path:
    return _write(tmp_path, "pacs008_unstructured.xml", PACS008_UNSTRUCTURED)


@pytest.fixture
def pacs009_cov(tmp_path: Path) -> Path:
    return _write(tmp_path, "pacs009_cov.xml", PACS009_COV)


@pytest.fixture
def pacs002(tmp_path: Path) -> Path:
    return _write(tmp_path, "pacs002.xml", PACS002)


@pytest.fixture
def pacs004(tmp_path: Path) -> Path:
    return _write(tmp_path, "pacs004.xml", PACS004)


@pytest.fixture
def pacs004_wrong_uetr(tmp_path: Path) -> Path:
    return _write(tmp_path, "pacs004_wrong.xml", PACS004_WRONG_UETR)


@pytest.fixture
def not_a_message(tmp_path: Path) -> Path:
    return _write(tmp_path, "junk.xml", NOT_A_MESSAGE)
