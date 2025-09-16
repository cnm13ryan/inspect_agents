# Filters Domain Tests

Tests for input/output filters and quarantine modes.

## Scope
This domain covers filtering mechanisms that process agent inputs and outputs:
- Input filtering and validation
- Output filtering and sanitization
- Quarantine modes for unsafe content
- Filter chain processing and configuration
- Content policy enforcement

## Common Fixtures
- Standard test environment fixtures from `tests/conftest.py`
- Mock filter configurations and policies
- Sample content for filtering tests
- Quarantine state simulators

## Selection Examples
```bash
# All filter tests
uv run pytest -q tests/unit/inspect_agents/filters

# Tests with specific keywords
uv run pytest -q tests/unit/inspect_agents/filters -k quarantine
uv run pytest -q tests/unit/inspect_agents/filters -k input
uv run pytest -q tests/unit/inspect_agents/filters -k output

# By marker
uv run pytest -q -m filters tests/unit/inspect_agents/filters
```

## Related Docs
- [Filters Guide](../../docs/TESTING_FILTERS.md)
