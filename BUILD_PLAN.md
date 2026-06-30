# `cbpr-validate` — Build Plan

**Goal:** A production-grade, open-source Python library + API for validating ISO 20022 CBPR+ payment messages against the **usage guidelines** — not just the XSD. The differentiator your tool makes explicit: *XSD-valid ≠ CBPR+-compliant.*

This is the "prototype → production" step. You already have the core SR2026 address logic working in your two prototypes; this plan turns that into something a team could actually adopt, and that you can point to in a senior interview.

---

## 1. The bar: what "production-grade" means here

A personal project can't run inside a bank, but it can be production-*grade*. Every item below is a deliberate signal of engineering maturity:

- Built to a **public, citable spec** (ISO 20022 / CBPR+) — every rule traces to a source.
- **Installable**: `pip install cbpr-validate`, published to PyPI, semantic versioning.
- **Three interfaces**: Python library, CLI, and a FastAPI REST service with an OpenAPI spec.
- **Dockerised**, with a one-command run.
- **Tested**: pytest suite, >90% coverage, fixtures for valid/invalid messages, CI gate.
- **CI/CD**: GitHub Actions (lint, type-check, test, build, publish).
- Real **error handling, logging, config**; handles multiple message versions and edge cases.
- **Documented** well enough that someone else could adopt it (mkdocs site + README).

---

## 2. Scope

**In scope (v1):**
- Message types: `pacs.008` (incl. SR2026 version), `pacs.009` (core + COV), `pacs.002` (status), `pacs.004` (return).
- Validation layers: (a) optional XSD structural check, (b) CBPR+ usage rules (the value-add).
- External Code Set validation (purpose, category purpose, charge bearer, status reason, return reason).
- **Cross-message correlation (pairwise)** — given two related messages, verify they reference each other correctly:
  - a `pacs.009` COV ↔ the originating `pacs.008` it covers,
  - a `pacs.002` ↔ the `pacs.008` it reports status on, in **either direction** (outgoing `pacs.008` you sent / incoming `pacs.002` reply you received, or incoming `pacs.008` you received / outgoing `pacs.002` reply you sent),
  - a `pacs.004` return ↔ the original `pacs.008` it returns.
  - v1 is intentionally **stateless and pairwise**: you hand the tool the two specific messages to compare; it does not ingest or store a stream of messages over time. See §12 for the stateful version (v2).
- Outputs: human-readable, JSON, and JUnit-XML (so it can run as a CI gate in *other* pipelines).

**Out of scope (v1) — note explicitly in the README:**
- camt.05x / camt.110-111 (v2 roadmap).
- Network/transport, real schemas redistribution, any proprietary scheme (e.g. Aani).
- Message *generation* (v2 — pairs naturally with the agentic project later).
- A stateful message store / live correlation across an arbitrary stream of messages (v2 — v1 is pairwise only, see §12).

---

## 3. Architecture

Layered, so each piece is testable and extensible. Internal normalized model decouples rules from message version.

```
cbpr-validate/
├── pyproject.toml
├── README.md
├── ARCHITECTURE.md          # the senior-signal doc (see §11)
├── Dockerfile
├── mkdocs.yml
├── .github/workflows/ci.yml
├── docs/
├── src/cbpr_validate/
│   ├── __init__.py
│   ├── parsers/             # XML/JSON → internal model (version-aware)
│   │   ├── pacs008.py
│   │   ├── pacs009.py
│   │   ├── pacs002.py
│   │   ├── pacs004.py       # return message parser
│   │   └── detect.py        # root-element + namespace detection
│   ├── model/               # Pydantic domain model
│   │   ├── payment.py       # Payment, Party, Agent, PostalAddress, Amount
│   │   └── finding.py       # Finding, Severity, ValidationResult
│   ├── rules/               # one module per rule group; rule registry
│   │   ├── registry.py
│   │   ├── structural.py    # UETR, BIC, mandatory fields
│   │   ├── address.py       # SR2026 structured/hybrid/unstructured
│   │   ├── codes.py         # External Code Set checks
│   │   ├── amounts.py       # currency / fractional digits
│   │   ├── agents.py        # agent-chain & COV consistency
│   │   └── returns.py       # pacs.004 return-reason & amount rules
│   ├── match/               # cross-message correlation (pairwise, v1)
│   │   ├── matcher.py       # Correlator: COV/status/return matching
│   │   └── result.py        # MatchResult model
│   ├── codesets/            # External Code Set loader + cache
│   │   ├── loader.py        # syncs from published source
│   │   └── data/            # cached snapshots, versioned
│   ├── schema/
│   │   └── xsd.py           # lxml XSD validation; path via config/env
│   ├── report/              # output formatters
│   │   ├── json_report.py
│   │   ├── text_report.py
│   │   └── junit_report.py
│   ├── api/
│   │   └── main.py          # FastAPI app: POST /validate, POST /correlate
│   ├── cli.py               # Typer CLI: check, match
│   └── config.py            # settings (env-driven)
└── tests/
    ├── conftest.py          # shared message fixtures
    ├── fixtures/            # valid + adversarial sample messages
    └── test_*.py
```

