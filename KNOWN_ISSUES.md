# Known issues and deferred work

Gaps found while building a phase that were deliberately left out of scope
rather than silently expanded into it (CLAUDE.md operating rule 7). Each entry
says what it is, why it was deferred, and what it would take.

---

## 1. No batch / folder readiness summary

**What.** There is no way to point the tool at a directory of messages and get
an aggregate readiness report ("412 messages, 38 with SR2026 address gaps,
across 6 debtor BICs"). Today you validate one message per invocation and
aggregate the JSON yourself.

**Why deferred.** Out of scope for the severity-profiles change, which is about
*which rulebook* a single message is judged against. Batch reporting is a
separate concern with its own design questions — output shape, grouping keys,
memory behaviour on large folders, partial-failure semantics — and bolting a
loop onto the CLI would pre-empt those choices badly.

**What it would take.** A new `cbpr-validate scan <dir>` command, an aggregate
result type (counts and groupings, not a concatenated `ValidationResult`), and
a reporter for it. The per-message path needs no changes.

---

## 2. No TOML config overrides

**What.** Profiles are the only way to change a severity, and the profile table
is in code (`src/cbpr_validate/profiles.py`). A bank cannot supply its own
`cbpr-validate.toml` declaring, say, that `CBPR-RTN-004` is an ERROR in their
environment.

**Why deferred.** Deliberate for now. A committed profile table is auditable
and reproducible: a finding's severity is a property of the released version,
not of whatever file happened to be on the machine. User-supplied overrides
need answers on precedence, validation of unknown rule IDs, and provenance in
the report (a result would have to record *which* config produced it) before
they are safe to add.

**What it would take.** A loader producing the same `rule_id -> severity`
mapping shape `profiles.py` already uses, layered over the selected profile,
plus provenance recorded on `ValidationResult` so a report can say where a
severity came from. The override mechanism itself would not change.

---

## 3. `check` bypasses `core`, so there are two roads to the rules

**What.** The documented design is "one shared core", but two different paths
exist:

| | Road A | Road B |
| --- | --- | --- |
| Used by | library `validate_*`, CLI `validate` | CLI `check`, API `POST /validate` |
| Entry | `core.validate_bytes` | caller reads and parses for itself |
| Bad input | an `ORCH-*` ERROR finding, never raises | CLI exit 2 / HTTP 400 |

So `check` and the API do not get `core`'s no-raise orchestration contract, and
error handling for an unreadable or unrecognised document differs between
`validate` and `check`.

**Why deferred.** Unifying them is a refactor of the CLI and API error paths
with its own behaviour changes (exit codes and HTTP statuses would move for
malformed input), and it is unrelated to severity profiles. It was safe to
leave alone here because the profile override lives in
`rules.registry.run_all()` — the one function *both* roads pass through — so
every interface already agrees on what a profile means.

**Guard in place.** `tests/test_interface_parity.py::test_check_and_validate_agree_on_the_verdict`
pins that `check` and `validate` return the same verdict and the same JSON for
the same profile, so the divergence cannot quietly widen while it remains.

**What it would take.** Route `check` and the API through `core.validate_bytes`,
then decide deliberately whether a malformed document should be an `ORCH-*`
finding (exit 1) or an input error (exit 2) — and change the documented exit-code
contract to match whichever is chosen.

---

## 4. `CBPR-ADDR-003` is unregistered

**What.** The hybrid-address line-count cap is implemented nowhere; the rule ID
is reserved and the function is not registered.

**Why deferred.** The cap value is ambiguous in the public CBPR+ guideline
material available, and guessing a threshold would produce confident-looking
wrong findings (CLAUDE.md operating rule 3). Note this is distinct from
`CBPR-ADDR-006`, which enforces the two caps that *are* unambiguous because
they come from the ISO 20022 schema itself (`Max70Text`, `maxOccurs=7`).

**What it would take.** Confirmation of the cap from the usage guidelines, then
a registered rule plus a passing and an adversarial fixture.
