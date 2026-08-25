"""Phase 4.5 — cross-message correlation (CBPR-COR-001/002/003).

Every scenario is covered twice: a clean match, and an adversarial pair that
must be reported as broken (wrong UETR, amount drift, mis-echoed references).
"""

from __future__ import annotations

import pytest

from cbpr_validate.match import (
    Direction,
    MatchKey,
    Scenario,
    UnsupportedPairError,
    correlate,
)
from cbpr_validate.parsers.pacs002 import parse_pacs002
from cbpr_validate.parsers.pacs004 import parse_pacs004
from cbpr_validate.parsers.pacs008 import parse_pacs008
from cbpr_validate.parsers.pacs009 import parse_pacs009

UETR = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER_UETR = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

PACS008 = f"""
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


def _cov(
    uetr: str = UETR,
    amount: str = "1000.00",
    ccy: str = "EUR",
    dbtr: str = "Alice Payer",
    cdtr: str = "Bob Payee",
) -> bytes:
    return f"""
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08">
  <FICdtTrf>
    <GrpHdr><MsgId>MSG-009-1</MsgId></GrpHdr>
    <CdtTrfTxInf>
      <PmtId><UETR>{uetr}</UETR></PmtId>
      <IntrBkSttlmAmt Ccy="{ccy}">{amount}</IntrBkSttlmAmt>
      <InstgRmbrsmntAgt><FinInstnId><BICFI>RMBRDEFF</BICFI></FinInstnId></InstgRmbrsmntAgt>
      <DbtrAgt><FinInstnId><BICFI>DEUTDEFF</BICFI></FinInstnId></DbtrAgt>
      <CdtrAgt><FinInstnId><BICFI>BARCGB22</BICFI></FinInstnId></CdtrAgt>
      <UndrlygCstmrCdtTrf>
        <PmtId><EndToEndId>E2E-1</EndToEndId><TxId>TX-1</TxId><UETR>{uetr}</UETR></PmtId>
        <IntrBkSttlmAmt Ccy="{ccy}">{amount}</IntrBkSttlmAmt>
        <Dbtr><Nm>{dbtr}</Nm></Dbtr>
        <DbtrAgt><FinInstnId><BICFI>DEUTDEFF</BICFI></FinInstnId></DbtrAgt>
        <CdtrAgt><FinInstnId><BICFI>BARCGB22</BICFI></FinInstnId></CdtrAgt>
        <Cdtr><Nm>{cdtr}</Nm></Cdtr>
      </UndrlygCstmrCdtTrf>
    </CdtTrfTxInf>
  </FICdtTrf>
</Document>
""".encode()


PACS009_CORE = b"""
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08">
  <FICdtTrf>
    <CdtTrfTxInf>
      <PmtId><UETR>cccccccc-cccc-4ccc-8ccc-cccccccccccc</UETR></PmtId>
      <IntrBkSttlmAmt Ccy="EUR">1000.00</IntrBkSttlmAmt>
    </CdtTrfTxInf>
  </FICdtTrf>
</Document>
"""


def _pacs002(
    uetr: str | None = UETR,
    orgnl_tx_id: str = "TX-1",
    orgnl_msg_id: str = "MSG-008-1",
) -> bytes:
    uetr_elem = f"<OrgnlUETR>{uetr}</OrgnlUETR>" if uetr else ""
    return f"""
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10">
  <FIToFIPmtStsRpt>
    <TxInfAndSts>
      <OrgnlGrpInf><OrgnlMsgId>{orgnl_msg_id}</OrgnlMsgId></OrgnlGrpInf>
      <OrgnlEndToEndId>E2E-1</OrgnlEndToEndId>
      <OrgnlTxId>{orgnl_tx_id}</OrgnlTxId>
      {uetr_elem}
      <TxSts>ACSC</TxSts>
    </TxInfAndSts>
  </FIToFIPmtStsRpt>
