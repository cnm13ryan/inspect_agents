# Schema Domain Tests

Tests for Pydantic models and typed results.

## Scope
This domain covers data modeling and validation:
- Pydantic model definitions and validation
- Type checking and schema enforcement
- Serialization and deserialization
- Schema migration and compatibility
- Typed result structures and processing

## Common Fixtures
- Standard test environment fixtures from `tests/conftest.py`
- Mock data structures and validation scenarios
- Schema validation helpers
- Type checking simulators

## Selection Examples
```bash
# All schema tests
uv run pytest -q tests/unit/inspect_agents/schema

# Tests with specific keywords
uv run pytest -q tests/unit/inspect_agents/schema -k validation
uv run pytest -q tests/unit/inspect_agents/schema -k serialization
uv run pytest -q tests/unit/inspect_agents/schema -k types
```

## Related Docs
- [Pytest Core Guide](../../docs/TESTING_PYTEST_CORE.md)
