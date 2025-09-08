"""CI-friendly pytest hooks that surface testing guides on failures.

This prints a short pointer to repo-local testing guides when the test session
has failures, making it easy for contributors and CI logs to link to the
appropriate docs. It is intentionally lightweight and has zero effect on
outcomes or exit codes.

Behavior:
- Always include a one-line header pointing to tests/docs/README.md.
- When failures occur, emit a small section with relevant guide file paths
  inferred from failing node ids (e.g., approvals, handoffs, timeouts,
  truncation, parallel, model resolution).
- Only activates in CI (CI=1) or when DEEPAGENTS_SHOW_TEST_GUIDES is truthy.
"""

from __future__ import annotations

import importlib.util as _importlib_util
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from pathlib import Path as _Path

import pytest

# Ensure src/ (and optional external/inspect_ai) are importable for tests
# This avoids requiring an editable install in local runs/CI.
_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
_SRC = _REPO_ROOT / "src"
_EXT_INSPECT = _REPO_ROOT / "external" / "inspect_ai"
for _p in (_EXT_INSPECT, _SRC):
    try:
        if _p.exists():
            pstr = str(_p)
            if pstr not in sys.path:
                sys.path.insert(0, pstr)
    except Exception:
        # Never fail test collection due to path setup
        pass


def _truthy(v: str | None) -> bool:
    return bool(v) and str(v).strip().lower() in {"1", "true", "yes", "on"}


ROOT = Path(__file__).resolve().parent
# Docs live under tests/docs
DOCS_DIR = ROOT / "docs"

GUIDE_INDEX = DOCS_DIR / "README.md"

GUIDES = {
    "approvals": DOCS_DIR / "TESTING_APPROVALS_POLICIES.md",
    "handoff": DOCS_DIR / "TESTING_SUBAGENTS_HANDOFFS.md",
    "subagent": DOCS_DIR / "TESTING_SUBAGENTS_HANDOFFS.md",
    "filters": DOCS_DIR / "TESTING_SUBAGENTS_HANDOFFS.md",
    "kill_switch": DOCS_DIR / "TESTING_APPROVALS_POLICIES.md",
    "timeout": DOCS_DIR / "TESTING_TOOL_TIMEOUTS.md",
    "tool_timeouts": DOCS_DIR / "TESTING_TOOL_TIMEOUTS.md",
    "truncation": DOCS_DIR / "TESTING_LIMITS_TRUNCATION.md",
    "parallel": DOCS_DIR / "TESTING_PARALLEL.md",
    "runner_model": DOCS_DIR / "TESTING_MODEL_RESOLUTION.md",
    "model_flags": DOCS_DIR / "TESTING_MODEL_RESOLUTION.md",
    "mock": DOCS_DIR / "TESTING_MOCKING.md",
    "benchmark": DOCS_DIR / "TESTING_BENCHMARKS.md",
    "async": DOCS_DIR / "TESTING_ASYNC.md",
}


def _guides_for_nodeid(nodeid: str) -> set[Path]:
    s = nodeid.lower()
    out: set[Path] = set()
    for key, path in GUIDES.items():
        if key in s:
            out.add(path)
    return out


# Capture markers during collection so we can map failures to guides precisely
_NODE_MARKS: dict[str, set[str]] = {}


def pytest_collection_modifyitems(items):  # pragma: no cover - wiring only
    for item in items:
        try:
            marks = {m.name for m in item.iter_markers()}
        except Exception:
            marks = set()
        _NODE_MARKS[item.nodeid] = marks


def pytest_report_header(config):  # pragma: no cover - cosmetic
    # One-line pointer at session start; always useful
    return [f"guides: {GUIDE_INDEX}"]


def _failed_reports(terminalreporter) -> Iterable[object]:
    try:
        return terminalreporter.stats.get("failed", [])
    except Exception:
        return []


def pytest_terminal_summary(terminalreporter, exitstatus, config):  # pragma: no cover - formatting only
    if not (_truthy(os.getenv("CI")) or _truthy(os.getenv("DEEPAGENTS_SHOW_TEST_GUIDES"))):
        return

    failed = list(_failed_reports(terminalreporter))
    if not failed:
        return

    guides: set[Path] = set()
    for rep in failed:
        nodeid = getattr(rep, "nodeid", "")
        # Prefer markers if present
        marks = _NODE_MARKS.get(nodeid, set())
        for m in marks:
            p = GUIDES.get(m)
            if p:
                guides.add(p)
        # Fallback to keyword heuristics
        if not marks:
            guides.update(_guides_for_nodeid(nodeid))

    # Always include the index
    # Prefer reporter API for broad compatibility with plugins
    try:
        terminalreporter.write_sep("=", "DeepAgents test guides")
    except Exception:
        terminalreporter.write_line("========== DeepAgents test guides ==========")
    terminalreporter.write_line(f"Index: {GUIDE_INDEX}")

    if guides:
        terminalreporter.write_line("Relevant:")
        for p in sorted(guides):
            terminalreporter.write_line(f"- {p}")
    else:
        terminalreporter.write_line("No specific match; see the index above.")


