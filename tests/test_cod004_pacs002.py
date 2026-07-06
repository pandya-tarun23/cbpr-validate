"""CBPR-COD-004 against a REAL parsed pacs.002 (Phase 4 upgrade).

Phase 3 tested this rule by constructing the Payment model directly because no
pacs.002 parser existed yet. Phase 4 adds that parser, so status-reason
validation is now exercised end-to-end from XML.
"""

from cbpr_validate.model.finding import Severity
from cbpr_validate.parsers.pacs002 import parse_pacs002
from cbpr_validate.rules.registry import run_all


def _pacs002(status_reason: str) -> bytes:
    return f"""
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10">
  <FIToFIPmtStsRpt>
    <TxInfAndSts>
      <OrgnlUETR>12121212-1212-4212-8212-121212121212</OrgnlUETR>
      <TxSts>RJCT</TxSts>
      <StsRsnInf><Rsn><Cd>{status_reason}</Cd></Rsn></StsRsnInf>
    </TxInfAndSts>
  </FIToFIPmtStsRpt>
</Document>
""".encode()


def test_cod_004_passes_on_valid_status_reason() -> None:
    result = run_all(parse_pacs002(_pacs002("ACCP")))
    assert not any(f.rule_id == "CBPR-COD-004" for f in result.findings)


def test_cod_004_fires_on_invalid_status_reason() -> None:
    result = run_all(parse_pacs002(_pacs002("NOPE")))
    cod004 = [f for f in result.findings if f.rule_id == "CBPR-COD-004"]
    assert cod004, "COD-004 must fire on a status reason outside ExternalStatusReason1Code"
    assert all(f.severity == Severity.WARN for f in cod004)
