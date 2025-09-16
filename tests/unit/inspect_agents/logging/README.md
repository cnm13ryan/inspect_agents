# Logging Domain Tests

Tests for transcript generation and redaction logic.

## Scope
This domain covers logging and transcript functionality:
- Transcript generation and formatting
- Sensitive data redaction and sanitization
- Log level management and filtering
- Structured logging outputs
- Log persistence and retrieval

## Common Fixtures
- Standard test environment fixtures from `tests/conftest.py`
- Mock logging configurations and handlers
- Sample log data with sensitive content
- Transcript formatting helpers

## Selection Examples
```bash
# All logging tests
uv run pytest -q tests/unit/inspect_agents/logging

# Tests with specific keywords
uv run pytest -q tests/unit/inspect_agents/logging -k transcript
uv run pytest -q tests/unit/inspect_agents/logging -k redaction
uv run pytest -q tests/unit/inspect_agents/logging -k sensitive
```

## Related Docs
- [Pytest Core Guide](../../docs/TESTING_PYTEST_CORE.md) (includes logging patterns)