# ----------------------------------------------------------------------
# Optional plugin shims
# ----------------------------------------------------------------------

"""Optional plugin shims.

Provide a minimal no-op 'benchmark' fixture when pytest-benchmark is absent.
This keeps benchmark tests runnable in environments that don't install the
optional plugin, treating them as functional smoke checks.
"""

_HAS_PYTEST_BENCHMARK = _importlib_util.find_spec("pytest_benchmark") is not None

if not _HAS_PYTEST_BENCHMARK:  # pragma: no cover - exercised only when plugin missing
    import pytest

    @pytest.fixture
    def benchmark():
        """Fallback benchmark fixture that simply executes the function.

        Usage compatibility:
            benchmark(lambda: some_fn())
        Returns the function's return value; no timing/stats are recorded.
        """

        def _runner(func, *args, **kwargs):
            return func(*args, **kwargs) if callable(func) else func

        return _runner

    def pytest_configure(config):  # pragma: no cover - cosmetic marker registration
        # Register the 'benchmark' marker to avoid unknown-mark warnings when
        # the real plugin isn't installed.
        try:
            config.addinivalue_line("markers", "benchmark: no-op when pytest-benchmark is unavailable")
        except Exception:
            pass

# Guard/cleanup fixture for approval-related tests that stub inspect_ai modules
# and register global approvers. Ensures isolation across tests.


@pytest.fixture
def approval_modules_guard():  # pragma: no cover - test support only
    import sys as _sys

    # Remember originals and clear stubs before running
    _mod_names = [
        "inspect_ai.approval._approval",
        "inspect_ai.approval._policy",
        "inspect_ai._util.registry",
        "inspect_ai.tool._tool_call",
    ]
    _saved = {name: _sys.modules.get(name) for name in _mod_names}
    for name in _mod_names:
        _sys.modules.pop(name, None)

    # Clear any registered approver
    try:
        from inspect_ai.approval._apply import init_tool_approval  # type: ignore

        init_tool_approval(None)  # type: ignore[func-returns-value]
    except Exception:
        pass

    try:
        yield
    finally:
        # Restore modules and clear approver again
        for name, mod in _saved.items():
            if mod is None:
                _sys.modules.pop(name, None)
            else:
                _sys.modules[name] = mod
        try:
            from inspect_ai.approval._apply import init_tool_approval  # type: ignore

            init_tool_approval(None)  # type: ignore[func-returns-value]
        except Exception:
            pass


# Managed guard for tool stub modules to prevent cross-test leakage.
# Provides automatic teardown even if a test aborts early.
@pytest.fixture
def tool_modules_guard(monkeypatch):  # pragma: no cover - test support only
    import sys as _sys

    targets = [
        "inspect_ai.tool._tools._text_editor",
        "inspect_ai.tool._tools._bash_session",
    ]
    saved = {t: _sys.modules.get(t) for t in targets}
    # Ensure a clean slate before the test runs
    for t in targets:
        _sys.modules.pop(t, None)

    try:
        yield
    finally:
        # Restore prior state deterministically
        for t, mod in saved.items():
            if mod is None:
                _sys.modules.pop(t, None)
            else:
                _sys.modules[t] = mod


# Minimal asyncio runner shim: if pytest-asyncio isn't installed, execute
# coroutine tests marked with @pytest.mark.asyncio using asyncio.run.
def pytest_pyfunc_call(pyfuncitem):  # pragma: no cover - passthrough logic
    import inspect as _inspect

    try:
        return None  # Defer to plugin if present
    except Exception:
        pass

    test_fn = pyfuncitem.obj
    if _inspect.iscoroutinefunction(test_fn):
        # Only handle when explicitly marked asyncio to avoid surprises
        if pyfuncitem.get_closest_marker("asyncio") is None:
            return None
        import asyncio as _asyncio

        # Build kwargs from resolved fixtures
        argnames = getattr(pyfuncitem._fixtureinfo, "argnames", ())
        kwargs = {name: pyfuncitem.funcargs[name] for name in argnames}
        _asyncio.run(test_fn(**kwargs))
        return True
    return None


