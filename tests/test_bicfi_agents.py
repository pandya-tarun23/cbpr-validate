"""The pacs.008 parser must read BICFI, not just the legacy BIC.

`pacs008.py` carried its own agent parser that looked only for `BIC`. Real CBPR+
traffic carries `BICFI`, so on a live message both agents parsed as `None` and
`CBPR-STR-002`, `CBPR-AGT-001` and `CBPR-AGT-003` returned no findings - not
because the message was clean, but because they had nothing to inspect.

That is a false negative, and it is harder to catch than a false positive: a
silent rule and a passing rule look identical from the outside. So these tests
do not merely assert "no findings" on good input - each adversarial case proves
the rule can still *fail*, which is the only evidence it actually ran.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cbpr_validate.model.finding import Severity
from cbpr_validate.parsers.parse import parse_message
from cbpr_validate.rules.agents import cbpr_agt_001_chain_consistency, cbpr_agt_003_lei
from cbpr_validate.rules.structural import cbpr_str_002_agent_bics

FIXTURE = Path(__file__).parent / "fixtures" / "pacs008_valid_hybrid_ro.xml"


def _pacs008(dbtr_agt: str, cdtr_agt: str, element: str = "BICFI", lei: str = "") -> bytes:
    lei_xml = f"<LEI>{lei}</LEI>" if lei else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
  <FIToFICstmrCdtTrf>
    <GrpHdr><MsgId>MSG-1</MsgId></GrpHdr>
    <CdtTrfTxInf>
      <PmtId><UETR>7a562c67-ca16-48ba-b074-65581be6f001</UETR></PmtId>
      <IntrBkSttlmAmt Ccy="EUR">100.00</IntrBkSttlmAmt>
      <Dbtr><Nm>Debtor Co</Nm>
        <PstlAdr><TwnNm>Epping</TwnNm><Ctry>GB</Ctry></PstlAdr></Dbtr>
      <DbtrAgt><FinInstnId><{element}>{dbtr_agt}</{element}>{lei_xml}</FinInstnId></DbtrAgt>
      <CdtrAgt><FinInstnId><{element}>{cdtr_agt}</{element}></FinInstnId></CdtrAgt>
      <Cdtr><Nm>Ardent Finance</Nm>
        <PstlAdr><TwnNm>Bucharest</TwnNm><Ctry>RO</Ctry></PstlAdr></Cdtr>
    </CdtTrfTxInf>
  </FIToFICstmrCdtTrf>
</Document>
""".encode()


# --- the parser reads both spellings ---------------------------------------


@pytest.mark.parametrize("element", ["BICFI", "BIC"])
def test_parser_reads_both_bicfi_and_legacy_bic(element: str) -> None:
    payment = parse_message(_pacs008("MYMBGB2LXXX", "GEBABEBBXXX", element=element))
    assert payment.dbtr_agt is not None and payment.dbtr_agt.bic == "MYMBGB2LXXX"
    assert payment.cdtr_agt is not None and payment.cdtr_agt.bic == "GEBABEBBXXX"


def test_parser_reads_agents_from_the_real_cbpr_plus_fixture() -> None:
    """The regression guard: these were both None before the fix."""
    payment = parse_message(FIXTURE.read_bytes())
    assert payment.dbtr_agt is not None and payment.dbtr_agt.bic == "MYMBGB2LXXX"
    assert payment.cdtr_agt is not None and payment.cdtr_agt.bic == "GEBABEBBXXX"


# --- and the rules that depend on it can now actually fail ------------------


def test_str002_fires_on_a_malformed_bicfi() -> None:
    payment = parse_message(_pacs008("NOTABIC!", "GEBABEBBXXX"))
    findings = cbpr_str_002_agent_bics(payment)
    assert len(findings) == 1
    assert findings[0].rule_id == "CBPR-STR-002"
    assert findings[0].severity is Severity.ERROR
    assert findings[0].location == "DbtrAgt.BIC"


def test_str002_passes_valid_bicfis() -> None:
    assert cbpr_str_002_agent_bics(parse_message(_pacs008("MYMBGB2LXXX", "GEBABEBBXXX"))) == []


def test_agt001_fires_when_bicfi_collapses_the_chain() -> None:
    payment = parse_message(_pacs008("MYMBGB2LXXX", "MYMBGB2LXXX"))
    findings = cbpr_agt_001_chain_consistency(payment)
    assert len(findings) == 1
    assert findings[0].rule_id == "CBPR-AGT-001"
    assert findings[0].severity is Severity.WARN


def test_agt003_fires_on_a_malformed_lei_beside_a_bicfi() -> None:
    payment = parse_message(_pacs008("MYMBGB2LXXX", "GEBABEBBXXX", lei="TOO-SHORT"))
    findings = cbpr_agt_003_lei(payment)
    assert len(findings) == 1
    assert findings[0].rule_id == "CBPR-AGT-003"
    assert findings[0].severity is Severity.INFO


# --- the point of the whole fix --------------------------------------------


def test_the_three_rules_are_no_longer_silent_on_a_bicfi_message() -> None:
    """Before the fix every one of these returned [] on a BICFI message because
    the agents were None. Each now demonstrably fails on bad input."""
    bad = parse_message(_pacs008("NOTABIC!", "NOTABIC!", lei="TOO-SHORT"))
    assert cbpr_str_002_agent_bics(bad), "STR-002 is silent - agents not parsed"
    assert cbpr_agt_001_chain_consistency(bad), "AGT-001 is silent - agents not parsed"
    assert cbpr_agt_003_lei(bad), "AGT-003 is silent - agents not parsed"
