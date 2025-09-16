# test(fs): sandbox preflight TTL caches warnings

import asyncio
import logging
import sys
import time
import types


def test_sandbox_preflight_ttl_warn_once_within_ttl(monkeypatch, caplog, tool_modules_guard):
    """ensure_sandbox_ready emits a single warning log within the TTL window.

    We simulate an unavailable sandbox by stubbing
    inspect_ai.tool._tool_support_helpers.tool_support_sandbox to raise. With
    INSPECT_SANDBOX_PREFLIGHT=auto and a short TTL, two calls within the TTL
    should produce exactly one structured warning log line.
    """

    # Import target module symbols
    from inspect_agents.fs import (
        ensure_sandbox_ready,
        reset_sandbox_preflight_cache,
    )

    # Ensure clean slate for cache
    reset_sandbox_preflight_cache()

    # Environment: auto mode, tiny TTL
    monkeypatch.setenv("INSPECT_SANDBOX_PREFLIGHT", "auto")
    monkeypatch.setenv("INSPECT_SANDBOX_PREFLIGHT_TTL_SEC", "1")

    # Make sure no in-process tool stubs short-circuit availability
    sys.modules.pop("inspect_ai.tool._tools._text_editor", None)
    sys.modules.pop("inspect_ai.tool._tools._bash_session", None)

    # Provide a stub module that raises to simulate unavailability
    mod_name = "inspect_ai.tool._tool_support_helpers"
    stub = types.ModuleType(mod_name)

    async def tool_support_sandbox(_name: str):  # pragma: no cover - trivial
        raise RuntimeError("sandbox unavailable")

    stub.tool_support_sandbox = tool_support_sandbox  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, mod_name, stub)

    # Capture logs from the fs module
    caplog.set_level(logging.INFO, logger="inspect_agents.fs")

    # First call: should log once and return False
    t0 = time.monotonic()
    ok1 = asyncio.run(ensure_sandbox_ready("editor"))
    assert ok1 is False

    # Second call within TTL: should be cached; no additional log
    ok2 = asyncio.run(ensure_sandbox_ready("editor"))
    assert ok2 is False

    # Filter for our structured tool_event warn payloads
    warn_logs = [rec for rec in caplog.records if "files:sandbox_preflight" in rec.getMessage()]
    assert len(warn_logs) == 1, "exactly one warning should be emitted within TTL"

    # Sanity: still within TTL window
    assert (time.monotonic() - t0) < 1.0
