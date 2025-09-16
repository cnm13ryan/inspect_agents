# State Domain Tests

Tests for store-backed state shims and management.

## Scope
This domain covers state management and persistence:
- Store-backed state implementation and validation
- State persistence and retrieval mechanisms
- State synchronization and consistency
- State shim layer functionality
- State transaction handling

## Common Fixtures
- Standard test environment fixtures from `tests/conftest.py`
- Mock state stores and persistence layers
- State synchronization test helpers
- Transaction simulation utilities

## Selection Examples
```bash
# All state tests
uv run pytest -q tests/unit/inspect_agents/state

# Tests with specific keywords
uv run pytest -q tests/unit/inspect_agents/state -k persistence
uv run pytest -q tests/unit/inspect_agents/state -k synchronization
uv run pytest -q tests/unit/inspect_agents/state -k transaction
```

## Related Docs
- [Pytest Core Guide](../../docs/TESTING_PYTEST_CORE.md)
