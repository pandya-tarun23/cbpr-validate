# cbpr-validate

A Python library, CLI, and API for validating ISO 20022 CBPR+ payment messages against the CBPR+ usage guidelines — not just the XSD.

> XSD-valid ≠ CBPR+-compliant.

## Status

Phase 3 is now implemented and verified. The project includes a normalized payment model, a pacs.008 parser, a rule registry, address/code/amount/structural validation rules, and a committed ISO 20022 code-set snapshot loader. See [BUILD_PLAN.md](BUILD_PLAN.md) for the roadmap.

## Current capabilities

- Parse pacs.008 XML into an internal Pydantic model
- Run registered validation rules for address, code-set, amount, and structural checks
- Validate code values against a committed ISO 20022 snapshot
- Execute the test suite and lint/type checks locally

## Verification

Run the following from the repository root:

```bash
python -m pytest -q
python -m ruff check .
python -m mypy src tests
```
