# Testing Guide — Filters

Focus: input/output filter modules, quarantine behaviors, and marker hygiene for filter-tagged tests.

## What to verify
- Default filters strip tool/system content before handing user inputs to agents.
- Output filters redact sensitive tokens and enforce maximum message lengths.
- Quarantine modes reroute blocked messages and emit structured audit logs.
- Filters markers (`@pytest.mark.filters`) pair with mocks to keep runs deterministic.

## Patterns
- Import filters via `from inspect_agents import filters` to exercise public entry points.
- Use `default_input_filter()` / `default_output_filter()` to mirror production wiring in tests.
- Patch env toggles like `INSPECT_FILTERS_QUARANTINE` with `monkeypatch` per test to avoid leakage.
- Capture logs with `caplog` targeting `inspect_agents.filters` for quarantine assertions.

## Tips
- Combine filters with handoff fixtures by explicitly setting `input_filter`/`output_filter` arguments.
- Keep payloads small; large snapshots trigger truncation checks unrelated to filters.
- Validate quarantine payloads with structured comparisons (`json.loads`) instead of substring matching.
- When stubbing filters, reset module-level registries in teardowns to prevent cross-test failures.

## Debugging failures
- If CI prints this guide, re-run locally with `pytest -q -m filters` to isolate scope.
- Use `CI=1 NO_NETWORK=1` to mirror the offline CI environment for reproducibility.
- For quarantine issues, enable `INSPECT_FILTERS_DEBUG=1` to surface verbose trace logs.
- For unexpected message shapes, print `state.messages` before/after filter application to spot leaks.
