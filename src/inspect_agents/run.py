from __future__ import annotations

import asyncio
import contextlib
import os
from typing import Any

from .observability import log_tool_event
from .profiles import resolve_profile_from_env


async def run_agent(
    agent: Any,
    input: str | list[Any],
    approval: list[Any] | None = None,
    limits: list[Any] | None = None,
    return_limit_error: bool = False,
    raise_on_limit: bool = False,
):
    """Run an agent and optionally propagate limit errors.

    By default this returns only the agent state. When Inspect returns a
    `(state, err)` tuple (e.g., when limits are supplied), you can opt in to
    propagation semantics:

    - If `return_limit_error` is True and a tuple is received, return
      `(state, err)` instead of dropping the error.
    - If `raise_on_limit` is True and `err` is not None, re-raise the error.

    This preserves backward compatibility when both flags are left as False.
    """
    # Normalize optional args to avoid mutable default pitfalls
    # (ensure each call gets its own list instance)
    limits = [] if limits is None else limits

    if approval:
        try:
            from inspect_ai.approval._apply import init_tool_approval  # type: ignore

            init_tool_approval(approval)
        except Exception:
            # If approval initialization isn't available in test stubs, continue.
            pass
    else:
        # Optional env-activated presets when no explicit approvals are supplied
        # INSPECT_APPROVAL_PRESET=ci|dev|prod
        preset = (os.getenv("INSPECT_APPROVAL_PRESET") or "").strip().lower()
        if preset in {"ci", "dev", "prod"}:
            try:
                from .approval import activate_approval_policies, approval_preset

                activate_approval_policies(approval_preset(preset))
            except Exception:
                # Safe no-op if approval wiring is unavailable in the environment
                pass

    # Resolve optional sandboxing profile from env (INSPECT_PROFILE=T?.H?.N?)
    # Applies tool toggles as defaults and emits an audit event. If a profile is
    # present, also set INSPECT_EVAL_SANDBOX=<provider> as a convenience for
    # upstream CLI paths; programmatic callers should still pass Task(..., sandbox=...).
    try:
        prof = resolve_profile_from_env()
        if prof is not None:
            os.environ.setdefault("INSPECT_EVAL_SANDBOX", prof.sandbox)
    except Exception:
        # Profiles are advisory; never fail the run if parsing or logging fails.
        pass

    # Guard: some tests install a minimal inspect_ai.approval._apply stub that
    # lacks `have_tool_approval` expected by newer Inspect. Patch it in before
    # importing Inspect internals to avoid ImportError during import-time wiring.
    try:  # pragma: no cover - exercised in integration tests
        import sys as _sys

        _apply = _sys.modules.get("inspect_ai.approval._apply")
        if _apply is not None and not hasattr(_apply, "have_tool_approval"):
            setattr(_apply, "have_tool_approval", lambda: bool(getattr(_apply, "_POLICIES", None)))
    except Exception:
        pass

    # Import submodule directly to bypass stubbed package __init__ in tests
    from inspect_ai.agent._run import run as agent_run  # type: ignore

    # --- Limit‑nearing telemetry (runner time budgets) ---
    # If a runner time limit exists, schedule a single, cancellable timer to
    # emit an "info" event before the limit is exceeded.
    def _parse_threshold_env() -> float:
        raw = os.getenv("INSPECT_LIMIT_NEARING_THRESHOLD", "")
        try:
            val = float(str(raw).strip()) if raw else 0.8
        except Exception:
            val = 0.8
        # Clamp to (0, 1); default to 0.8 if out of range
        return val if 0.0 < val < 1.0 else 0.8

    def _extract_time_limit_seconds(items: list[Any]) -> float | None:
        """Return the runner time limit in seconds, if present.

        Tries to detect Inspect's internal _TimeLimit type first; otherwise falls
        back to a conservative heuristic (float-valued limit without a 'check()').
        If multiple time limits are present, returns the smallest positive one.
        """
        if not items:
            return None
        candidates: list[float] = []
        # Prefer explicit type checks when available
        _TimeLimitType: Any | None = None  # noqa: N806
        try:  # Inspect exports the internal class symbol from the module
            from inspect_ai.util._limit import _TimeLimit as _TL  # type: ignore

            _TimeLimitType = _TL  # noqa: N806
        except Exception:
            _TimeLimitType = None  # noqa: N806

        for it in items:
            try:
                if _TimeLimitType is not None and isinstance(it, _TimeLimitType):
                    limit_val = getattr(it, "limit", None)
                else:
                    # Heuristic: time limits have float limits and no 'check()'
                    limit_val = getattr(it, "limit", None)
                    if not isinstance(limit_val, (float, int)):
                        continue
                    # Exclude token/message/working which expose a check()
                    if hasattr(it, "check"):
                        continue
                if isinstance(limit_val, (float, int)):
                    limit_f = float(limit_val)
                    if limit_f > 0:
                        candidates.append(limit_f)
            except Exception:
                continue

        return min(candidates) if candidates else None

    _near_task: asyncio.Task[None] | None = None
    _time_limit = _extract_time_limit_seconds(limits)
    if _time_limit is not None and _time_limit > 0:
        _threshold = _parse_threshold_env()
        _delay = _threshold * float(_time_limit)

        async def _emit_after_delay(delay_s: float, limit_s: float) -> None:
            try:
                await asyncio.sleep(delay_s)
                try:
                    log_tool_event(
                        name="limits",
                        phase="info",
                        extra={
                            "event": "limit_nearing",
                            "scope": "runner",
                            "kind": "time",
                            "threshold": float(limit_s),
                            "used": float(delay_s),
                        },
                    )
                except Exception:
                    # Observability must never affect control flow
                    pass
            except asyncio.CancelledError:
                # Expected on early completion paths
                return

        _near_task = asyncio.create_task(_emit_after_delay(_delay, float(_time_limit)))

    try:
        result = await agent_run(agent, input, limits=limits)
    finally:
        # Ensure timer is cancelled on any exit path to avoid stray logs
        if _near_task is not None:
            _near_task.cancel()
            with contextlib.suppress(Exception):
                await _near_task

    # Inspect returns a tuple when limits are provided; otherwise it's the state
    if isinstance(result, tuple):
        state, err = result

        # Emit a structured event when a limit error is returned
        if err is not None:
            try:
                extra: dict[str, Any] = {
                    "scope": "runner",
                    "error_type": type(err).__name__,
                }
                # Optionally enrich when attributes are available
                for attr in ("kind", "threshold", "used"):
                    try:
                        value = getattr(err, attr)
                    except Exception:
                        value = None
                    if value is not None:
                        extra[attr] = value
                log_tool_event(name="limits", phase="error", extra=extra)
            except Exception:
                # Never let observability interfere with control flow
                pass

        # Optionally raise when a limit error occurred
        if raise_on_limit and err is not None:
            # `err` is expected to be an Exception (e.g., LimitExceededError)
            # Raise it directly to preserve type and traceback
            raise err

        # Optionally return the `(state, err)` tuple to the caller
        if return_limit_error:
            return state, err

        # Backward-compat: default to returning state only
        return state

    return result