# ----------------------------------------------------------------------
# Default Env Guard (autouse)
# ----------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _default_env_guard(monkeypatch, request):
    """Harden env for all tests by default.

    - Disable optional heavy tools (web_search/exec/browser/editor).
    - Unset common provider keys to prevent auto-enabling.
    - Default to offline (`NO_NETWORK=1`) unless opted-out.

    Opt-out mechanisms:
    - Marker `@pytest.mark.network` on a test/function/module/class.
    - Presence of a repository file `.allow_network_in_tests` at repo root.

    Individual tests can still override via their own `monkeypatch` calls.
    """
    # Best-effort: clear any previously-registered approvals
    try:  # pragma: no cover - shim may not exist in all environments
        from inspect_ai.approval._apply import init_tool_approval  # type: ignore

        init_tool_approval(None)  # type: ignore[func-returns-value]
    except Exception:
        pass

    # Disable optional tools to keep init deterministic across the suite
    monkeypatch.setenv("INSPECT_ENABLE_WEB_SEARCH", "0")
    monkeypatch.setenv("INSPECT_ENABLE_EXEC", "0")
    monkeypatch.setenv("INSPECT_ENABLE_WEB_BROWSER", "0")
    monkeypatch.setenv("INSPECT_ENABLE_TEXT_EDITOR_TOOL", "0")

    # Unset provider keys that would auto-enable web_search
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CSE_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CSE_API_KEY", raising=False)

    # Offline by default; allow opt-out via marker or escape-hatch file
    repo_root = _Path(__file__).resolve().parents[1]
    allow_file = repo_root / ".allow_network_in_tests"
    has_network_marker = bool(request.node.get_closest_marker("network"))
    if allow_file.exists() or has_network_marker:
        monkeypatch.delenv("NO_NETWORK", raising=False)
    else:
        monkeypatch.setenv("NO_NETWORK", "1")


# Ensure tests that stub out Inspect's call_tools module don't leak state.
# Some tests replace `inspect_ai.model._call_tools` in `sys.modules` without
# automatic restoration. This guard captures the original module reference and
# restores it after each test to prevent order-dependent failures in suites
# that expect real tool execution (e.g., handoff prescan tests).
@pytest.fixture(autouse=True)
def _call_tools_module_guard():  # pragma: no cover - test infrastructure
    import sys as _sys

    name = "inspect_ai.model._call_tools"
    saved = _sys.modules.get(name)
    try:
        yield
    finally:
        if saved is None:
            _sys.modules.pop(name, None)
        else:
            _sys.modules[name] = saved


def pytest_configure(config):  # pragma: no cover - cosmetic marker registration
    # Ensure common markers are known regardless of optional plugins
    try:
        config.addinivalue_line("markers", "benchmark: present even if pytest-benchmark is unavailable")
    except Exception:
        pass
    try:
        config.addinivalue_line("markers", "network: allow real network for this test")
    except Exception:
        pass
    # Register repo markers used for selection/guides to avoid unknown-mark warnings
    for _m in [
        "approvals",
        "handoff",
        "filters",
        "kill_switch",
        "timeout",
        "truncation",
        "parallel",
        "model_flags",
    ]:
        try:
            config.addinivalue_line("markers", f"{_m}: repository-defined test marker")
        except Exception:
            pass


# Optional dependency shim for `jsonlines` managed via fixture to ensure cleanup.
@pytest.fixture(autouse=True, scope="session")
def jsonlines_stub():  # pragma: no cover - test support only
    try:
        import jsonlines as _jsonlines  # type: ignore  # noqa: F401

        yield  # Real package present; nothing to stub
        return
    except Exception:
        pass

    import json
    import sys as _sys
    import types as _types

    _jl = _types.ModuleType("jsonlines")

    class _Reader:
        def __init__(self, fp):
            self._fp = fp

        def iter(self, type=dict):  # noqa: A002 - match third‑party API
            for line in self._fp:
                try:
                    yield json.loads(line)
                except Exception:
                    continue

    _jl.Reader = _Reader  # type: ignore[attr-defined]
    _saved = _sys.modules.get("jsonlines")
    _sys.modules["jsonlines"] = _jl
    try:
        yield
    finally:
        if _saved is None:
            _sys.modules.pop("jsonlines", None)
        else:
            _sys.modules["jsonlines"] = _saved
