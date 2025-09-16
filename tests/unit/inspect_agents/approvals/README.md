# Approvals Domain Tests

Tests for approval policies, handoff exclusivity, and kill-switch functionality.

## Scope
This domain covers the approval system that controls when and how agents can perform certain actions, including:
- Approval policies and their enforcement
- Handoff exclusivity mechanisms
- Kill-switch functionality for stopping agent execution
- Policy validation and configuration

## Common Fixtures
- Standard test environment fixtures from `tests/conftest.py`
- Approval policy mock configurations
- Agent handoff state simulators

## Selection Examples
```bash
# All approval tests
uv run pytest -q tests/unit/inspect_agents/approvals

# Tests with specific keywords
uv run pytest -q tests/unit/inspect_agents/approvals -k policy
uv run pytest -q tests/unit/inspect_agents/approvals -k handoff
uv run pytest -q tests/unit/inspect_agents/approvals -k kill

# By marker
uv run pytest -q -m approvals tests/unit/inspect_agents/approvals
uv run pytest -q -m handoff tests/unit/inspect_agents/approvals
```

## Related Docs
- [Approvals & Policies Guide](../../docs/TESTING_APPROVALS_POLICIES.md)
- [Subagents & Handoffs Guide](../../docs/TESTING_SUBAGENTS_HANDOFFS.md)
