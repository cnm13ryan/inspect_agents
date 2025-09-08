"""Consolidated filesystem and sandbox utilities.

This module centralizes helpers previously duplicated across tools modules:
- Mode/root/bytes/timeouts/truthy helpers
- Sandbox preflight with TTL cache + reset API
- Symlink denial and root-confinement path validation

Design goals:
- Dependency-light (only stdlib + anyio + optional inspect_tool_support types)
- No import cycles with local modules (does not import .tools or .tools_files)
- Preserve existing behaviors/messages used by callers when adopted
"""

from __future__ import annotations

import os
import time
import warnings

import anyio

# --- Exceptions ---------------------------------------------------------------
from .exceptions import ToolException

# --- Truthy/Config helpers ----------------------------------------------------
from .settings import truthy  # single source of truth


def fs_mode() -> str:
    """Return filesystem mode: 'store' (default) or 'sandbox'."""

    return os.getenv("INSPECT_AGENTS_FS_MODE", "store").strip().lower()


def use_sandbox_fs() -> bool:
    """True when sandbox filesystem mode is active."""

    return fs_mode() == "sandbox"


def default_tool_timeout() -> float:
    """Default per-tool timeout in seconds (env: INSPECT_AGENTS_TOOL_TIMEOUT, default 15)."""

    try:
        return float(os.getenv("INSPECT_AGENTS_TOOL_TIMEOUT", "15"))
    except Exception:
        return 15.0


def fs_root() -> str:
    """Absolute filesystem root path used to confine sandbox operations.

    Controlled by `INSPECT_AGENTS_FS_ROOT` (default: "/repo"). Ensures the
    returned value is absolute.
    """

    root = os.getenv("INSPECT_AGENTS_FS_ROOT", "/repo")
    if not os.path.isabs(root):
        root = os.path.abspath(root)
    return root


def max_bytes() -> int:
    """Maximum allowed file size in bytes (env: INSPECT_AGENTS_FS_MAX_BYTES, default 5_000_000)."""

    try:
        return int(os.getenv("INSPECT_AGENTS_FS_MAX_BYTES", "5000000"))
    except Exception:
        return 5_000_000


# --- Sandbox preflight (cached) ----------------------------------------------

_SANDBOX_READY: bool | None = None
_SANDBOX_WARN: str | None = None
_SANDBOX_TS: float | None = None  # monotonic seconds of last evaluation


def reset_sandbox_preflight_cache() -> None:
    """Reset cached sandbox preflight result and warning.

    Clears the module-level cache (result, warning, TTL timestamp) so that the
    next call to `ensure_sandbox_ready` re-evaluates preflight regardless of TTL.
    Intended for tests and operator workflows.
    """

    global _SANDBOX_READY, _SANDBOX_WARN, _SANDBOX_TS
    _SANDBOX_READY = None
    _SANDBOX_WARN = None
    _SANDBOX_TS = None


