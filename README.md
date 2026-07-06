# cbpr-validate

A Python library, CLI, and API for validating ISO 20022 CBPR+ payment messages against the CBPR+ usage guidelines — not just the XSD.

> XSD-valid ≠ CBPR+-compliant.

## Status

Phase 4 is now implemented and verified. On top of the Phase 0–3 foundation
(normalized payment model, pacs.008 parser, rule registry, address/code/amount/
structural rules, committed ISO 20022 code-set snapshot loader), this phase adds
parsers for **pacs.009 (core + COV)**, **pacs.002**, and **pacs.004**, plus the
**agents** and **returns** rule groups. See [BUILD_PLAN.md](BUILD_PLAN.md) for the
roadmap.

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
- Execute the test suite and lint/type checks locally

## Rule groups

| Group | Rules |
| --- | --- |
| Structural | `CBPR-STR-001..004` |
| Address (SR2026) | `CBPR-ADDR-001/002/004/005` (`ADDR-003` intentionally unregistered) |
| Codes | `CBPR-COD-001..004` |
| Amounts | `CBPR-AMT-001..003` |
| Agents / COV | `CBPR-AGT-001` (WARN), `CBPR-AGT-002` (ERROR), `CBPR-AGT-003` (INFO) |
| Returns (pacs.004) | `CBPR-RTN-001/002/003` (ERROR/WARN), `CBPR-RTN-004` (WARN), `CBPR-RTN-005` (INFO) |

## Verification

Run the following from the repository root:

```bash
python -m pytest -q
python -m ruff check .
python -m mypy src tests
```
