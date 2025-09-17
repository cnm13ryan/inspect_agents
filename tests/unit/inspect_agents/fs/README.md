# Filesystem Domain Tests

Tests for files tool and sandbox filesystem behaviors.

## Scope
This domain covers filesystem operations and sandboxing:
- Files tool functionality and safety
- Sandbox filesystem constraints and isolation
- File access permissions and validation
- Path resolution and security checks
- Filesystem operation logging and monitoring

## Common Fixtures
- Standard test environment fixtures from `tests/conftest.py`
- Temporary filesystem setups and sandboxes
- Mock file system structures
- File permission test helpers

## Selection Examples
```bash
# All filesystem tests
uv run pytest -q tests/unit/inspect_agents/fs

# Tests with specific keywords
uv run pytest -q tests/unit/inspect_agents/fs -k read
uv run pytest -q tests/unit/inspect_agents/fs -k write
uv run pytest -q tests/unit/inspect_agents/fs -k sandbox
uv run pytest -q tests/unit/inspect_agents/fs -k permissions

# Single test focus
uv run pytest -q tests/unit/inspect_agents/fs -k "read and not write"
```

## Related Docs
- [Tools & Filesystem Guide](../../docs/TESTING_TOOLS_FILESYSTEM.md)
