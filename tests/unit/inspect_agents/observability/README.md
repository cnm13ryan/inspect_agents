# Observability Domain Tests

Tests for observability and monitoring functionality.

## Scope
This domain covers monitoring and observability features:
- Metrics collection and reporting
- Performance monitoring and profiling
- Health checks and system status
- Telemetry data processing
- Observability configuration and setup

## Common Fixtures
- Standard test environment fixtures from `tests/conftest.py`
- Mock metrics collectors and reporters
- Observability configuration helpers
- Performance measurement simulators

## Selection Examples
```bash
# All observability tests
uv run pytest -q tests/unit/inspect_agents/observability

# Tests with specific keywords
uv run pytest -q tests/unit/inspect_agents/observability -k metrics
uv run pytest -q tests/unit/inspect_agents/observability -k monitoring
uv run pytest -q tests/unit/inspect_agents/observability -k telemetry
```

## Related Docs
- [Pytest Core Guide](../../docs/TESTING_PYTEST_CORE.md)
