# cbpr-validate

A Python library, CLI, and API for validating ISO 20022 CBPR+ payment messages against the CBPR+ usage guidelines — not just the XSD.

> XSD-valid ≠ CBPR+-compliant.

## Status

Phase 4.5 is now implemented and verified. On top of the Phase 0–4 foundation
(normalized payment model, parsers for pacs.008/009/002/004, and the address,
code, amount, structural, agent and return rule groups), this phase adds the
**cross-message correlation engine** — pairwise, stateless checks that two
specific messages correctly reference each other. See
[BUILD_PLAN.md](BUILD_PLAN.md) for the roadmap.

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
- Execute the test suite and lint/type checks locally

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
