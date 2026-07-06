from cbpr_validate.model.finding import Severity
from cbpr_validate.parsers.pacs004 import parse_pacs004
from cbpr_validate.rules.registry import run_all


def _pacs004(
    *,
    reason: str = "CANC",
    orgnl_amt: str = "1000.00",
    rtrd_amt: str = "990.00",
    ccy: str = "USD",
    charges: str = '<ChrgsInf><Amt Ccy="USD">10.00</Amt></ChrgsInf>',
    drop: str = "",
    compensation: str = "",
) -> bytes:
    rows = {
        "OrgnlMsgId": "<OrgnlGrpInf><OrgnlMsgId>MSG-1</OrgnlMsgId></OrgnlGrpInf>",
        "OrgnlEndToEndId": "<OrgnlEndToEndId>E2E-1</OrgnlEndToEndId>",
        "OrgnlTxId": "<OrgnlTxId>TX-1</OrgnlTxId>",
        "OrgnlUETR": "<OrgnlUETR>34343434-3434-4434-8434-343434343434</OrgnlUETR>",
        "OrgnlIntrBkSttlmAmt": (
            f'<OrgnlIntrBkSttlmAmt Ccy="{ccy}">{orgnl_amt}</OrgnlIntrBkSttlmAmt>'
        ),
        "OrgnlIntrBkSttlmDt": "<OrgnlIntrBkSttlmDt>2026-07-01</OrgnlIntrBkSttlmDt>",
    }
    if drop:
        rows.pop(drop)
    body = "".join(rows.values())
    return f"""
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.004.001.09">
  <PmtRtr>
    <TxInf>
      {body}
      <RtrdIntrBkSttlmAmt Ccy="{ccy}">{rtrd_amt}</RtrdIntrBkSttlmAmt>
      <RtrRsnInf><Rsn><Cd>{reason}</Cd></Rsn></RtrRsnInf>
      {charges}
      {compensation}
    </TxInf>
  </PmtRtr>
</Document>
""".encode()


def test_rtn_clean_return_has_no_errors() -> None:
    result = run_all(parse_pacs004(_pacs004()))
    for rid in ("CBPR-RTN-001", "CBPR-RTN-002", "CBPR-RTN-003", "CBPR-RTN-004"):
        assert not any(f.rule_id == rid for f in result.findings), rid


def test_rtn_001_fires_on_invalid_return_reason() -> None:
    result = run_all(parse_pacs004(_pacs004(reason="ZZZZ")))
    rtn001 = [f for f in result.findings if f.rule_id == "CBPR-RTN-001"]
    assert rtn001
    assert all(f.severity == Severity.ERROR for f in rtn001)


def test_rtn_002_fires_on_missing_original_reference() -> None:
    result = run_all(parse_pacs004(_pacs004(drop="OrgnlEndToEndId")))
    rtn002 = [f for f in result.findings if f.rule_id == "CBPR-RTN-002"]
    assert rtn002, "RTN-002 must fire when an original-reference field is absent"
    assert all(f.severity == Severity.ERROR for f in rtn002)
    assert any("OrgnlEndToEndId" in f.message for f in rtn002)


def test_rtn_003_fires_when_returned_exceeds_original() -> None:
    result = run_all(parse_pacs004(_pacs004(orgnl_amt="1000.00", rtrd_amt="1200.00", charges="")))
    rtn003 = [f for f in result.findings if f.rule_id == "CBPR-RTN-003"]
    assert rtn003, "RTN-003 must fire when the returned amount exceeds the original"
    assert all(f.severity == Severity.ERROR for f in rtn003)


def test_rtn_003_currency_mismatch_is_error() -> None:
    xml = _pacs004(ccy="USD")
    xml = xml.replace(b'<RtrdIntrBkSttlmAmt Ccy="USD">', b'<RtrdIntrBkSttlmAmt Ccy="EUR">')
    result = run_all(parse_pacs004(xml))
    rtn003 = [f for f in result.findings if f.rule_id == "CBPR-RTN-003"]
    assert rtn003
    assert all(f.severity == Severity.ERROR for f in rtn003)


def test_rtn_003_warns_on_unexplained_shortfall() -> None:
    # returned < original but NO charges disclosed to explain the gap -> WARN
    result = run_all(parse_pacs004(_pacs004(rtrd_amt="990.00", charges="")))
    rtn003 = [f for f in result.findings if f.rule_id == "CBPR-RTN-003"]
    assert rtn003
    assert all(f.severity == Severity.WARN for f in rtn003)


def test_rtn_004_fires_when_charges_do_not_reconcile() -> None:
    # returned 990 + charges 5 != original 1000 -> WARN
    charges = '<ChrgsInf><Amt Ccy="USD">5.00</Amt></ChrgsInf>'
    result = run_all(parse_pacs004(_pacs004(rtrd_amt="990.00", charges=charges)))
    rtn004 = [f for f in result.findings if f.rule_id == "CBPR-RTN-004"]
    assert rtn004
    assert all(f.severity == Severity.WARN for f in rtn004)


def test_rtn_005_fires_on_malformed_compensation() -> None:
    comp = '<CompstnAmt Ccy="USD">-5.00</CompstnAmt>'
    result = run_all(parse_pacs004(_pacs004(compensation=comp)))
    rtn005 = [f for f in result.findings if f.rule_id == "CBPR-RTN-005"]
    assert rtn005
    assert all(f.severity == Severity.INFO for f in rtn005)


def test_rtn_rules_do_not_run_on_non_return() -> None:
    # A pacs.004 rule set must stay silent for other message types.
    from cbpr_validate.model.payment import Payment

    result = run_all(Payment(message_type="pacs.008"))
    assert not any(f.rule_id.startswith("CBPR-RTN") for f in result.findings)
