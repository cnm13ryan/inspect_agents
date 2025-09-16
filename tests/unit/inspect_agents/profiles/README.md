# Profiles Domain Tests

Tests for profiles management and configuration.

## Scope
This domain covers profile-related functionality:
- Profile creation and management
- Profile configuration validation
- Profile switching and activation
- Profile inheritance and overrides
- Profile-specific settings and behaviors

## Common Fixtures
- Standard test environment fixtures from `tests/conftest.py`
- Mock profile configurations
- Profile validation helpers
- Profile state management simulators

## Selection Examples
```bash
# All profiles tests
uv run pytest -q tests/unit/inspect_agents/profiles

# Tests with specific keywords
uv run pytest -q tests/unit/inspect_agents/profiles -k config
uv run pytest -q tests/unit/inspect_agents/profiles -k validation
uv run pytest -q tests/unit/inspect_agents/profiles -k switching
```

## Related Docs
- [Pytest Core Guide](../../docs/TESTING_PYTEST_CORE.md)
