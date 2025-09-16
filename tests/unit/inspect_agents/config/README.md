# Config Domain Tests

Tests for YAML configuration loading and limits parsing.

## Scope
This domain covers configuration management including:
- YAML configuration file loading and validation
- Limits configuration and parsing
- Settings management and validation
- Configuration deprecation handling
- Alias resolution for limit settings

## Common Fixtures
- Standard test environment fixtures from `tests/conftest.py`
- Mock configuration files and YAML structures
- Settings validation helpers

## Selection Examples
```bash
# All config tests
uv run pytest -q tests/unit/inspect_agents/config

# Tests with specific keywords
uv run pytest -q tests/unit/inspect_agents/config -k yaml
uv run pytest -q tests/unit/inspect_agents/config -k limits
uv run pytest -q tests/unit/inspect_agents/config -k settings
uv run pytest -q tests/unit/inspect_agents/config -k deprecations

# Single test files
uv run pytest -q tests/unit/inspect_agents/config/test_config_loader.py
uv run pytest -q tests/unit/inspect_agents/config/test_yaml_limits.py
```

## Related Docs
- [Limits & Truncation Guide](../../docs/TESTING_LIMITS_TRUNCATION.md)
