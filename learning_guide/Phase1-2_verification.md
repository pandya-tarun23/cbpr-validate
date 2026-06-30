# Phase 1–2 Verification Steps

This document records the verification steps used while implementing Phase 1 (Model + Parser + Detection) and Phase 2 (Rule engine + Address rules).

Summary of checks performed
- Unit tests: parser and rule tests were added and executed (`tests/test_parsers.py`, `tests/test_rules_address.py`).
- Full test-suite run validated integration between parsing and rules.
- BUILD_PLAN.md updated to mark Phase 1 and Phase 2 complete.

Quick commands

Run the full test suite (recommended):

```bash
python -m pytest -q
```

Run only parser tests:

```bash
python -m pytest tests/test_parsers.py -q
```

Run only address rule tests:

```bash
python -m pytest tests/test_rules_address.py -q
```

Programmatic verification examples

Parse a `pacs.008` XML file and inspect the model:

```python
from cbpr_validate.parsers.pacs008 import parse_pacs008

with open("pacs008.xml","rb") as f:
    payment = parse_pacs008(f.read())

print(payment.model_dump())
```

Run all registered rules against a parsed message:

```python
from cbpr_validate.rules.registry import run_all
from cbpr_validate.parsers.pacs008 import parse_pacs008

with open("pacs008.xml","rb") as f:
    payment = parse_pacs008(f.read())

result = run_all(payment)
print(result.json())
```

Inspect registered rule names (useful to confirm registration):

```python
from cbpr_validate.rules.registry import list_rules
print(list_rules())
```

Coverage and diagnostic steps
- Run coverage via pytest to see current gaps:

```bash
python -m pytest --cov=cbpr_validate --cov-report=term-missing -q
```

- Files to inspect when something fails:
  - `src/cbpr_validate/parsers/pacs008.py` — parsing logic
  - `src/cbpr_validate/parsers/detect.py` — detection utility
  - `src/cbpr_validate/model/` — domain models
  - `src/cbpr_validate/rules/` — rule implementations and `registry.py`

Notes and next verification tasks
- Add tests for `parsers/detect.py` to increase coverage for detection logic.
- Add adversarial fixtures (edge cases) for address rules (line caps, missing attributes, special characters) and expand `tests/fixtures/`.
- Add tests for `rules/registry.py` defensive branches (rule exceptions) and for `model/validation_result.py` helpers.

Location
- This file: `learning_guide/Phase1-2_verification.md`
- BUILD_PLAN entry updated at: `BUILD_PLAN.md` (Phase 1 and Phase 2 sections).

If you want, I can now (choose):
- add `parsers/detect.py` unit tests to increase coverage, or
- scaffold `codesets/loader.py` and `rules/codes.py` to begin Phase 3.
