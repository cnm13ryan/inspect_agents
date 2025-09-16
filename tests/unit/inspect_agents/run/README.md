# Run Domain Tests

Tests for run-related functionality and execution management.

## Scope
This domain covers agent execution and run management:
- Run lifecycle management and coordination
- Execution context setup and teardown
- Run state tracking and persistence
- Run result processing and validation
- Multi-run coordination and scheduling

## Common Fixtures
- Standard test environment fixtures from `tests/conftest.py`
- Mock execution environments and contexts
- Run state tracking helpers
- Result validation simulators

## Selection Examples
```bash
# All run tests
uv run pytest -q tests/unit/inspect_agents/run

# Tests with specific keywords
uv run pytest -q tests/unit/inspect_agents/run -k lifecycle
uv run pytest -q tests/unit/inspect_agents/run -k execution
uv run pytest -q tests/unit/inspect_agents/run -k state
uv run pytest -q tests/unit/inspect_agents/run -k results
```

## Related Docs
- [Pytest Core Guide](../../docs/TESTING_PYTEST_CORE.md)
