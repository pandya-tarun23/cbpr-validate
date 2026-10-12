# Changelog

All notable changes to this project are documented here. This project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-10-12

### Changed — BEHAVIOUR CHANGE, please read

**Unstructured postal addresses are now reported as `WARN`, not `ERROR`, by
default. A message that was `NOT COMPLIANT` in 1.1.0 may now be `COMPLIANT`,
and a CLI call that exited `1` may now exit `0`.**

`CBPR-ADDR-001` (unstructured-only address) and `CBPR-ADDR-002` (TownName and
Country required) are the two affected rules. Nothing else changed severity.

**To restore the previous strict behaviour, select the `sr2026` profile:**

```bash
cbpr-validate validate payment.xml --profile sr2026    # exits 1, as 1.1.0 did
```

```python
validate_file("payment.xml", profile="sr2026")         # is_compliant False, as 1.1.0
```

```bash
curl -d '{"message": "...", "profile": "sr2026"}' localhost:8000/validate
```

Alternatively keep the default profile and tighten the gate instead, which
fails the build on the readiness gap while still reporting it as a warning:

```bash
cbpr-validate validate payment.xml --fail-on warn      # exits 1 on a WARN
```

**Why.** SWIFT deferred every payments change in Standards Release 2026,
including the removal of fully unstructured postal addresses in CBPR+
(originally 14 Nov 2026). **A new date has not been confirmed.** The network
accepts these addresses today, so reporting them as hard errors overstated the
position: it told users their live, working traffic was non-compliant. They are
now a visible readiness gap by default, and a rejection only when you ask for
the future rulebook.

### Added

- **Severity profiles.** `current` (the new default) and `sr2026`. A profile is
  a flat `rule_id -> severity` mapping applied once after the rules run; no
  rule's detection logic is profile-aware.
  - CLI: `--profile current|sr2026` on `validate` and `check`.
  - Library: `profile=` on `validate_file`, `validate_string`, `validate_bytes`
    and `rules.registry.run_all`.
  - API: optional `"profile"` field on `POST /validate`.
  - An unknown profile name is an input error: CLI exit `2` (listing the valid
    names), API `422`, `ValueError` from the library.
- **`Finding.base_severity`** — the severity the rule itself declared, always
  populated. `severity != base_severity` means the active profile moved that
  finding, i.e. it is an SR2026 readiness gap.
- **`ValidationResult.profile`** records which rulebook produced the verdict,
  and `.overridden` lists the findings the profile moved.
- The profile is surfaced by every reporter: a `(profile: ...)` suffix on the
  text summary (plus an `N SR2026 address gaps` note when any fired), a
  top-level `"profile"` field in JSON, and a `<property name="profile">` in
  JUnit.
- `--fail-on` now accepts both `warn` and `warning` on **both** `validate` and
  `check`. Previously `check` accepted only `warn` and `validate` only
  `warning`, and the other spelling exited `2`. Both old spellings still work.

### Notes

- JUnit still maps only `ERROR` to `<failure>`, so under the default profile an
  address gap no longer fails a build. Use `--profile sr2026` or
  `--fail-on warn` if you want it to.
- No new dependencies. No rule's detection logic changed.

## [1.1.0] - 2026-09-27

### Added

- `CBPR-ADDR-006` — `AdrLine` length and count validation (`Max70Text`,
  `maxOccurs=7`).
- `ARCHITECTURE.md`.

### Fixed

- `CBPR-AMT-001/002` — currency validated against the full ISO 4217 list, with
  decimal-place checking separated from validity.

## [1.0.0] - 2026-09

### Added

- Initial release: version-agnostic payment model; `pacs.008`, `pacs.009`
  (core + COV), `pacs.002` and `pacs.004` parsers; the structural, address,
  code-set, amount, agent and return rule groups; pairwise correlation
  (`CBPR-COR-001/002/003`); the Typer CLI, FastAPI service and text/JSON/JUnit
  reporters; and the optional XSD layer.
