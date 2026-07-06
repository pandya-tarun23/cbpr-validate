from cbpr_validate.model.finding import Severity
from cbpr_validate.parsers.pacs009 import parse_pacs009
from cbpr_validate.rules.registry import run_all

# A well-formed COV: the reimbursement (cover) agent is a DISTINCT institution
# from any intermediary agent. AGT-002 must NOT fire.
COV_CLEAN = b"""
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
        <Dbtr><Nm>Alice</Nm></Dbtr>
        <DbtrAgt><FinInstnId><BICFI>DEUTDEFF</BICFI></FinInstnId></DbtrAgt>
        <CdtrAgt><FinInstnId><BICFI>BARCGB22</BICFI></FinInstnId></CdtrAgt>
        <Cdtr><Nm>Bob</Nm></Cdtr>
      </UndrlygCstmrCdtTrf>
    </CdtTrfTxInf>
  </FICdtTrf>
</Document>
"""

# ADVERSARIAL COV: the SAME institution (RMBRDEFF) is presented as both the
# reimbursement (cover) agent and an intermediary agent — the classic COV error.
# AGT-002 must fire at ERROR.
COV_REIMB_INTRMY_COLLISION = b"""
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08">
  <FICdtTrf>
    <CdtTrfTxInf>
      <PmtId><UETR>cdcdcdcd-cdcd-4dcd-8dcd-cdcdcdcdcdcd</UETR></PmtId>
      <IntrBkSttlmAmt Ccy="EUR">7500.00</IntrBkSttlmAmt>
      <InstgRmbrsmntAgt><FinInstnId><BICFI>RMBRDEFF</BICFI></FinInstnId></InstgRmbrsmntAgt>
      <IntrmyAgt1><FinInstnId><BICFI>RMBRDEFF</BICFI></FinInstnId></IntrmyAgt1>
      <DbtrAgt><FinInstnId><BICFI>DEUTDEFF</BICFI></FinInstnId></DbtrAgt>
      <CdtrAgt><FinInstnId><BICFI>BARCGB22</BICFI></FinInstnId></CdtrAgt>
      <UndrlygCstmrCdtTrf>
        <PmtId><UETR>cdcdcdcd-cdcd-4dcd-8dcd-cdcdcdcdcdcd</UETR></PmtId>
        <Dbtr><Nm>Alice</Nm></Dbtr>
        <DbtrAgt><FinInstnId><BICFI>DEUTDEFF</BICFI></FinInstnId></DbtrAgt>
        <CdtrAgt><FinInstnId><BICFI>BARCGB22</BICFI></FinInstnId></CdtrAgt>
        <Cdtr><Nm>Bob</Nm></Cdtr>
      </UndrlygCstmrCdtTrf>
    </CdtTrfTxInf>
  </FICdtTrf>
</Document>
"""

# Chain collapse: DbtrAgt == CdtrAgt. AGT-001 must fire at WARN.
CORE_CHAIN_COLLAPSE = b"""
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08">
  <FICdtTrf>
    <CdtTrfTxInf>
      <PmtId><UETR>efefefef-efef-4fef-8fef-efefefefefef</UETR></PmtId>
      <IntrBkSttlmAmt Ccy="USD">100.00</IntrBkSttlmAmt>
      <DbtrAgt><FinInstnId><BICFI>DEUTDEFF</BICFI></FinInstnId></DbtrAgt>
      <CdtrAgt><FinInstnId><BICFI>DEUTDEFF</BICFI></FinInstnId></CdtrAgt>
    </CdtTrfTxInf>
  </FICdtTrf>
</Document>
"""

# Malformed LEI on the debtor agent. AGT-003 must fire at INFO.
CORE_BAD_LEI = b"""
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08">
  <FICdtTrf>
    <CdtTrfTxInf>
      <PmtId><UETR>10101010-1010-4010-8010-101010101010</UETR></PmtId>
      <IntrBkSttlmAmt Ccy="USD">100.00</IntrBkSttlmAmt>
      <DbtrAgt><FinInstnId><BICFI>DEUTDEFF</BICFI><LEI>NOT-A-VALID-LEI</LEI></FinInstnId></DbtrAgt>
      <CdtrAgt><FinInstnId><BICFI>BARCGB22</BICFI></FinInstnId></CdtrAgt>
    </CdtTrfTxInf>
  </FICdtTrf>
</Document>
"""


def test_agt_002_passes_on_clean_cov() -> None:
    result = run_all(parse_pacs009(COV_CLEAN))
    assert not any(f.rule_id == "CBPR-AGT-002" for f in result.findings)


def test_agt_002_fires_on_reimbursement_intermediary_collision() -> None:
    result = run_all(parse_pacs009(COV_REIMB_INTRMY_COLLISION))
    agt002 = [f for f in result.findings if f.rule_id == "CBPR-AGT-002"]
    assert agt002, "AGT-002 must fire when a reimbursement agent is reused as intermediary"
    assert all(f.severity == Severity.ERROR for f in agt002)
    assert all(f.spec_reference for f in agt002)


def test_agt_001_fires_on_chain_collapse() -> None:
    result = run_all(parse_pacs009(CORE_CHAIN_COLLAPSE))
    agt001 = [f for f in result.findings if f.rule_id == "CBPR-AGT-001"]
    assert agt001
    assert all(f.severity == Severity.WARN for f in agt001)


def test_agt_001_passes_on_distinct_agents() -> None:
    result = run_all(parse_pacs009(COV_CLEAN))
    assert not any(f.rule_id == "CBPR-AGT-001" for f in result.findings)


def test_agt_003_fires_on_malformed_lei() -> None:
    result = run_all(parse_pacs009(CORE_BAD_LEI))
    agt003 = [f for f in result.findings if f.rule_id == "CBPR-AGT-003"]
    assert agt003
    assert all(f.severity == Severity.INFO for f in agt003)


def test_agt_003_silent_when_no_lei_present() -> None:
    result = run_all(parse_pacs009(CORE_CHAIN_COLLAPSE))
    assert not any(f.rule_id == "CBPR-AGT-003" for f in result.findings)
