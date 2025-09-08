# TODO — Testing Infra: Resilient pytest parallel default (xdist optional)

Context & Motivation
- Purpose: Ensure `pytest` runs cleanly for local developers without `pytest-xdist` while keeping parallel execution as the default in CI. This reduces onboarding friction and avoids errors like `pytest: error: unrecognized arguments: -n` when xdist isn’t installed.
- Problem: `pyproject.toml` sets `addopts = "-q -n auto --maxfail=1"`. When `pytest-xdist` is missing, `pytest` fails to start due to the unknown `-n` option.
- Impact: Lowers the barrier to running tests locally; avoids support churn; preserves fast CI.
- Constraints: Do not slow down CI, which already installs `.[testing]` (includes `pytest-xdist`). Retain ability to override parallelism (`-n 0` for constrained jobs).

Implementation Guidance
- Files to examine
  - `pyproject.toml` → `[tool.pytest.ini_options].addopts` (contains `-n auto`).
  - `.github/workflows/tests.yml` → test invocations already accept a matrix var `pytest_n`; default is `""`, but addopts injects `-n auto` implicitly.
- Greppable identifiers: `addopts`, `-n auto`, `pytest_xdist`, `pytest_n`.

- Options (choose one)
  1) CI-only parallel (recommended simple path)
     - Change: Remove `-n auto` from `pyproject.toml` addopts (keep `-q --maxfail=1`).
     - Update workflows: Set matrix default to `pytest_n: ["-n auto"]` (or set `PYTEST_ADDOPTS`), and keep explicit `-n 0` lanes for constrained jobs.
     - Pros: Trivial to reason about; no dynamic hooks; local runs degrade gracefully.
  2) Conditional enable (plugin present → parallel)
     - Add a light hook in `tests/conftest.py` that appends `-n auto` only when `importlib.util.find_spec("xdist")` is truthy and the command line didn’t pass `-n`.
     - Pros: One place to manage behavior; works in both local + CI.
     - Cons: Slight indirection; needs careful merge with existing addopts.
  3) CI config file
     - Keep `pyproject.toml` minimal (no `-n`), and add a CI-only `pytest.ini` (in workflow checkout) that sets `addopts = -q -n auto --maxfail=1`.
     - Pros: Fully isolates CI behavior.
     - Cons: Two sources of truth unless documented clearly.

Scope Definition
- Implement one option above; avoid changes to test bodies.
- Files likely to modify: `pyproject.toml`, `.github/workflows/tests.yml` (and optionally `benchmarks.yml` if it assumes addopts semantics).
- Focus on developer UX and CI determinism; avoid altering markers, paths, or coverage settings.

Success Criteria
- Local: `pytest` runs without error when xdist is not installed (serial by default).
- CI: Tests run in parallel by default; lanes can still set `-n 0` when needed.
- Documentation: Update testing guide to mention parallel default in CI and how to opt in/out locally (`pip install pytest-xdist`, `pytest -n auto`, `-n 0`).

Task Checklist
- [ ] Remove `-n auto` from `pyproject.toml` addopts or make it conditional.
- [ ] Update `.github/workflows/tests.yml` to pass `-n auto` (matrix default) or `PYTEST_ADDOPTS` in CI.
- [ ] Verify `pytest` runs locally without xdist and in CI with parallelism.
- [ ] Update `tests/docs/README.md` or a testing guide with guidance for local parallel runs and overrides.
