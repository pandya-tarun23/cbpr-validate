from cbpr_validate.parsers.detect import detect_message_type
from cbpr_validate.model.validation_result import ValidationResult
from cbpr_validate.model.finding import Finding, Severity
from cbpr_validate.rules import registry


def test_detect_pacs008_namespace() -> None:
    xml = b'<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"><A/></Document>'
    assert detect_message_type(xml) == "pacs.008"


def test_detect_non_pacs_returns_none() -> None:
    xml = b'<root xmlns="urn:example"><a/></root>'
    assert detect_message_type(xml) is None


def test_validation_result_helpers() -> None:
    f_err = Finding(rule_id="R_ERR", severity=Severity.ERROR, message="error")
    f_warn = Finding(rule_id="R_WARN", severity=Severity.WARN, message="warn")
    vr = ValidationResult(findings=[f_err, f_warn])
    assert vr.errors == [f_err]
    assert vr.warnings == [f_warn]
    assert vr.is_compliant is False


def test_registry_exception_branch() -> None:
    # preserve existing rules
    before = list(registry._RULES)

    @registry.register
    def _broken(payment):
        raise RuntimeError("boom")

    try:
        res = registry.run_all(None)
        ids = {f.rule_id for f in res.findings}
        assert "REG-EXC" in ids
    finally:
        # restore original registry to avoid test pollution
        registry._RULES[:] = before
