# Planner Domain Tests

Tests for planning functionality and algorithms.

## Scope
This domain covers agent planning capabilities:
- Planning algorithm implementation and validation
- Plan generation and optimization
- Planning state management
- Plan execution coordination
- Planning constraint handling

## Common Fixtures
- Standard test environment fixtures from `tests/conftest.py`
- Mock planning scenarios and environments
- Plan validation helpers
- Planning state simulators

## Selection Examples
```bash
# All planner tests
uv run pytest -q tests/unit/inspect_agents/planner

# Tests with specific keywords
uv run pytest -q tests/unit/inspect_agents/planner -k algorithm
uv run pytest -q tests/unit/inspect_agents/planner -k generation
uv run pytest -q tests/unit/inspect_agents/planner -k execution
```

## Related Docs
- [Pytest Core Guide](../../docs/TESTING_PYTEST_CORE.md)