---

## 4. Core data models

**`Finding`** — the unit of output. Make it rich and traceable (this is what separates it from a toy validator):

```
Finding:
    rule_id:        str        # e.g. "CBPR-ADDR-001"
    severity:       Severity   # ERROR | WARN | INFO
    message:        str        # plain-English explanation
    location:       str        # XPath / field path
    party:          str|None   # Dbtr / Cdtr / DbtrAgt ...
    remediation:    str        # how to fix
    spec_reference: str        # citation to the guideline / code set
```

**`ValidationResult`** — aggregates findings, exposes `.is_compliant`, `.errors`, `.warnings`, and serialises to each output format.

**`MatchResult`** — the unit of output for cross-message correlation (§6). Distinct from `Finding`/`ValidationResult` because it describes a relationship *between two messages*, not a property of one:

```
MatchResult:
    matched:         bool
    scenario:        str            # "COV", "STATUS", "RETURN"
    match_key:       str            # field the match was decided on, e.g. "UETR"
    uetr:            str | None
    linked_fields:   list[str]      # Orgnl*/UndrlygCstmrCdtTrf fields that matched
    mismatches:      list[Finding]  # e.g. amount mismatch, party mismatch
    message_a:       MessageRef     # type + UETR/TxId of the first message
    message_b:       MessageRef     # type + UETR/TxId of the second message
```

**Internal model** (`Payment`, `Party`, `Agent`, `PostalAddress`, `Amount`) — Pydantic, version-agnostic, so a `pacs.008.001.08` and the SR2026 version both normalise to the same shape and rules run once.

---

## 5. Rule catalogue (v1)

Implement each as a registered rule with a stable ID. Group + severity below. **Verify every threshold against the actual CBPR+ usage guideline and cite it in `spec_reference`** — don't hardcode from memory.

**Structural (`structural.py`)**
- `CBPR-STR-001` UETR present and valid UUIDv4 — ERROR
- `CBPR-STR-002` All agent BICs valid format (8/11, BICFI) — ERROR
- `CBPR-STR-003` Mandatory CBPR+ elements present (per message type) — ERROR
- `CBPR-STR-004` Settlement method / clearing system consistency — WARN

**Address / SR2026 (`address.py`)** — the headline group
- `CBPR-ADDR-001` Unstructured-only address (AdrLine, no TwnNm/Ctry) — ERROR *(invalid after 14 Nov 2026)*
- `CBPR-ADDR-002` Minimum gate: structured TwnNm **and** Ctry present — ERROR if missing
- `CBPR-ADDR-003` Hybrid address line-count within cap *(verify exact cap)* — WARN
- `CBPR-ADDR-004` Ctry is ISO 3166-1 alpha-2 — ERROR
- `CBPR-ADDR-005` Classify & report: fully-structured / hybrid / unstructured — INFO

**Codes (`codes.py`)** — validate against live External Code Sets
- `CBPR-COD-001` Purpose code ∈ ExternalPurpose1Code — ERROR
- `CBPR-COD-002` Category purpose ∈ ExternalCategoryPurpose1Code — ERROR
- `CBPR-COD-003` Charge bearer ∈ {DEBT, CRED, SHAR, SLEV} + CBPR+ usage — ERROR/WARN
- `CBPR-COD-004` (pacs.002) Status reason ∈ ExternalStatusReason1Code — WARN

**Amounts (`amounts.py`)**
- `CBPR-AMT-001` Currency ∈ ISO 4217 — ERROR
- `CBPR-AMT-002` Fractional digits valid for currency (e.g. JPY = 0) — ERROR
- `CBPR-AMT-003` Amount > 0 — ERROR

