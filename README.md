# cbpr-validate

A Python library, CLI, and API for validating ISO 20022 CBPR+ payment messages against the CBPR+ usage guidelines — not just the XSD.

> XSD-valid ≠ CBPR+-compliant.

## Quickstart

```bash
pip install cbpr-validate
cbpr-validate validate payment.xml
```

```text
CBPR-ADDR-005 | INFO | Address classification for Dbtr: structured | Dbtr.PstlAdr
CBPR-ADDR-005 | INFO | Address classification for Cdtr: unstructured | Cdtr.PstlAdr
CBPR-ADDR-001 | ERROR | Unstructured-only address (AdrLine without TwnNm/Ctry) | Cdtr.PstlAdr
CBPR-ADDR-002 | ERROR | Minimum gate: TownName and Country must be present | Cdtr.PstlAdr
4 finding(s): 2 error, 0 warn, 2 info - NOT COMPLIANT
```

Exit code is `0` when clean and `1` when anything at or above the `--fail-on`
threshold fires (default `error`), so it drops straight into a pipeline. Add
`--json` for machine-readable output.

From Python, one call does the same thing:

```python
from cbpr_validate import validate_file

result = validate_file("payment.xml")
result.is_compliant          # False
[f.rule_id for f in result.errors]
```

`validate_file`, `validate_string` and `validate_bytes` never raise: an
unreadable, malformed or unrecognised document comes back as a result carrying a
single `ORCH-*` ERROR finding, so there is one shape to handle.

## Status

Phase 5 is now implemented and verified. On top of the Phase 0–4.5 foundation
(normalized payment model, parsers for pacs.008/009/002/004, the rule groups, and
the cross-message correlation engine), this phase adds the **three interfaces** —
a Typer CLI, a FastAPI service, JSON/text/JUnit reporters, and the optional XSD
layer. See [BUILD_PLAN.md](BUILD_PLAN.md) for the roadmap.

## Current capabilities

- Parse pacs.008, pacs.009 (core **and** COV, capturing the embedded underlying
  customer credit transfer), pacs.002, and pacs.004 XML into one internal
  Pydantic model
- Run registered validation rules for address, code-set, amount, structural,
  **agent-chain / COV**, and **pacs.004 return** checks
- Validate code values (purpose, category purpose, charge bearer, status reason,
  **return reason**) against a committed ISO 20022 snapshot
- Flag the pacs.009 COV **reimbursement-vs-intermediary agent** distinction
  (`CBPR-AGT-002`) — the check most generic validators miss
- **Correlate two related messages** (COV↔008, 002↔008, 004↔008) on UETR, with a
  flagged legacy fallback, and report amount/party/reference drift between them
- Use it three ways — as a **library**, a **CLI**, or a **REST API** — all three
  producing byte-identical results for the same message
- Emit **human-readable, JSON, or JUnit-XML** output, so it can gate someone
  else's CI pipeline
- Optionally run an **XSD structural pass** against your own licensed schemas

## Correlation (pairwise, stateless)

A rule asks *"does this message comply?"*; a correlation asks *"do these two
messages correctly reference each other?"* — so it returns a `MatchResult`, not a
`ValidationResult`.

```python
from cbpr_validate.match import correlate
from cbpr_validate.parsers.pacs004 import parse_pacs004
from cbpr_validate.parsers.pacs008 import parse_pacs008

result = correlate(parse_pacs004(rtn_xml), parse_pacs008(orig_xml))
result.matched          # linked on a shared identifier?
result.match_key        # UETR | OrgnlTxId | OrgnlEndToEndId | NONE
result.fallback_used    # True when a UETR was absent and a legacy key was used
result.is_consistent    # linked AND nothing about the link is in error
result.mismatches       # Findings: amount drift, party drift, mis-echoed refs
```

Matching is always keyed on **UETR** first (CBPR+ mandates it persist end-to-end);
`OrgnlTxId`/`OrgnlEndToEndId` are used only when a UETR is absent on one side, and
that is flagged. For `pacs.002 ↔ pacs.008` the caller must pass
`direction="outbound" | "inbound"` — the tool never infers identity from BICs.

