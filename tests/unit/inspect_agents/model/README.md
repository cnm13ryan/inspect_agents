# Model Domain Tests

Tests for model resolution and role mapping.

## Scope
This domain covers model-related functionality:
- Model resolution and selection logic
- Role mapping and permission assignment
- Model fallback and retry mechanisms
- Model source configuration and validation
- Model label and flag management
- Generation retry timing and arguments

## Common Fixtures
- Standard test environment fixtures from `tests/conftest.py`
- Mock model configurations and providers
- Model resolution test helpers
- Role mapping simulators

## Selection Examples
```bash
# All model tests
uv run pytest -q tests/unit/inspect_agents/model

# Tests with specific keywords
uv run pytest -q tests/unit/inspect_agents/model -k resolution
uv run pytest -q tests/unit/inspect_agents/model -k fallback
uv run pytest -q tests/unit/inspect_agents/model -k retry
uv run pytest -q tests/unit/inspect_agents/model -k roles

# By marker
uv run pytest -q -m model_flags tests/unit/inspect_agents/model

# Single test files
uv run pytest -q tests/unit/inspect_agents/model/test_model_resolver.py
uv run pytest -q tests/unit/inspect_agents/model/test_generate_with_retry_time_args.py
```

## Related Docs
- [Model Resolution Guide](../../docs/TESTING_MODEL_RESOLUTION.md)
