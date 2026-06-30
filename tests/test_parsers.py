from cbpr_validate.parsers.pacs008 import parse_pacs008


SAMPLE_STRUCTURED = b"""
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
  <FIToFICstmrCdtTrf>
    <CstmrCdtTrfInitn>
      <PmtInf>
        <PmtId>
          <UETR>11111111-1111-4111-8111-111111111111</UETR>
        </PmtId>
        <Dbtr>
          <Nm>Debtor Name</Nm>
          <PstlAdr>
            <TwnNm>Townsville</TwnNm>
            <Ctry>GB</Ctry>
          </PstlAdr>
        </Dbtr>
        <DbtrAgt>
          <FinInstnId>
            <BIC>DEUTDEFF</BIC>
          </FinInstnId>
        </DbtrAgt>
        <CdtTrfTxInf>
          <PmtId>
            <UETR>11111111-1111-4111-8111-111111111111</UETR>
          </PmtId>
          <Amt>
            <InstdAmt Ccy="EUR">100.00</InstdAmt>
          </Amt>
          <Cdtr>
            <Nm>Creditor Name</Nm>
          </Cdtr>
          <CdtrAgt>
            <FinInstnId>
              <BIC>BARCGB22</BIC>
            </FinInstnId>
          </CdtrAgt>
        </CdtTrfTxInf>
      </PmtInf>
    </CstmrCdtTrfInitn>
  </FIToFICstmrCdtTrf>
</Document>
"""


SAMPLE_HYBRID = b"""
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
  <FIToFICstmrCdtTrf>
    <CstmrCdtTrfInitn>
      <PmtInf>
        <PmtId>
          <UETR>22222222-2222-4222-8222-222222222222</UETR>
        </PmtId>
        <Dbtr>
          <Nm>Hybrid Debtor</Nm>
          <PstlAdr>
            <AdrLine>123 Example Street</AdrLine>
            <TwnNm>Metrocity</TwnNm>
            <Ctry>US</Ctry>
          </PstlAdr>
        </Dbtr>
        <CdtTrfTxInf>
          <PmtId>
            <UETR>22222222-2222-4222-8222-222222222222</UETR>
          </PmtId>
          <Amt>
            <InstdAmt Ccy="USD">2500.50</InstdAmt>
          </Amt>
        </CdtTrfTxInf>
      </PmtInf>
    </CstmrCdtTrfInitn>
  </FIToFICstmrCdtTrf>
</Document>
"""


SAMPLE_UNSTRUCTURED = b"""
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
  <FIToFICstmrCdtTrf>
    <CstmrCdtTrfInitn>
      <PmtInf>
        <PmtId>
          <UETR>33333333-3333-4333-8333-333333333333</UETR>
        </PmtId>
        <Dbtr>
          <Nm>Unstructured Debtor</Nm>
          <PstlAdr>
            <AdrLine>One line address only</AdrLine>
          </PstlAdr>
        </Dbtr>
        <CdtTrfTxInf>
          <PmtId>
            <UETR>33333333-3333-4333-8333-333333333333</UETR>
          </PmtId>
          <Amt>
            <InstdAmt Ccy="JPY">1000</InstdAmt>
          </Amt>
        </CdtTrfTxInf>
      </PmtInf>
    </CstmrCdtTrfInitn>
  </FIToFICstmrCdtTrf>
</Document>
"""


def test_parse_structured() -> None:
    p = parse_pacs008(SAMPLE_STRUCTURED)
    assert p.uetr is not None
    assert p.amount is not None
    assert p.amount.currency == "EUR"


def test_parse_hybrid() -> None:
    p = parse_pacs008(SAMPLE_HYBRID)
    assert p.uetr is not None
    assert p.amount is not None
    assert p.amount.currency == "USD"


def test_parse_unstructured() -> None:
    p = parse_pacs008(SAMPLE_UNSTRUCTURED)
    assert p.uetr is not None
    assert p.amount is not None
    assert p.amount.currency == "JPY"
