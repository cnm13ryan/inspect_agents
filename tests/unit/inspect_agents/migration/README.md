# Migration Domain Tests

Tests for legacy to deep agent migration path.

## Scope
This domain covers migration functionality between agent versions:
- Legacy agent compatibility and transition
- Deep agent migration paths and validation
- Backward compatibility testing
- Migration state management
- Configuration translation between versions

## Common Fixtures
- Standard test environment fixtures from `tests/conftest.py`
- Legacy agent simulators and mock configurations
- Migration state tracking helpers
- Version compatibility test data

## Selection Examples
```bash
# All migration tests
uv run pytest -q tests/unit/inspect_agents/migration

# Tests with specific keywords
uv run pytest -q tests/unit/inspect_agents/migration -k legacy
uv run pytest -q tests/unit/inspect_agents/migration -k compatibility
uv run pytest -q tests/unit/inspect_agents/migration -k transition
```

## Related Docs
- [Pytest Core Guide](../../docs/TESTING_PYTEST_CORE.md)
