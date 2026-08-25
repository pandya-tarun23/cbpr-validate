# CLAUDE.md — cbpr-validate

Persistent context for Claude Code. Read this at the start of every session
before doing anything. `BUILD_PLAN.md` is the authoritative roadmap; this file
is the operating manual.

## What this project is

`cbpr-validate` — a production-grade, open-source Python library (+ CLI + API,
later phases) that validates ISO 20022 CBPR+ payment messages against the
**usage guidelines**, not just the XSD. The core thesis, stated everywhere:
**XSD-valid ≠ CBPR+-compliant.** This is a job-search portfolio piece for a
senior payments architect role, so the *engineering signal* (clean history,
traceable rules, honest gaps) matters as much as the functionality.

## Current status

Phases 0–4.5 are complete and on `main`, verified green.
- Phase 0: skeleton + CI.
- Phase 1: version-agnostic Pydantic model, `pacs.008` parser, `detect.py`.
- Phase 2: rule registry (`run_all`), address rule group.
- Phase 3: codes/amounts/structural rules + committed ISO 20022 code-set
  snapshot loader (`codesets/loader.py`, `codesets/data/iso20022_codesets.json`).
- Phase 4: `pacs.009` (core + COV), `pacs.002`, `pacs.004` parsers; `agents.py`
  (incl. the headline `CBPR-AGT-002` COV rule) and `returns.py`.
- Phase 4.5: pairwise correlation engine (`match/matcher.py`, `match/result.py`)
  — `CBPR-COR-001/002/003`, keyed on UETR with a flagged legacy fallback.

**Next: Phase 5** (CLI + FastAPI + JSON/text/JUnit reporters, optional XSD layer).

## Carried-over decisions — do NOT re-litigate

- `CBPR-ADDR-003` (hybrid line-count cap) is **intentionally unregistered** —
  the cap is ambiguous in available guideline material and we refuse to guess.
  Leave it unregistered until the cap is confirmed.
- `CBPR-COD-004` now runs against a real parsed `pacs.002`; the Phase 3
  direct-construction workaround was removed in Phase 4. Done — don't revisit.
- Correlation returns `MatchResult`, **not** `ValidationResult`, and lives
  outside `run_all()`. It is pairwise and stateless by design; a stateful
  `MessageStore` is v2, not a gap to close.
- `direction` is **required** for the `pacs.002 ↔ pacs.008` correlation and has
  no default. The tool must never infer whose message it is from BICs.

## Operating rules (these are non-negotiable)

1. **One commit/PR per phase.** The README + BUILD_PLAN status updates ride in
   the *same* commit as that phase's code. Never squash two phases together —
   the git history reading as deliberate, phase-by-phase engineering is a
   deliberate portfolio signal.
2. **Every rule needs BOTH a passing fixture AND an adversarial fixture** that
   asserts the correct `rule_id` and `severity`. A passing-only test
   *demonstrates* a rule; it does not *test* it. This is the single most
   common gap — do not repeat it.
3. **Never guess an ambiguous threshold.** If a spec value is unclear, either
   leave the rule unregistered (like ADDR-003) or pick the *conservative*
   interpretation and document the choice in a code comment. Flag it to the
   user. Do not silently hard-code an uncertain number.
4. **Never commit SWIFT XSDs or copied CBPR+/SR2026 guideline text.** Implement
   rules in your own code; cite the source in `spec_reference` only. Public ISO
   code sets (e.g. in `codesets/data/`) ARE fine to commit.
5. **Reuse the committed code-set snapshot.** Do not re-fetch or duplicate
   code-set data at runtime. Rules read the committed snapshot.
6. **Respect phase boundaries.** Through Phase 4, every rule evaluates a
   SINGLE message. Cross-message correlation is Phase 4.5 ONLY. CLI/API is
   Phase 5 ONLY. If you catch yourself cross-referencing two messages or
   building an interface before then, stop — it's the next phase.
7. **Stay in scope for the current phase.** If you find an out-of-scope gap,
   log it in `KNOWN_ISSUES.md` rather than expanding scope.
8. **Definition of done for any phase:** all listed rules implemented AND
   registered; adversarial tests present; `pytest` green; coverage ≥ 90% on
   new modules; ruff + mypy clean; README + BUILD_PLAN updated; one commit.

## Tech stack

Python 3.11+, Pydantic v2, lxml, Typer (CLI, Phase 5), FastAPI (API, Phase 5),
pytest + pytest-cov, ruff, mypy.

## Commands (run inside the venv)

```bash
pip install -e .
pip install pytest pytest-cov ruff mypy
python -m pytest -q            # run tests
python -m ruff check src tests # lint  (use `python -m ruff`, not bare `ruff`)
python -m mypy src             # types
```

## Workflow expectation

Work the current phase from its `/goal` prompt. Build parsers before the rules
that depend on them. Run the full suite after each change. Only declare a phase
done when every DoD criterion above is independently verified, and show the
final pytest + coverage output plus the list of new rule_ids with severities.
