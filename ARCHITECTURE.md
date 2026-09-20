# Architecture

<!-- TODO: one or two sentences in your own voice. Suggested seed below — edit freely. -->
`cbpr-validate` validates ISO 20022 CBPR+ payment messages against the **usage
guidelines**, not just the XSD schema. This document explains how it is built and
why the key decisions were made — the schema tells you a message is *well-formed*;
this tool tells you whether it is *CBPR+-compliant*.

---

## 1. The problem: XSD-valid ≠ CBPR+-compliant

<!-- TODO: 3–5 sentences. This is the thesis of the whole project — say it in your own words.
Points to hit:
- An XSD checks structure/data types. It passes messages that still violate CBPR+ usage rules.
- Concrete examples the tool catches that XSD cannot: unstructured-only postal address (invalid under SR2026),
  the pacs.009 COV reimbursement-vs-intermediary agent distinction, cross-message drift between a pacs.004
  return and the pacs.008 it reverses.
- Why this matters operationally: these gaps are what cause manual repair, reconciliation, and last-mile delay. -->

---

## 2. Design goals

<!-- TODO: keep or trim. These are the principles the rest of the doc should visibly follow. -->
- **Traceable** — every finding carries a stable `rule_id`, a plain-English message, a field location, a
  remediation hint, and a `spec_reference` back to the guideline.
- **Version-decoupled** — a rule is written once and runs against any supported message version, because rules
  operate on an internal normalized model, not on raw XML.
- **One core, many interfaces** — library, CLI, and REST API all go through the same parse → validate → report
  path, so they cannot disagree about what a message means.
- **Honest failure** — "we could not evaluate this message" is never reported as "this message is compliant."
- **No licensed material in the repo** — SWIFT XSDs and guideline text are never redistributed; rules are
  implemented in code and cite their source.

---

## 3. High-level architecture

A layered pipeline. Each stage is independently testable, and the internal model is the seam that decouples
everything downstream from message-version specifics.

```
            ┌─────────── interfaces ───────────┐
            │  library (core.py)  CLI  REST API │
            └─────────────────┬─────────────────┘
                              │  (one shared core)
   raw bytes ──► detect ──► parse ──► normalized model ──►  rules engine  ──► findings ──┐
                (namespace)  (per type)   (Pydantic)         correlation   ──► matches  ──┤
                                                                                          ▼
                                                                        report: text / JSON / JUnit
```

<!-- TODO: if you draw a nicer diagram later (e.g. a PNG or mermaid), drop it in here. Optional. -->

---

## 4. The layers

### 4.1 Detection & parsing (`parsers/`)
- `detect.py` identifies the message type by namespace (root element or child of a SWIFT envelope), covering
  `pacs.008 / .009 / .002 / .004`.
- `parse.py` (`parse_message`) dispatches to the per-type parser; individual parsers
  (`pacs008.py`, `pacs009.py`, `pacs002.py`, `pacs004.py`, shared `_common.py`) turn XML into the model.
- The pacs.009 COV parser captures the embedded `UndrlygCstmrCdtTrf` as a nested `Payment`, so the COV rule
  and cross-message correlation can reach the underlying transaction.

### 4.2 Internal normalized model (`model/`)
- Pydantic v2 models — `Payment`, `Party`, `Agent`, `PostalAddress`, `Amount` — version-agnostic by design.
- `Finding` (with `Severity` = ERROR | WARN | INFO) and `ValidationResult` (`is_compliant`, `errors`,
  `warnings`) are the output units for single-message validation.
- **This is the key architectural seam:** a `pacs.008.001.08` and its SR2026 variant both normalise to the
  same shape, so every rule is written once. (See ADR-003.)

### 4.3 Rule engine (`rules/`)
- `registry.py` — decorator-based registration; `run_all()` executes every registered rule against a parsed
  message and aggregates `Finding`s.
- Rule groups, each a module: `structural.py`, `address.py`, `codes.py`, `amounts.py`, `agents.py`,
  `returns.py`.
- Rule ID families: `CBPR-STR-*`, `CBPR-ADDR-*`, `CBPR-COD-*`, `CBPR-AMT-*`, `CBPR-AGT-*`, `CBPR-RTN-*`.
- Headline rule: `CBPR-AGT-002` — the pacs.009 COV reimbursement-vs-intermediary agent distinction.
- Code-set checks (`codes.py`) validate against a committed, version-stamped snapshot of the ISO 20022
  External Code Sets (`codesets/loader.py` + `codesets/data/`), so validation is reproducible offline.

### 4.4 Correlation engine (`match/`)
- Separate from rules because it evaluates a relationship **between two messages**, not a property of one.
- `correlate(a, b, direction=None)` infers the scenario from the message-type pair (either argument order):
  - `CBPR-COR-001` pacs.009 COV ↔ originating pacs.008
  - `CBPR-COR-002` pacs.002 ↔ pacs.008 (`direction` **required** — identity is never inferred from BICs)
  - `CBPR-COR-003` pacs.004 return ↔ original pacs.008
- Primary match key is always **UETR**; `OrgnlTxId` / `OrgnlEndToEndId` are fallbacks only when a UETR is
  absent, and the result flags that fallback. Two UETRs that *disagree* are a real non-match, never a reason
  to try a weaker key.
- Output is `MatchResult` (distinct from `ValidationResult`; exposes `is_consistent`). (See ADR-005.)
- **v1 is deliberately pairwise and stateless** — you hand it the two messages to compare; there is no message
  store. (See ADR-004.)

