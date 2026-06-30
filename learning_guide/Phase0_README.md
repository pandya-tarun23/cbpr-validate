# Phase 0 — Step-by-Step: How the Skeleton Was Built

Phase 0's goal per `BUILD_PLAN.md`: a green CI pipeline on `main`, with package layout and tooling in place but no real validation logic yet.

This document walks through exactly what was done, in order, including the two real issues hit along the way and how they were resolved.

---

## 1. Decide where the project lives

The build plan describes `cbpr-validate` as a standalone, PyPI-publishable open-source library — distinct from the `payments_llm` prototype repo it grew out of. Decision: create a **new, separate repo** at `C:\Users\tarun\cbpr-validate`, rather than nesting it inside `payments_llm`.

Also decided: write the CI workflow file now, but defer creating the GitHub remote/pushing until later — verify everything locally first.

## 2. Create the directory skeleton

```bash
mkdir -p src/cbpr_validate/{parsers,model,rules,codesets,schema,report,api} tests .github/workflows
```

This mirrors the architecture in `BUILD_PLAN.md` §3 — one subpackage per concern (parsers, model, rules, codesets, schema, report, api), so each is independently testable later.

## 3. Write `pyproject.toml`

Single source of truth for build config, dependencies, and every tool:

- **`[build-system]`** — `hatchling`.
- **`[project]`** — name, version `0.1.0`, `requires-python = ">=3.11"`, runtime deps (`pydantic`, `lxml`, `typer`, `fastapi`, `uvicorn`, `httpx`).
- **`[project.optional-dependencies] dev`** — `pytest`, `pytest-cov`, `ruff`, `mypy`.
- **`[project.scripts]`** — `cbpr-validate = "cbpr_validate.cli:main"` (entry point for the future CLI).
- **`[tool.ruff]`**, **`[tool.mypy]`** (`strict = true`), **`[tool.pytest.ini_options]`**, **`[tool.coverage.run]`** — config for every quality gate in one file.

## 4. Add the package skeleton

- `src/cbpr_validate/__init__.py` — just `__version__ = "0.1.0"`.
- `src/cbpr_validate/cli.py` — a real (not fake) Typer app with one working command (`version`), proving the CLI entry point actually wires up.
- Empty `__init__.py` in `parsers/`, `model/`, `rules/`, `codesets/`, `schema/`, `report/`, `api/` — just enough to mark them as packages. Deliberately **no** stub logic (e.g. no placeholder `config.py`) — half-finished modules would violate the "no half-finished implementations" rule and add nothing Phase 0 actually needs.

## 5. Add tests

- `tests/conftest.py` — empty for now; shared fixtures arrive in Phase 1 once there are real messages to parse.
- `tests/test_smoke.py` — two tests: package import sets `__version__`, and the CLI's `version` command runs and prints it.

## 6. Add supporting files

- `.gitignore` — standard Python ignores (`__pycache__/`, `.venv/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `dist/`, etc.).
- `README.md` — minimal stub (status: Phase 0, points at `BUILD_PLAN.md`); gets real polish in Phase 6.
- `BUILD_PLAN.md` — copied over from the original `payments_llm/cbpr-validate_BUILD_PLAN.md` so the plan lives with the code it describes.
- `.github/workflows/ci.yml` — on push/PR to `main`, matrix over Python 3.11/3.12/3.13: checkout → setup-python → `pip install -e ".[dev]"` → `ruff check .` → `mypy src` → `pytest`.

## 7. Initialize git

```bash
git init -b main
```

## 8. Verify everything locally before trusting CI

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -e ".[dev]"
ruff check .       # passed
mypy src           # passed
pytest             # FAILED — see issue below
```

### Issue hit: smoke test failed on CLI invocation

`runner.invoke(app, ["version"])` returned exit code 2 ("Got unexpected extra argument(s)"). Root cause: **Typer collapses a single-command app into one top-level command** — when only one `@app.command()` is registered, there's no subcommand layer at all yet, so the CLI is invoked as `cbpr-validate` (no `version` argument), not `cbpr-validate version`. Confirmed directly:

```bash
python -m cbpr_validate.cli   # -> prints "0.1.0", no subcommand needed
```

This isn't a bug — it's expected Typer behavior that will naturally change once a second command (`check`, in Phase 5) is added and the app becomes a real multi-command group. **Fix:** updated the test to invoke with no args (`runner.invoke(app, [])`) to match the actual current CLI surface. Re-ran `pytest` — 2 passed.

## 9. Commit

```bash
git add -A
git commit -m "Phase 0: project skeleton with CI"
```

(One near-miss here: a `git add -A` was first run from the wrong working directory — the shell's cwd had reset to `payments_llm` between conversation turns — and staged unrelated files there. Caught via `git status` before committing, unstaged with `git restore --staged`, and re-ran from the confirmed `cbpr-validate` directory. Lesson: always confirm `pwd` before git operations in a fresh shell turn.)

## 10. Create the GitHub remote and push

No `gh` CLI was installed, so:

```powershell
winget install --id GitHub.cli -e --source winget --accept-source-agreements --accept-package-agreements
```

(First attempt without `--source winget` failed — winget tried the `msstore` source too and hit a certificate error querying it. Pinning `--source winget` avoided that.)

Authentication needs an interactive browser flow that can't be driven from a non-interactive tool, so this step required the user to run, in their own terminal:

```
gh auth login
```

(GitHub.com → HTTPS → Y → "Login with a web browser", paste the device code, approve in browser.)

Once `gh auth status` confirmed login, the repo was created from the existing local repo and pushed:

```powershell
gh repo create pandya-tarun23/cbpr-validate --public --source=. --remote=origin --description "..."
git push -u origin main
```

## 11. Confirm CI is actually green on GitHub

```powershell
gh run watch <run-id> --exit-status
```

Result: `test (3.11)`, `test (3.12)`, `test (3.13)` all passed — lint, type-check, and tests, on every targeted Python version. That's the Phase 0 Definition of Done from `BUILD_PLAN.md` §9: **green CI on `main`**.

Repo: https://github.com/pandya-tarun23/cbpr-validate

---

## Key takeaways

- **Skeleton ≠ stub everything.** Only `cli.py` got real (if minimal) logic; the rest of the subpackages are empty `__init__.py` markers — there was no validation logic to write yet, so nothing was faked.
- **Verify locally before trusting CI.** Running ruff/mypy/pytest in a local venv caught the Typer single-command bug before it ever reached GitHub Actions.
- **A failing test can mean the test is wrong, not the code.** The Typer collapse behavior was a framework default, not a defect — the fix was correcting the test's assumption about the CLI surface, not the `cli.py` implementation.
- **Always re-confirm `pwd` before destructive-adjacent git commands** (`add`, `commit`) in a fresh shell turn — working directory does not reliably persist across conversation turns.