async def ensure_sandbox_ready(tool_name: str) -> bool:
    """Return True if the Inspect sandbox service is available for `tool_name`.

    Behavior mirrors the existing implementation in tools_files with:
    - Modes via INSPECT_SANDBOX_PREFLIGHT: auto|skip|force (default auto)
    - TTL cache via INSPECT_SANDBOX_PREFLIGHT_TTL_SEC (default 300 seconds)
    - In-process stub detection for unit tests (text_editor/bash_session)
    - Optional warning log payload when service is unavailable
    - In 'force' mode, raises ToolException on unavailability
    """

    global _SANDBOX_READY, _SANDBOX_WARN, _SANDBOX_TS

    mode = (os.getenv("INSPECT_SANDBOX_PREFLIGHT", "auto") or "").strip().lower()
    if mode not in {"auto", "skip", "force"}:
        mode = "auto"

    if mode == "skip":
        return False

    # In-process stubs for unit tests (avoid needing a live sandbox)
    try:
        import sys

        now = time.monotonic()
        if tool_name == "editor" and "inspect_ai.tool._tools._text_editor" in sys.modules:
            _SANDBOX_READY = True
            _SANDBOX_TS = now
            return True
        if tool_name == "bash session" and "inspect_ai.tool._tools._bash_session" in sys.modules:
            _SANDBOX_READY = True
            _SANDBOX_TS = now
            return True
    except Exception:
        pass

    # TTL cache
    try:
        ttl_sec = float(os.getenv("INSPECT_SANDBOX_PREFLIGHT_TTL_SEC", "300"))
    except Exception:
        ttl_sec = 300.0
    now = time.monotonic()
    if _SANDBOX_READY is not None and _SANDBOX_TS is not None and ttl_sec > 0:
        if (now - _SANDBOX_TS) < ttl_sec:
            return _SANDBOX_READY
    _SANDBOX_TS = None  # invalidate on expiry

    # Lazy import to avoid heavy deps when not in sandbox mode
    try:  # pragma: no cover - integration path
        from inspect_ai.tool._tool_support_helpers import tool_support_sandbox
    except Exception:
        _SANDBOX_READY = False
        _SANDBOX_TS = now
        _SANDBOX_WARN = "Sandbox helper unavailable; falling back to Store-backed FS."
        if mode == "force":
            raise ToolException(_SANDBOX_WARN)
        return False

    try:
        # Verify the sandbox has the required service; ignore returned version
        await tool_support_sandbox(tool_name)
        _SANDBOX_READY = True
        _SANDBOX_TS = now
        return True
    except Exception as exc:
        _SANDBOX_READY = False
        _SANDBOX_TS = now
        _SANDBOX_WARN = str(exc) or ("Sandbox service not available; falling back to Store-backed FS.")

        # Best-effort structured warning log matching prior payload shape, without importing .tools
        try:
            import json
            import logging

            logger = logging.getLogger(__name__)
            payload: dict[str, object] = {"tool": "files:sandbox_preflight", "phase": "warn", "ok": False}
            payload["warning"] = _SANDBOX_WARN
            if truthy(os.getenv("INSPECT_SANDBOX_LOG_PATHS")):
                payload["fs_root"] = fs_root()
                payload["sandbox_tool"] = tool_name
            logger.info("tool_event %s", json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass

        if mode == "force":
            raise ToolException(_SANDBOX_WARN)
        return False


# --- Symlink denial and root-confinement -------------------------------------


async def deny_symlink(path: str) -> None:
    """Deny access to symlinks in sandbox mode.

    Raises ToolException if the target is a symbolic link when sandbox is
    available; otherwise acts as a best-effort no-op when sandbox isn't ready.
    """

    # If sandbox bash support isn't available, skip symlink verification.
    if not await ensure_sandbox_ready("bash session"):
        return

    try:
        import shlex

        from inspect_ai.tool._tools._bash_session import bash_session

        bash = bash_session()
        escaped_path = shlex.quote(path)
        with anyio.fail_after(default_tool_timeout()):
            result = await bash(action="run", command=f"test -L {escaped_path} && echo SYMLINK || echo OK")
        if result and hasattr(result, "stdout"):
            output = result.stdout.strip() if result.stdout else ""
            if output == "SYMLINK":
                raise ToolException(
                    f"Access denied: '{path}' is a symbolic link. "
                    f"Symbolic links are not allowed in sandbox mode for security reasons."
                )
    except ToolException:
        raise
    except Exception:
        # Best-effort only: any failure in the check shouldn't fail the op.
        return


def validate_sandbox_path(path: str) -> str:
    """Validate that `path` resides within the configured `fs_root()`.

    Returns the normalized absolute path or raises ToolException when outside
    the configured root.
    """

    root = fs_root()

    # Normalize the input path to absolute
    abs_path = os.path.join(root, path) if not os.path.isabs(path) else path
    normalized_path = os.path.normpath(abs_path)

    # Enforce root confinement (allow exactly the root itself)
    if not (normalized_path == root or normalized_path.startswith(root + os.sep)):
        raise ToolException(
            f"Access denied: path '{path}' is outside the configured filesystem root '{root}'. "
            f"Only paths within the root are allowed in sandbox mode."
        )
    return normalized_path


# --- Path Policy (Allow/Deny Globs) -------------------------------------------


def _split_globs(val: str | None) -> list[str]:
    try:
        if not val:
            return []
        parts = [p.strip() for p in val.split(",")]
        return [p for p in parts if p]
    except Exception:
        return []


def match_path_policy(abs_path: str) -> tuple[str, str | None]:
    """Return (kind, rule) where kind is 'deny'|'allow'|'none'.

    Rules are evaluated relative to fs_root():
    - INSPECT_FS_DENY: comma-separated globs (deny wins if matched)
    - INSPECT_FS_ALLOW: comma-separated globs (when set, only matched
      paths are allowed; non-matches are implicitly denied by 'allow')
    """
    import fnmatch
    import os as _os

    root = fs_root()
    try:
        rel = _os.path.relpath(abs_path, root)
    except Exception:
        rel = abs_path
    rel_posix = rel.replace(_os.sep, "/")

    deny = _split_globs(os.getenv("INSPECT_FS_DENY"))
    for rule in deny:
        if fnmatch.fnmatch(rel_posix, rule):
            return "deny", rule

    allow = _split_globs(os.getenv("INSPECT_FS_ALLOW"))
    if allow:
        for rule in allow:
            if fnmatch.fnmatch(rel_posix, rule):
                return "allow", rule
        # allow list present but no match → implicit deny
        return "deny", "<implicit-allow>"

    return "none", None


def check_policy(abs_path: str, op: str) -> None:
    """Enforce path policy for a given absolute path and op.

    Raises ToolException on denial with a descriptive message including the
    matched rule.
    """
    kind, rule = match_path_policy(abs_path)
    if kind == "deny":
        root = fs_root()
        raise ToolException(
            f"PolicyDenied: operation '{op}' on '{abs_path}' denied by rule '{rule}' under root '{root}'"
        )


# --- Compatibility aliases (for gradual adoption) ----------------------------

_DEPRECATIONS_ENABLED = truthy(os.getenv("INSPECT_SHOW_DEPRECATIONS"))
_DEPRECATIONS_EMITTED: set[str] = set()


def _warn_alias(name: str) -> None:
    if not _DEPRECATIONS_ENABLED:
        return
    try:
        global _DEPRECATIONS_EMITTED
        key = f"fs:{name}"
        if key in _DEPRECATIONS_EMITTED:
            return
        warnings.warn(
            f"{name} is deprecated; use the non-underscore variant from inspect_agents.fs instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        _DEPRECATIONS_EMITTED.add(key)
    except Exception:
        return


def _truthy(val: str | None) -> bool:  # noqa: D401
    _warn_alias("_truthy")
    return truthy(val)


def _fs_mode() -> str:  # noqa: D401
    _warn_alias("_fs_mode")
    return fs_mode()


def _use_sandbox_fs() -> bool:  # noqa: D401
    _warn_alias("_use_sandbox_fs")
    return use_sandbox_fs()


def _default_tool_timeout() -> float:  # noqa: D401
    _warn_alias("_default_tool_timeout")
    return default_tool_timeout()


def _fs_root() -> str:  # noqa: D401
    _warn_alias("_fs_root")
    return fs_root()


def _max_bytes() -> int:  # noqa: D401
    _warn_alias("_max_bytes")
    return max_bytes()


async def _ensure_sandbox_ready(tool_name: str) -> bool:  # noqa: D401
    _warn_alias("_ensure_sandbox_ready")
    return await ensure_sandbox_ready(tool_name)


async def _deny_symlink(path: str) -> None:  # noqa: D401
    _warn_alias("_deny_symlink")
    await deny_symlink(path)


_validate_sandbox_path = validate_sandbox_path
