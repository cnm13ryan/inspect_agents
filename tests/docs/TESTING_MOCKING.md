# Testing Guide — Mocking (pytest-mock)

Use `pytest-mock` for clean, scoped mocking and spying.

## Patterns
- Patch attributes: `mocker.patch('pkg.mod.attr', new=...)` or `mocker.patch.object(obj, 'name', ...)`.
- Spies: `spy = mocker.spy(obj, 'method')`; assert `spy.call_count`, `spy.call_args`.
- Autospeccing: prefer to patch concrete functions/attrs rather than whole modules where possible.

## Use-Site Patching Helper
- Prefer patching at the use site with signature checks via `tests/fixtures/patching.py`:
  ```python
  from tests.fixtures.patching import patch_use_site

  # Enforce callable signature (autospec=True by default)
  def _exclusive() -> list[str]:
      return ["EXCLUSIVE_SENTINEL"]

  with patch_use_site(
      "inspect_agents.approval.handoff_exclusive_policy",
      new=_exclusive,
  ):
      ...  # code under test
  ```
- Behavior:
  - If `new` is provided and target is callable, the helper wraps it in an autospecced proxy to catch signature drift (raises `TypeError` on mismatch).
  - Set `autospec=False` for dynamic attributes or intentionally loose call contracts: `patch_use_site("pkg.mod.attr", new=impl, autospec=False)`.

## Scope & Cleanup
- Mocks are automatically undone after each test; avoid manual teardown.
- For heavy module stubs (e.g., `inspect_ai.approval._apply`), install module objects in `sys.modules` inside the test and remove them after if they’re not test-scoped (see approval tests for patterns).

## Examples
- Spy and patch example:
  ```python
  def test_log_tool_event_spy(mocker):
      import inspect_agents.tools as tools
      spy = mocker.spy(tools, "_log_tool_event")
      tools._log_tool_event(name="x", phase="start")
      assert spy.call_count == 1

  def test_patch_env_flag(mocker):
      import os
      mocker.patch.dict(os.environ, {"INSPECT_AGENTS_TYPED_RESULTS": "1"}, clear=False)
      from inspect_agents.tools import _use_typed_results
      assert _use_typed_results() is True
  ```

## References
- pytest-mock usage.
