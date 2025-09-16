# Tools Domain Tests

Tests for tool schemas, observability, and todos tool functionality.

## Scope
This domain covers tool-related functionality:
- Tool schema definition and validation
- Tool observability and monitoring
- Todos tool implementation and features
- Tool error handling and codes
- Tool wrapper functionality and deprecations
- Tool output limits and policies

## Common Fixtures
- Standard test environment fixtures from `tests/conftest.py`
- Mock tool definitions and schemas
- Tool execution simulators
- Error handling test helpers

## Selection Examples
```bash
# All tools tests
uv run pytest -q tests/unit/inspect_agents/tools

# Tests with specific keywords
uv run pytest -q tests/unit/inspect_agents/tools -k schema
uv run pytest -q tests/unit/inspect_agents/tools -k observability
uv run pytest -q tests/unit/inspect_agents/tools -k todos
uv run pytest -q tests/unit/inspect_agents/tools -k error

# Single test files
uv run pytest -q tests/unit/inspect_agents/tools/test_tool_schema.py
uv run pytest -q tests/unit/inspect_agents/tools/test_todos_tool.py
uv run pytest -q tests/unit/inspect_agents/tools/test_tool_error_codes.py
```

## Related Docs
- [Tools & Filesystem Guide](../../docs/TESTING_TOOLS_FILESYSTEM.md)
- [Tool Timeouts Guide](../../docs/TESTING_TOOL_TIMEOUTS.md)