</Document>
""".encode()


def _pacs004(
    uetr: str = UETR,
    orgnl_amount: str = "1000.00",
    returned_amount: str = "990.00",
) -> bytes:
    return f"""
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.004.001.09">
  <PmtRtr>
    <TxInf>
      <OrgnlGrpInf><OrgnlMsgId>MSG-008-1</OrgnlMsgId></OrgnlGrpInf>
      <OrgnlEndToEndId>E2E-1</OrgnlEndToEndId>
      <OrgnlTxId>TX-1</OrgnlTxId>
      <OrgnlUETR>{uetr}</OrgnlUETR>
      <OrgnlIntrBkSttlmAmt Ccy="EUR">{orgnl_amount}</OrgnlIntrBkSttlmAmt>
      <OrgnlIntrBkSttlmDt>2026-07-01</OrgnlIntrBkSttlmDt>
      <RtrdIntrBkSttlmAmt Ccy="EUR">{returned_amount}</RtrdIntrBkSttlmAmt>
      <RtrRsnInf><Rsn><Cd>CANC</Cd></Rsn></RtrRsnInf>
      <ChrgsInf>
        <Amt Ccy="EUR">10.00</Amt>
        <Agt><FinInstnId><BICFI>DEUTDEFF</BICFI></FinInstnId></Agt>
      </ChrgsInf>
    </TxInf>
  </PmtRtr>
</Document>
""".encode()


# --------------------------------------------------------------------------
# The pacs.008 parser must now expose the identifiers correlation matches on.
# --------------------------------------------------------------------------


def test_pacs008_exposes_correlation_identifiers() -> None:
    p = parse_pacs008(PACS008)
    assert p.message_type == "pacs.008"
    assert p.msg_id == "MSG-008-1"
    assert p.tx_id == "TX-1"
    assert p.end_to_end_id == "E2E-1"
    assert p.instr_id == "INSTR-1"
    assert p.interbank_settlement_amount is not None
    assert p.interbank_settlement_amount.currency == "EUR"


# --------------------------------------------------------------------------
# CBPR-COR-001 — pacs.009 COV <-> originating pacs.008
# --------------------------------------------------------------------------


def test_cor001_clean_match() -> None:
    result = correlate(parse_pacs009(_cov()), parse_pacs008(PACS008))
    assert result.matched
    assert result.is_consistent
    assert result.scenario is Scenario.COV
    assert result.match_key is MatchKey.UETR
    assert result.uetr == UETR
    assert not result.fallback_used
    assert result.mismatches == []
    assert "IntrBkSttlmAmt" in result.linked_fields
    assert "Dbtr/Nm" in result.linked_fields and "Cdtr/Nm" in result.linked_fields


def test_cor001_argument_order_does_not_matter() -> None:
    result = correlate(parse_pacs008(PACS008), parse_pacs009(_cov()))
    assert result.matched
    assert result.message_a.message_type == "pacs.009"
    assert result.message_b.message_type == "pacs.008"


def test_cor001_wrong_uetr_is_not_a_match() -> None:
    result = correlate(parse_pacs009(_cov(uetr=OTHER_UETR)), parse_pacs008(PACS008))
    assert not result.matched
    assert not result.is_consistent
    assert result.match_key is MatchKey.UETR
    assert [f.rule_id for f in result.mismatches] == ["CBPR-COR-001"]
    assert result.mismatches[0].severity == "ERROR"


def test_cor001_amount_drift_is_an_error() -> None:
    result = correlate(parse_pacs009(_cov(amount="999.00")), parse_pacs008(PACS008))
    assert result.matched  # linked on UETR ...
    assert not result.is_consistent  # ... but inconsistent
    amounts = [f for f in result.errors if f.location == "IntrBkSttlmAmt"]
    assert len(amounts) == 1
    assert amounts[0].rule_id == "CBPR-COR-001"


def test_cor001_currency_drift_is_an_error() -> None:
    result = correlate(parse_pacs009(_cov(ccy="USD")), parse_pacs008(PACS008))
    assert result.matched
    assert len(result.errors) == 1
    assert "currency differs" in result.errors[0].message


def test_cor001_party_drift_is_a_warning() -> None:
    result = correlate(parse_pacs009(_cov(cdtr="Robert Payee")), parse_pacs008(PACS008))
    assert result.matched
    assert result.is_consistent  # a name difference does not break the link
    assert [f.rule_id for f in result.warnings] == ["CBPR-COR-001"]
    assert result.warnings[0].party == "Cdtr"


def test_cor001_party_name_comparison_ignores_case_and_whitespace() -> None:
    result = correlate(parse_pacs009(_cov(dbtr="  alice   PAYER ")), parse_pacs008(PACS008))
    assert result.warnings == []
    assert "Dbtr/Nm" in result.linked_fields


def test_cor001_core_pacs009_is_not_a_cov() -> None:
    result = correlate(parse_pacs009(PACS009_CORE), parse_pacs008(PACS008))
    assert not result.matched
    assert result.match_key is MatchKey.NONE
    assert "not a COV" in result.mismatches[0].message


def test_cor001_falls_back_to_txid_when_uetr_absent() -> None:
    cov_xml = _cov().replace(f"<UETR>{UETR}</UETR>".encode(), b"")
    original = parse_pacs008(PACS008.replace(f"<UETR>{UETR}</UETR>".encode(), b""))
    result = correlate(parse_pacs009(cov_xml), original)
    assert result.matched
    assert result.match_key is MatchKey.ORGNL_TX_ID
    assert result.fallback_used
    assert result.uetr is None


# --------------------------------------------------------------------------
# CBPR-COR-002 — pacs.002 <-> pacs.008 (bidirectional)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("direction", [Direction.OUTBOUND, Direction.INBOUND])
def test_cor002_clean_match_both_directions(direction: Direction) -> None:
    result = correlate(parse_pacs002(_pacs002()), parse_pacs008(PACS008), direction)
    assert result.matched and result.is_consistent
    assert result.scenario is Scenario.STATUS
    assert result.match_key is MatchKey.UETR
    assert result.direction is direction
    assert set(result.linked_fields) >= {"UETR", "OrgnlMsgId", "OrgnlTxId", "OrgnlEndToEndId"}


def test_cor002_accepts_direction_as_a_string() -> None:
    result = correlate(parse_pacs002(_pacs002()), parse_pacs008(PACS008), "outbound")
    assert result.direction is Direction.OUTBOUND


def test_cor002_direction_is_required() -> None:
    with pytest.raises(ValueError, match="direction is required"):
        correlate(parse_pacs002(_pacs002()), parse_pacs008(PACS008))


def test_cor002_wrong_uetr_is_not_a_match() -> None:
    result = correlate(
        parse_pacs002(_pacs002(uetr=OTHER_UETR)), parse_pacs008(PACS008), "inbound"
    )
    assert not result.matched
    assert [f.rule_id for f in result.errors] == ["CBPR-COR-002"]


def test_cor002_mis_echoed_references_warn_even_when_linked() -> None:
    status = parse_pacs002(_pacs002(orgnl_tx_id="TX-WRONG", orgnl_msg_id="MSG-WRONG"))
    result = correlate(status, parse_pacs008(PACS008), "outbound")
    assert result.matched  # UETR still links them
    assert result.is_consistent
    locations = sorted(f.location for f in result.warnings if f.location)
    assert locations == ["OrgnlMsgId", "OrgnlTxId"]


def test_cor002_falls_back_to_txid_when_uetr_absent() -> None:
    result = correlate(parse_pacs002(_pacs002(uetr=None)), parse_pacs008(PACS008), "inbound")
    assert result.matched
    assert result.match_key is MatchKey.ORGNL_TX_ID
    assert result.fallback_used


def test_cor002_unlinkable_pair_reports_no_shared_identifier() -> None:
    status = parse_pacs002(
        b"""
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10">
  <FIToFIPmtStsRpt><TxInfAndSts><TxSts>ACSC</TxSts></TxInfAndSts></FIToFIPmtStsRpt>
