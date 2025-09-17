# Tests — Quick Start

This is the front door to the test suite. It tells you where tests live, how to run fast subsets, and how the offline‑by‑default policy works. For complete guides, see the local docs index at [docs/README.md](docs/README.md).

## Directory Map
- `unit/` – fast, isolated tests for library behavior. Place new unit tests under `tests/unit/inspect_agents/<domain>/`.
  - Each domain has its own README with scope, fixtures, and selection examples. See [Domain READMEs](#domain-readmes) below.
- `integration/` – end‑to‑end flows and CLI/script coverage. Includes `integration/inspect_agents/` and `integration/examples/` for runnable scenarios.
- `examples/` – legacy/minimal wrappers; prefer `integration/examples/` for new work.
- `perf/` – opt‑in performance suites (uses the `benchmark` marker when available; runs as smoke when `pytest-benchmark` is absent).
- `fixtures/` – shared helpers, stubs, and test data.
- `docs/` – local testing guides (index: `tests/docs/README.md`).

## Offline by Default
- The suite runs offline by default by setting `NO_NETWORK=1` and disabling optional tools in a root autouse fixture (`tests/conftest.py`).
- Opt out for specific tests in two ways:
  - Add `@pytest.mark.network` to the test/function/module/class to allow real network.
  - Create a repository file named `.allow_network_in_tests` at repo root to allow network broadly during local runs.

Greppable identifiers: `NO_NETWORK`, `DEEPAGENTS_SHOW_TEST_GUIDES`, `pytest.mark.network`.

## Run Examples
- All tests, offline: `CI=1 NO_NETWORK=1 uv run pytest -q`
- Only unit tests: `uv run pytest -q tests/unit`
- Only integration examples: `uv run pytest -q tests/integration/examples`
- Keyword select: `uv run pytest -q -k truncation`
- By marker: `uv run pytest -q -m handoff tests/integration/inspect_agents`

## Docs You’ll Want
- Index: `tests/docs/README.md`
- Pytest core: `tests/docs/TESTING_PYTEST_CORE.md`
- Approvals & policies: `tests/docs/TESTING_APPROVALS_POLICIES.md`
- Parallel (xdist): `tests/docs/TESTING_PARALLEL.md`
- Limits & truncation: `tests/docs/TESTING_LIMITS_TRUNCATION.md`
- Tool timeouts: `tests/docs/TESTING_TOOL_TIMEOUTS.md`
- Tools & filesystem: `tests/docs/TESTING_TOOLS_FILESYSTEM.md`
- Model resolution: `tests/docs/TESTING_MODEL_RESOLUTION.md`

Tip: Pytest prints a one‑line pointer to the guides at session start (e.g., `guides: tests/docs/README.md`). To show guide hints locally on failures, export `DEEPAGENTS_SHOW_TEST_GUIDES=1`.

## Domain READMEs

Each major unit test domain has its own README with detailed scope, fixtures, and selection examples:

- [`unit/inspect_agents/approvals/`](unit/inspect_agents/approvals/README.md) – approval policies, handoff exclusivity, kill-switch
- [`unit/inspect_agents/config/`](unit/inspect_agents/config/README.md) – YAML loader + limits
- [`unit/inspect_agents/filters/`](unit/inspect_agents/filters/README.md) – input/output filters and quarantine modes
- [`unit/inspect_agents/fs/`](unit/inspect_agents/fs/README.md) – files tool + sandbox FS behaviors
- [`unit/inspect_agents/iterative/`](unit/inspect_agents/iterative/README.md) – iterative agent limits, productive time
- [`unit/inspect_agents/logging/`](unit/inspect_agents/logging/README.md) – transcript + redaction logic
- [`unit/inspect_agents/migration/`](unit/inspect_agents/migration/README.md) – legacy→deep agent migration path
- [`unit/inspect_agents/model/`](unit/inspect_agents/model/README.md) – model resolution + role mapping
- [`unit/inspect_agents/observability/`](unit/inspect_agents/observability/README.md) – observability and monitoring
- [`unit/inspect_agents/planner/`](unit/inspect_agents/planner/README.md) – planning functionality
- [`unit/inspect_agents/profiles/`](unit/inspect_agents/profiles/README.md) – profiles management
- [`unit/inspect_agents/run/`](unit/inspect_agents/run/README.md) – run-related functionality
- [`unit/inspect_agents/schema/`](unit/inspect_agents/schema/README.md) – pydantic models, typed results
- [`unit/inspect_agents/state/`](unit/inspect_agents/state/README.md) – store-backed state shims
- [`unit/inspect_agents/tools/`](unit/inspect_agents/tools/README.md) – tool schemas, observability, todos tool