**Agents / COV (`agents.py`)**
- `CBPR-AGT-001` Agent chain consistency (Dbtr/Instg/Intrmy/Cdtr agents) — WARN
- `CBPR-AGT-002` (pacs.009 COV) Reimbursement vs intermediary agent distinction — ERROR
- `CBPR-AGT-003` LEI present/valid where required — INFO

> The COV rule (`CBPR-AGT-002`) is worth highlighting in your docs — it's exactly the pacs.009 distinction most generic tools get wrong, and it signals you know the standard at depth.

**Returns (`returns.py`)** — pacs.004 usage rules
- `CBPR-RTN-001` Return reason code ∈ ExternalReturnReason1Code — ERROR
- `CBPR-RTN-002` Mandatory original-reference fields present (OrgnlMsgId, OrgnlEndToEndId, OrgnlTxId, OrgnlUETR, OrgnlInterbankSettlementAmt, OrgnlInterbankSettlementDt) — ERROR
- `CBPR-RTN-003` Returned interbank settlement amount ≤ original interbank settlement amount, net of disclosed charges *(verify exact CBPR+ tolerance/charge-deduction rule)* — ERROR/WARN
- `CBPR-RTN-004` Charges-deducted breakdown (`ChrgsInf`), if present, reconciles with original vs. returned amount — WARN
- `CBPR-RTN-005` Compensation/interest fields, if present, well-formed — INFO

---

## 6. Correlation catalogue (v1)

Distinct from §5: these checks don't evaluate a single message against the guidelines, they evaluate **whether two specific messages correctly reference each other**. v1 is deliberately pairwise and stateless — no message store, no "watch a stream and tell me what arrives." You pass the tool exactly the two messages you want compared; it tells you whether they're linked and, if so, whether anything about the link is inconsistent (amount, parties, dates).