</Document>
"""
    )
    result = correlate(status, parse_pacs008(PACS008), "outbound")
    assert not result.matched
    assert result.match_key is MatchKey.NONE
    assert "share no identifier" in result.mismatches[0].message


# --------------------------------------------------------------------------
# CBPR-COR-003 — pacs.004 return <-> original pacs.008
# --------------------------------------------------------------------------


def test_cor003_clean_match() -> None:
    result = correlate(parse_pacs004(_pacs004()), parse_pacs008(PACS008))
    assert result.matched and result.is_consistent
    assert result.scenario is Scenario.RETURN
    assert result.match_key is MatchKey.UETR
    assert result.mismatches == []


def test_cor003_wrong_uetr_is_not_a_match() -> None:
    result = correlate(parse_pacs004(_pacs004(uetr=OTHER_UETR)), parse_pacs008(PACS008))
    assert not result.matched
    assert [f.rule_id for f in result.errors] == ["CBPR-COR-003"]


def test_cor003_misstated_original_amount_is_an_error() -> None:
    # Internally consistent (990 + 10 charges = 1000) but the original pacs.008
    # actually settled 1000.00 EUR, not 1000.50 — only correlation can see this.
    result = correlate(
        parse_pacs004(_pacs004(orgnl_amount="1000.50", returned_amount="990.50")),
        parse_pacs008(PACS008),
    )
    assert result.matched
    assert not result.is_consistent
    assert result.errors[0].location == "TxInf/OrgnlTxRef/OrgnlIntrBkSttlmAmt"


def test_cor003_returned_more_than_the_real_original_is_an_error() -> None:
    result = correlate(
        parse_pacs004(_pacs004(orgnl_amount="1000.00", returned_amount="1200.00")),
        parse_pacs008(PACS008),
    )
    assert result.matched
    locations = [f.location for f in result.errors]
    assert "TxInf/RtrdIntrBkSttlmAmt" in locations


def test_cor003_skips_amount_checks_without_a_comparable_original() -> None:
    no_settlement = PACS008.replace(
        b'<IntrBkSttlmAmt Ccy="EUR">1000.00</IntrBkSttlmAmt>', b""
    )
    result = correlate(
        parse_pacs004(_pacs004(orgnl_amount="9999.00")), parse_pacs008(no_settlement)
    )
    assert result.matched
    assert result.errors == []  # no like-for-like comparison available


# --------------------------------------------------------------------------
# Fallbacks and fields that cannot be compared
# --------------------------------------------------------------------------


def _strip(xml: bytes, *fragments: bytes) -> bytes:
    for fragment in fragments:
        xml = xml.replace(fragment, b"")
    return xml


UETR_ELEM = f"<UETR>{UETR}</UETR>".encode()
TXID_ELEM = b"<TxId>TX-1</TxId>"
SETTLEMENT_ELEM = b'<IntrBkSttlmAmt Ccy="EUR">1000.00</IntrBkSttlmAmt>'
INSTD_ELEM = b'<Amt><InstdAmt Ccy="EUR">1000.00</InstdAmt></Amt>'


def test_cor001_falls_back_to_end_to_end_id_last() -> None:
    cov = parse_pacs009(_strip(_cov(), UETR_ELEM, TXID_ELEM))
    original = parse_pacs008(_strip(PACS008, UETR_ELEM, TXID_ELEM))
    result = correlate(cov, original)
    assert result.matched
    assert result.match_key is MatchKey.ORGNL_END_TO_END_ID
    assert result.fallback_used


def test_cor001_compares_instructed_amounts_when_no_settlement_amount() -> None:
    cov = parse_pacs009(_cov().replace(b"IntrBkSttlmAmt", b"InstdAmt"))
    original = parse_pacs008(_strip(PACS008, SETTLEMENT_ELEM))
    result = correlate(cov, original)
    assert result.matched and result.is_consistent
    assert "InstdAmt" in result.linked_fields


def test_cor001_emits_nothing_when_no_amounts_are_comparable() -> None:
    cov = parse_pacs009(_strip(_cov(), SETTLEMENT_ELEM))
    original = parse_pacs008(_strip(PACS008, SETTLEMENT_ELEM, INSTD_ELEM))
    result = correlate(cov, original)
    assert result.matched
    assert result.errors == []
    assert "IntrBkSttlmAmt" not in result.linked_fields
    assert "InstdAmt" not in result.linked_fields


def test_cor001_skips_party_comparison_when_a_name_is_absent() -> None:
    cov = parse_pacs009(
        _cov().replace(b"<Dbtr><Nm>Alice Payer</Nm></Dbtr>", b"<Dbtr><PstlAdr/></Dbtr>")
    )
    result = correlate(cov, parse_pacs008(PACS008))
    assert result.matched
    assert result.warnings == []
    assert "Dbtr/Nm" not in result.linked_fields
    assert "Cdtr/Nm" in result.linked_fields


def test_cor002_skips_reference_checks_for_absent_fields() -> None:
    status = parse_pacs002(
        _strip(_pacs002(), b"<OrgnlEndToEndId>E2E-1</OrgnlEndToEndId>")
    )
    result = correlate(status, parse_pacs008(PACS008), "outbound")
    assert result.matched and result.is_consistent
    assert "OrgnlEndToEndId" not in result.linked_fields
    assert "OrgnlTxId" in result.linked_fields


def test_pacs008_ignores_an_unparseable_settlement_amount() -> None:
    p = parse_pacs008(
        PACS008.replace(SETTLEMENT_ELEM, b'<IntrBkSttlmAmt Ccy="EUR">not-a-number</IntrBkSttlmAmt>')
    )
    assert p.interbank_settlement_amount is None


# --------------------------------------------------------------------------
# Unsupported pairs
# --------------------------------------------------------------------------


def test_unsupported_pair_raises() -> None:
    with pytest.raises(UnsupportedPairError, match="Unsupported correlation pair"):
        correlate(parse_pacs008(PACS008), parse_pacs008(PACS008))


def test_unsupported_pair_pacs002_and_pacs004_raises() -> None:
    with pytest.raises(UnsupportedPairError):
        correlate(parse_pacs002(_pacs002()), parse_pacs004(_pacs004()))
