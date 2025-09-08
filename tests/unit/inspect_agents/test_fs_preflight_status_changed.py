"""test(fs): sandbox preflight status-change events

Validates that ensure_sandbox_ready emits one structured `status_changed`
tool_event when sandbox availability flips up and down, and does not emit
duplicates when the status remains unchanged within a recheck window.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
import types

from tests.fixtures.helpers import parse_tool_events


def test_sandbox_preflight_status_changed_up_then_down(monkeypatch, caplog, tool_modules_guard):
    # Import target symbols
    from inspect_agents.fs import ensure_sandbox_ready, reset_sandbox_preflight_cache

    # Clean cache and force re-evaluation on every call
    reset_sandbox_preflight_cache()
    monkeypatch.setenv("INSPECT_SANDBOX_PREFLIGHT", "auto")
    monkeypatch.setenv("INSPECT_SANDBOX_PREFLIGHT_TTL_SEC", "0")

    # Ensure no in-process stubs that would short-circuit to available=True
    sys.modules.pop("inspect_ai.tool._tools._text_editor", None)
    sys.modules.pop("inspect_ai.tool._tools._bash_session", None)

    # Install stubbed helper module whose behavior we can flip
    mod_name = "inspect_ai.tool._tool_support_helpers"
    stub = types.ModuleType(mod_name)

    async def _fail(_name: str):  # pragma: no cover - trivial
        raise RuntimeError("sandbox unavailable")

    async def _ok(_name: str):  # pragma: no cover - trivial
        return "ok"

    stub.tool_support_sandbox = _fail  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, mod_name, stub)

    # Capture structured logs from fs module
    caplog.set_level(logging.INFO, logger="inspect_agents.fs")

    # 1) Start unavailable (no status_changed from None -> False)
    ok = asyncio.run(ensure_sandbox_ready("editor"))
    assert ok is False

    # 2) Flip to available (expect exactly one status_changed: False -> True)
    stub.tool_support_sandbox = _ok  # type: ignore[attr-defined]
    ok2 = asyncio.run(ensure_sandbox_ready("editor"))
    assert ok2 is True

    # 3) Stable available again (no new status_changed)
    ok3 = asyncio.run(ensure_sandbox_ready("editor"))
    assert ok3 is True

    # 4) Flip back to unavailable (expect exactly one status_changed: True -> False)
    stub.tool_support_sandbox = _fail  # type: ignore[attr-defined]
    ok4 = asyncio.run(ensure_sandbox_ready("editor"))
    assert ok4 is False

    # 5) Stable unavailable again (no new status_changed)
    ok5 = asyncio.run(ensure_sandbox_ready("editor"))
    assert ok5 is False

    # Parse and filter events
    events = [e for e in parse_tool_events(caplog) if e.get("tool") == "files:sandbox_preflight"]
    flips = [e for e in events if e.get("phase") == "status_changed"]

    # Expect exactly two flips: up then down
    assert len(flips) == 2, flips
    assert flips[0].get("old") is False and flips[0].get("new") is True, flips[0]
    assert flips[1].get("old") is True and flips[1].get("new") is False, flips[1]


def test_sandbox_preflight_status_changed_respects_ttl(monkeypatch, caplog, tool_modules_guard):
    # Import target symbols
    from inspect_agents.fs import ensure_sandbox_ready, reset_sandbox_preflight_cache

    reset_sandbox_preflight_cache()
    monkeypatch.setenv("INSPECT_SANDBOX_PREFLIGHT", "auto")
    # Small positive TTL so within-window calls are cached
    # Choose a TTL large enough to avoid accidental expiry due to test overhead
    monkeypatch.setenv("INSPECT_SANDBOX_PREFLIGHT_TTL_SEC", "2.0")

    sys.modules.pop("inspect_ai.tool._tools._text_editor", None)
    sys.modules.pop("inspect_ai.tool._tools._bash_session", None)

    mod_name = "inspect_ai.tool._tool_support_helpers"
    stub = types.ModuleType(mod_name)

    async def _fail(_name: str):  # pragma: no cover - trivial
        raise RuntimeError("sandbox unavailable")

    async def _ok(_name: str):  # pragma: no cover - trivial
        return "ok"

    stub.tool_support_sandbox = _fail  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, mod_name, stub)

    caplog.set_level(logging.INFO, logger="inspect_agents.fs")

    # Start unavailable (no status_changed from None -> False)
    assert asyncio.run(ensure_sandbox_ready("editor")) is False

    # Flip underlying helper to available, but within TTL should return cached False
    stub.tool_support_sandbox = _ok  # type: ignore[attr-defined]
    assert asyncio.run(ensure_sandbox_ready("editor")) is False

    # After TTL expires, recheck should flip to True and emit one status_changed
    time.sleep(2.5)
    assert asyncio.run(ensure_sandbox_ready("editor")) is True

    # Within TTL, still True and no additional flip
    assert asyncio.run(ensure_sandbox_ready("editor")) is True

    # Flip underlying helper back to failure; wait for TTL to expire before recheck
    stub.tool_support_sandbox = _fail  # type: ignore[attr-defined]
    time.sleep(2.5)
    assert asyncio.run(ensure_sandbox_ready("editor")) is False

    events = [e for e in parse_tool_events(caplog) if e.get("tool") == "files:sandbox_preflight"]
    flips = [e for e in events if e.get("phase") == "status_changed"]

    # Exactly two flips total (up once after TTL; down once after TTL)
    assert len(flips) == 2, flips
    assert flips[0].get("old") is False and flips[0].get("new") is True, flips[0]
    assert flips[1].get("old") is True and flips[1].get("new") is False, flips[1]