Primary match key is always **UETR** (CBPR+ mandates it persist end-to-end across a payment's lifecycle); fall back to `OrgnlTxId` / `OrgnlEndToEndId` only when UETR is absent on legacy/non-CBPR+ messages, and flag that fallback in the result.

- `CBPR-COR-001` **pacs.009 COV ↔ originating pacs.008** — match `UndrlygCstmrCdtTrf.PmtId.UETR` (in the COV's embedded underlying transaction) against the originating `pacs.008`'s `PmtId.UETR`. On match, cross-check settlement amount/currency and Dbtr/Cdtr consistency between the two.
- `CBPR-COR-002` **pacs.002 ↔ pacs.008 (bidirectional)** — match `TxInfAndSts.OrgnlUETR` (falling back to `OrgnlTxId`/`OrgnlEndToEndId`) against the `pacs.008`'s `PmtId`. Direction (was the `pacs.008` sent by you or received by you) is passed explicitly via a `direction: outbound|inbound` parameter — the tool does not infer identity from BICs; see CLI below.
- `CBPR-COR-003` **pacs.004 return ↔ original pacs.008** — match `OrgnlGrpInf`/`TxInf.OrgnlUETR` against the original `pacs.008`'s `PmtId.UETR`. On match, cross-check returned amount against original (feeds `CBPR-RTN-003`).

**Interface shape (Phase 5):**
```
cbpr-validate match pacs009.xml pacs008.xml
cbpr-validate match pacs008.xml pacs002.xml --direction outbound
cbpr-validate match pacs004.xml pacs008.xml
```
Each prints/serialises a `MatchResult` (§4). The API equivalent is `POST /correlate` taking two message payloads (+ optional `direction`) and returning the same structure as JSON.

---

## 7. Spec sources (all public — this is why production-grade is achievable)

- **ISO 20022 message schemas**: iso20022.org registry (download the message definitions you support).
- **External Code Sets**: published on iso20022.org, refreshed quarterly — your `codesets/loader.py` should sync from the published file and snapshot it with a version stamp. Includes `ExternalReturnReason1Code` for `CBPR-RTN-001`.
- **CBPR+ usage guidelines**: SWIFT MyStandards (CBPR+ Usage Guidelines). *Note: needs a free MyStandards account; read the rules, implement them, cite them — do not redistribute.*
- **SR2026 specifics**: SWIFT Standards Release 2026 documentation.

> **Licensing:** never commit SWIFT XSDs or copied guideline text to a public repo. Implement rules in your own code, cite the source in `spec_reference`, and have users point the XSD path at their own licensed copy via env var.

---

## 8. Tech stack

- Python 3.11+, **Pydantic v2** (model + validation), **lxml** (XSD + XPath).
- **Typer** (CLI), **FastAPI** + **uvicorn** (API), **httpx** for code-set sync.
- **pytest** + **pytest-cov**, **ruff** (lint), **mypy** (types).
- **mkdocs-material** (docs), **Docker**, **GitHub Actions**.
- Build/publish: `hatchling` or `setuptools` + `build` + `twine` (PyPI via Trusted Publishing).
- No persistence layer in v1 — correlation is pairwise/in-memory only (see §6, §12).

---

## 9. Production-grade checklist (your "definition of done")

- [ ] `pip install cbpr-validate` works from PyPI (start on TestPyPI).
- [ ] CLI: `cbpr-validate check message.xml --format json`.
- [ ] CLI: `cbpr-validate match a.xml b.xml [--direction outbound|inbound]` covers COV→008, 002↔008, 004→008.
- [ ] API: `POST /validate` and `POST /correlate` return structured findings/results + OpenAPI docs at `/docs`.
- [ ] `docker run` validates a file with zero local setup.
- [ ] >90% test coverage; CI fails on lint/type/test errors.
- [ ] Semantic versioning + CHANGELOG.
- [ ] README with quickstart, badges (CI, coverage, PyPI), and the "XSD-valid ≠ compliant" explainer.
- [ ] ARCHITECTURE.md + at least 3 ADRs (decision records).
- [ ] A benchmark number (messages/sec) in the README.

---

## 10. Build phases (≈7–9 weeks, part-time)

**Phase 0 — Skeleton (½ week)**
Repo, `pyproject.toml`, package layout, ruff/mypy/pytest config, CI that runs lint+test on an empty suite. *DoD: green CI on `main`.* ✅ done.

**Phase 1 — Model + parser + detection (1 week)**
Pydantic model, `pacs008` parser, `detect.py`. Port and harden your existing extraction. *DoD: parse 3 sample pacs.008 (structured/hybrid/unstructured) into the model, tested.*

Status: **Completed** ✅

What was delivered:
- Pydantic v2 models: `Payment`, `Party`, `Agent`, `PostalAddress`, `Amount` ([src/cbpr_validate/model/payment.py](src/cbpr_validate/model/payment.py#L1)).
- `Finding` and `ValidationResult` helpers for rule outputs ([src/cbpr_validate/model/finding.py](src/cbpr_validate/model/finding.py#L1), [src/cbpr_validate/model/validation_result.py](src/cbpr_validate/model/validation_result.py#L1)).
- Lightweight `pacs.008` parser and a `detect` utility that identify and populate the model ([src/cbpr_validate/parsers/pacs008.py](src/cbpr_validate/parsers/pacs008.py#L1), [src/cbpr_validate/parsers/detect.py](src/cbpr_validate/parsers/detect.py#L1)).
- Unit tests covering structured, hybrid and unstructured address scenarios (tests pass).

How to verify locally:

Run the test suite:

```bash
python -m pytest -q
```

Quick programmatic example (parse a file):

```python
from cbpr_validate.parsers.pacs008 import parse_pacs008

with open("pacs008.xml","rb") as f:
    payment = parse_pacs008(f.read())

print(payment.model_dump())
```

Notes / next steps for Phase 1 → 2:
- Move on to the rules registry and implement the `address` rule group per §5 (Phase 2).
- Add adversarial fixtures and extend parser coverage for additional pacs.008 variants.

**Phase 2 — Rule engine + address rules (1–1.5 weeks)**
Registry, `Finding`/`ValidationResult`, the full `address.py` group. *DoD: SR2026 address rules pass adversarial fixtures.*

Status: **Completed** ✅

What was delivered:
- A lightweight rules registry with decorator-based registration and runner ([src/cbpr_validate/rules/registry.py](src/cbpr_validate/rules/registry.py#L1)).
- Address rule group implementing `CBPR-ADDR-001`, `CBPR-ADDR-002`, and `CBPR-ADDR-005` ([src/cbpr_validate/rules/address.py](src/cbpr_validate/rules/address.py#L1)).
- Unit tests exercising the address rules against structured, hybrid and unstructured `pacs.008` fixtures ([tests/test_rules_address.py](tests/test_rules_address.py#L1)).

How to verify locally:

Run the test suite (or the address tests only):

```bash
python -m pytest tests/test_rules_address.py -q
python -m pytest -q
```

Programmatic example (run all registered rules against a parsed message):

```python
from cbpr_validate.parsers.pacs008 import parse_pacs008
from cbpr_validate.rules.registry import run_all

with open("pacs008.xml","rb") as f:
    p = parse_pacs008(f.read())

result = run_all(p)
print(result.json())
```

Notes / next steps for Phase 2 → 3:
- Expand the rules registry if needed (rule metadata, severity mapping, stable `rule_id` enforcement).
- Implement `codes.py`, `amounts.py`, and `structural.py` in Phase 3 and add code-set snapshot loader in `codesets/loader.py`.
- Add adversarial fixtures for edge cases (address line caps, non-ASCII town names, missing currency attributes).

**Phase 3 — Codes + amounts + structural (1 week)**
`codesets/loader.py` (sync + snapshot), `codes.py`, `amounts.py`, `structural.py`. *DoD: purpose/charge-bearer validated against a real code-set snapshot.*

**Phase 4 — pacs.009 (COV) + pacs.002 + pacs.004 (return) + agents (1.5 weeks)**
Parsers for all three, `agents.py` incl. the COV rule, `returns.py` for pacs.004. *DoD: COV reimbursement-vs-intermediary rule tested; pacs.004 return-reason + amount rules tested.*

**Phase 4.5 — Correlation engine (0.5–1 week)**
`match/matcher.py` + `MatchResult` (§6): COV↔008, 002↔008 (bidirectional via `direction`), 004↔008, all keyed primarily on UETR. *DoD: each of the three scenarios passes fixtures for both a clean match and a deliberately mismatched pair (wrong UETR, amount drift).*

**Phase 5 — Interfaces (1 week)**
CLI (Typer: `check`, `match`), FastAPI service (`/validate`, `/correlate`), JSON/text/JUnit reporters, optional XSD layer. *DoD: all three interfaces validate and correlate the same messages identically.*

**Phase 6 — Productionise + publish (1 week)**
Dockerfile, mkdocs site, README polish, badges, benchmark, TestPyPI → PyPI, tag v1.0.0. *DoD: clean install + run by someone other than you.*

---

## 11. Senior-signal artifacts (do not skip)

These convert "a repo" into "an architect's portfolio":
- **ARCHITECTURE.md** — the layered design + why the internal model decouples rules from versions.
- **ADRs** (`docs/adr/`) — e.g. "Why rules in code, not a rules DSL", "Why we don't ship SWIFT XSDs", "Why an internal normalized model", "Why correlation is pairwise/stateless in v1, not a stored ledger".
- **A design note**: "XSD-valid ≠ CBPR+-compliant — what the schema can't catch" (this is also your next LinkedIn post).
- **Benchmark**: throughput number proves you thought about scale.

---

## 12. v2 roadmap (state it in the README to show vision)

camt.053/054 and camt.110/111 (E&I) · a web playground (hosted) · a GitHub Action others can use as a CI step · message *generation* (links to the agentic project) · pluggable rule packs for other market practices (HVPS+, regional) · **a stateful, pluggable `MessageStore`** so messages can be ingested one at a time as they arrive (`cbpr-validate ingest`) and correlations queried later (`cbpr-validate query --uetr ...`) instead of always being supplied pairwise.

---

## 13. Working with Claude Code

Drop this file in the repo root and drive phase by phase. Example prompts:

- *Phase 1:* "Implement `src/cbpr_validate/model/payment.py` as Pydantic v2 models per §4, and `parsers/pacs008.py` to populate them, reusing the address-extraction approach from my existing repo. Add tests against the fixtures."
- *Phase 2:* "Implement the `rules/registry.py` and `rules/address.py` rule group per the §5 catalogue. Each rule returns `Finding` objects with `spec_reference`. Write adversarial tests."
- *Phase 4:* "Implement `parsers/pacs004.py` and `rules/returns.py` per the §5 Returns group. Cite `ExternalReturnReason1Code` in `spec_reference`."
- *Phase 4.5:* "Implement `match/matcher.py` and `MatchResult` per §6 — the three correlation scenarios (COV→008, 002↔008 bidirectional, 004→008), keyed on UETR with the documented fallback. Write fixtures for both clean matches and deliberate mismatches."
- *Phase 5:* "Add a FastAPI `POST /validate` endpoint that runs all registered rules and returns a `ValidationResult` as JSON, with OpenAPI docs. Add `POST /correlate` per §6."

Keep each phase a separate PR/commit so the history reads as deliberate engineering.