### 4.5 Reporting (`report/`)
- Three formatters — `text_report.py`, `json_report.py`, `junit_report.py` — all fed from the same result
  objects.
- Only `ERROR` becomes a JUnit `<failure>`, so a CI build fails exactly when `is_compliant` / `is_consistent`
  is false. All emitted text is ASCII and XML-escaped, so a non-Latin party name or an `&` in a field can
  never corrupt or crash a report.

### 4.6 Optional XSD layer (`schema/xsd.py`)
- Off by default; enabled by pointing `CBPR_VALIDATE_XSD_DIR` at a **locally licensed** copy of the schemas.
- No schema is shipped or committed. If the layer is requested but a schema cannot be found, it raises rather
  than returning "clean" — the caller asked for structural validation, so silently skipping it would be a lie.

### 4.7 Interfaces
- **Library** (`core.py`): `validate_file` / `validate_string` / `validate_bytes`. These **never raise** —
  unreadable, malformed, and unrecognised inputs each return a `ValidationResult` carrying a single
  `ORCH-READ-ERROR` / `ORCH-PARSE-ERROR` / `ORCH-UNSUPPORTED` finding, so a caller has exactly one shape to
  handle. (See ADR-006.)
- **CLI** (`cli.py`, Typer): `validate`, `check`, `match`, `version`; `--format text|json|junit`,
  `--fail-on error|warn|never`, `--xsd`/`--xsd-dir`, and `--direction` for a pacs.002 pair. Exit codes are a
  stable contract: `0` clean, `1` findings at/above threshold (or a pair that does not correlate), `2`
  unusable input.
- **REST API** (`api/main.py`, FastAPI): `POST /validate`, `POST /correlate`, `GET /health`, OpenAPI at
  `/docs`. A correlation that fails is a `200` with `is_consistent: false` — a result, not an HTTP error; only
  unusable input is a `400`.
- Parity is **tested, not asserted** (`tests/test_interface_parity.py`): library, CLI, and API outputs are
  compared across the same messages and correlation scenarios.

---

## 5. Error-handling philosophy

<!-- TODO: you can tighten this, but the substance is real and worth stating explicitly — it's a maturity signal. -->
- **"Cannot evaluate" ≠ "not compliant".** Orchestration failures use an `ORCH-` prefix and are kept distinct
  from usage-guideline violations.
- **The library core never raises.** Every failure mode returns a `ValidationResult`, so callers integrate one
  contract.
- **Exit codes are an API.** The CLI's `0 / 1 / 2` contract is what lets the tool act as a CI gate.

---

## 6. Key design decisions (ADRs)

<!-- TODO: write these up as short ADRs under docs/adr/ (context → decision → consequences, ~1 page each).
This section is just the index. The four marked ★ are the ones the build plan told you not to skip. -->
- **ADR-001 ★** — Rules in code, not a rules DSL.
- **ADR-002 ★** — Do not ship SWIFT XSDs; cite sources, let users supply their own licensed copy.
- **ADR-003 ★** — An internal normalized (Pydantic) model to decouple rules from message version.
- **ADR-004 ★** — Correlation is pairwise/stateless in v1, not a stored ledger.
- **ADR-005** — `MatchResult` is a distinct type from `ValidationResult` (relationship vs. property).
- **ADR-006** — The library core never raises; orchestration errors are findings with an `ORCH-` prefix.

---

## 7. Extensibility — how to add a rule

<!-- TODO: verify the exact function signature against rules/registry.py before publishing. Seed: -->
1. Add a function to the relevant `rules/<group>.py`, register it with the registry decorator.
2. Return `Finding`s with a stable `rule_id`, a `severity`, a `location`, a `remediation`, and a
   `spec_reference` citing the guideline.
3. Add adversarial fixtures (a message that should fire it and one that should not) under `tests/`.
4. `run_all()` picks it up automatically — no interface change needed.

---

## 8. Testing strategy

- **192 tests, 99% coverage**, `ruff` and `mypy` clean. <!-- TODO: update these numbers when they change. -->
- **Adversarial fixtures**: every rule has both a clean case and a deliberately broken one (wrong UETR, amount
  drift, currency/party drift, mis-echoed references, missing mandatory fields).
- **Interface parity tests** guarantee library / CLI / API cannot silently diverge.
- CI (`.github/workflows/ci.yml`) gates lint, type-check, and tests on every change.

---

## 9. Scope & non-goals (v1)

**In scope:** `pacs.008`, `pacs.009` (core + COV), `pacs.002`, `pacs.004`; usage-guideline rules; External
Code Set checks; pairwise cross-message correlation; text/JSON/JUnit output.

**Out of scope (v1):** camt.05x / camt.110-111 (E&I); message *generation*; a stateful message store /
live-stream correlation; network/transport; redistribution of licensed schemas; proprietary regional schemes.

---

## 10. Performance

<!-- TODO: this is the one number you still owe the README/architecture doc. Run a quick benchmark
(N messages through validate_bytes in a loop, wall-clock) and state throughput here, e.g. "~X messages/sec
single-threaded on <machine>". It's a small task that signals you thought about scale. -->
_Benchmark: TODO._

---

## 11. Roadmap (v2)

camt.053/054 and camt.110/111 (E&I) · a hosted web playground · a reusable GitHub Action (CI step) · message
generation (pairs with the agentic project) · pluggable rule packs (HVPS+, regional) · a stateful
`MessageStore` so messages can be ingested one at a time (`ingest`) and correlations queried later (`query
--uetr ...`) instead of always pairwise.
