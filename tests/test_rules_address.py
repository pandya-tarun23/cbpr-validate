from cbpr_validate.parsers.pacs008 import parse_pacs008
from cbpr_validate.rules.registry import run_all

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
        <CdtTrfTxInf>
          <PmtId>
            <UETR>11111111-1111-4111-8111-111111111111</UETR>
          </PmtId>
          <Amt>
            <InstdAmt Ccy="EUR">100.00</InstdAmt>
          </Amt>
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

from cbpr_validate.model.finding import Severity   # add to imports

SAMPLE_PARTIAL = b"""
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
  <FIToFICstmrCdtTrf>
    <CstmrCdtTrfInitn>
      <PmtInf>
        <PmtId>
          <UETR>44444444-4444-4444-8444-444444444444</UETR>
        </PmtId>
        <Dbtr>
          <Nm>Partial Debtor</Nm>
          <PstlAdr>
            <TwnNm>Partialtown</TwnNm>
            <!-- Ctry deliberately omitted -->
          </PstlAdr>
        </Dbtr>
        <CdtTrfTxInf>
          <PmtId>
            <UETR>44444444-4444-4444-8444-444444444444</UETR>
          </PmtId>
          <Amt>
            <InstdAmt Ccy="EUR">100.00</InstdAmt>
          </Amt>
        </CdtTrfTxInf>
      </PmtInf>
    </CstmrCdtTrfInitn>
  </FIToFICstmrCdtTrf>
</Document>
"""


def test_addr_002_fires_on_partial_address() -> None:
    p = parse_pacs008(SAMPLE_PARTIAL)
    result = run_all(p)
    findings_002 = [f for f in result.findings if f.rule_id == "CBPR-ADDR-002"]
    # the rule must actually fire on a town-without-country address
    assert findings_002, "ADDR-002 should fire when Ctry is missing"
    # and it must fire at ERROR severity
    assert all(f.severity == Severity.ERROR for f in findings_002)
    # isolation: this is the case ADDR-001 does NOT catch (structured data present)
    ids = {f.rule_id for f in result.findings}
    assert "CBPR-ADDR-001" not in ids

def test_address_rules_structured() -> None:
    p = parse_pacs008(SAMPLE_STRUCTURED)
    result = run_all(p)
    # structured should produce INFO classification and no CBPR-ADDR-001 error
    ids = {f.rule_id for f in result.findings}
    assert "CBPR-ADDR-005" in ids
    assert "CBPR-ADDR-001" not in ids


def test_address_rules_hybrid() -> None:
    p = parse_pacs008(SAMPLE_HYBRID)
    result = run_all(p)
    ids = {f.rule_id for f in result.findings}
    assert "CBPR-ADDR-005" in ids
    assert "CBPR-ADDR-001" not in ids


def test_address_rules_unstructured() -> None:
    p = parse_pacs008(SAMPLE_UNSTRUCTURED)
    result = run_all(p)
    ids = {f.rule_id for f in result.findings}
    assert "CBPR-ADDR-001" in ids
