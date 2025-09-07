"""Shared test helpers for approvals shim, event parsing, and vendor path.

These helpers deduplicate common glue used across integration and unit tests.
"""

from __future__ import annotations

import json
import sys
import types
from collections.abc import Iterable
from typing import Any


def ensure_vendor_on_path() -> None:
    """Prepend vendored Inspect-AI source to `sys.path` if missing.

    Ensures tests import Inspect-AI modules from `external/inspect_ai/src` for
    consistent behavior independent of any globally installed packages.
    """

    vendor_src = "external/inspect_ai/src"
    if vendor_src not in sys.path:
        sys.path.insert(0, vendor_src)


def build_apply_shim(monkeypatch) -> types.ModuleType:
    """Install a lightweight shim for `inspect_ai.approval._apply`.

    Provides `init_tool_approval(policies)` and `apply_tool_approval(...)` with
    simple pattern matching on `call.function`. This mirrors the ad-hoc shim
    used across tests so that approval policies can be exercised end-to-end
    without coupling to upstream internals.
    """

    import fnmatch

    mod_name = "inspect_ai.approval._apply"
    apply_mod = types.ModuleType(mod_name)

    _compiled: list[tuple[list[str], object]] = []

    def init_tool_approval(policies: Iterable[object] | None) -> None:  # pragma: no cover - wiring
        nonlocal _compiled
        compiled: list[tuple[list[str], object]] = []
        if policies:
            for p in policies:
                tools = getattr(p, "tools", "*")
                approver = getattr(p, "approver", None)
                patterns = tools if isinstance(tools, list) else [tools]
                compiled.append((patterns, approver))
        _compiled = compiled

    async def apply_tool_approval(message: str, call: Any, viewer: Any, history: list[Any]):
        approver = None
        if _compiled:
            for patterns, ap in _compiled:
                for pat in patterns:
                    pat = pat if pat.endswith("*") else pat + "*"
                    if fnmatch.fnmatch(getattr(call, "function", ""), pat):
                        approver = ap
                        break
                if approver:
                    break
        if approver is None:

            class _Approval:
                decision = "approve"
                modified = None
                explanation = None

            return True, _Approval()
        view = viewer(call) if callable(viewer) else None
        approval = await approver(message, call, view, history)  # type: ignore[misc]
        allowed = getattr(approval, "decision", None) in ("approve", "modify")
        return allowed, approval

    apply_mod.init_tool_approval = init_tool_approval  # type: ignore[attr-defined]
    apply_mod.apply_tool_approval = apply_tool_approval  # type: ignore[attr-defined]

    # Install/replace module using pytest monkeypatch when available
    monkeypatch.setitem(sys.modules, mod_name, apply_mod)
    return apply_mod


def parse_tool_events(caplog) -> list[dict[str, Any]]:
    """Parse repo-local `tool_event` JSON payloads from a `caplog` fixture.

    Returns a list of dict payloads extracted from log records whose message
    starts with `"tool_event "` followed by a JSON object.
    """

    events: list[dict[str, Any]] = []
    for rec in getattr(caplog, "records", []):
        try:
            msg = rec.getMessage()
        except Exception:
            continue
        if not (isinstance(msg, str) and msg.startswith("tool_event ")):
            continue
        try:
            payload = json.loads(msg.split("tool_event ", 1)[1])
        except Exception:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events