v1 is deliberately **pairwise and stateless**: you supply the two messages to
compare. A stateful message store is v2 (see BUILD_PLAN §12).

## Interfaces

All three front doors run the same parsing, the same rules and the same
formatting code. `tests/test_interface_parity.py` compares their actual output
and fails if they ever diverge.

### CLI

```bash
cbpr-validate validate message.xml                   # single-file front door
cbpr-validate validate message.xml --json
cbpr-validate validate message.xml --fail-on warning

cbpr-validate check message.xml                      # human-readable
cbpr-validate check message.xml --format json        # machine-readable
cbpr-validate check message.xml --format junit       # CI gate
cbpr-validate check message.xml --fail-on warn       # tighten the gate
cbpr-validate check message.xml --xsd --xsd-dir ./schemas

cbpr-validate match pacs009.xml pacs008.xml
cbpr-validate match pacs002.xml pacs008.xml --direction outbound
cbpr-validate match pacs004.xml pacs008.xml
```

`validate` is the one-file front door built on `cbpr_validate.core`; `check` is
the fuller command that adds `--format junit` and the optional `--xsd` pass, and
`match` correlates two messages.

Exit codes are part of the contract: `0` clean, `1` findings at or above the
`--fail-on` threshold (or the two messages do not correlate), `2` the input
could not be used. Only `ERROR` findings become JUnit `<failure>` elements, so a
build fails exactly when the message is non-compliant.

### API

```bash
uvicorn cbpr_validate.api.main:app --reload
```

`POST /validate` runs every rule against one message; `POST /correlate` takes two
messages plus an optional `direction`. OpenAPI docs are served at `/docs`.

```bash
curl -X POST localhost:8000/validate \
  -H 'content-type: application/json' \
  -d '{"message": "<Document ...>"}'
```

### Library

```python
from cbpr_validate.parsers.parse import parse_message
from cbpr_validate.rules.registry import run_all

result = run_all(parse_message(xml_bytes))
result.is_compliant, result.errors, result.warnings
```

## The optional XSD layer

No SWIFT schema is shipped or committed here. Point `CBPR_VALIDATE_XSD_DIR` (or
`--xsd-dir`) at your own licensed copy of the ISO 20022 message definitions and
schema files are matched by message family. If a schema cannot be located the
command **fails loudly** rather than silently reporting "clean" — you asked for
the layer, so pretending it ran would be a lie.

This layer is deliberately secondary. The schema is the floor; the usage
guidelines are the bar.

## Rule groups

| Group | Rules |
| --- | --- |
| Structural | `CBPR-STR-001..004` |
| Address (SR2026) | `CBPR-ADDR-001/002/004/005` (`ADDR-003` intentionally unregistered) |
| Codes | `CBPR-COD-001..004` |
| Amounts | `CBPR-AMT-001..003` |
| Agents / COV | `CBPR-AGT-001` (WARN), `CBPR-AGT-002` (ERROR), `CBPR-AGT-003` (INFO) |
| Returns (pacs.004) | `CBPR-RTN-001/002/003` (ERROR/WARN), `CBPR-RTN-004` (WARN), `CBPR-RTN-005` (INFO) |

## Correlation scenarios

| Scenario | ID | Pair | Key |
| --- | --- | --- | --- |
| COV | `CBPR-COR-001` | pacs.009 COV ↔ originating pacs.008 | `UndrlygCstmrCdtTrf` UETR |
| Status | `CBPR-COR-002` | pacs.002 ↔ pacs.008 (bidirectional, `direction` required) | `OrgnlUETR` |
| Return | `CBPR-COR-003` | pacs.004 ↔ original pacs.008 | `OrgnlUETR` |

## Verification

Run the following from the repository root:

```bash
python -m pytest -q
python -m ruff check .
python -m mypy src tests
```
