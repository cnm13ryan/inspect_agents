from __future__ import annotations

import os
import re
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass

from .observability import log_tool_event

_T_PATTERN = r"T([012])"
_H_PATTERN = r"H([0123])"
_N_PATTERN = r"N([012])"
_PROFILE_RE = re.compile(rf"^{_T_PATTERN}\.{_H_PATTERN}\.{_N_PATTERN}$", re.IGNORECASE)


@dataclass(frozen=True)
class SandboxProfile:
    """Resolved sandbox profile.

    Attributes
    - t/h/n: normalized profile components (e.g., "T1")
    - sandbox: provider string to pass to Inspect Task.sandbox ("local"|"docker"|"k8s"|"proxmox")
    """

    t: str
    h: str
    n: str
    sandbox: str


def parse_profile(profile: str) -> tuple[str, str, str]:
    """Parse a Tx.Hx.Nx string and return normalized components.

    Raises ValueError on invalid input.
    """
    m = _PROFILE_RE.fullmatch(profile.strip())
    if not m:
        raise ValueError("Invalid INSPECT_PROFILE. Expected 'T[0-2].H[0-3].N[0-2]' (e.g., T1.H1.N2).")
    return (f"T{m.group(1)}", f"H{m.group(2)}", f"N{m.group(3)}")


def _map_host_isolation(h: str) -> str:
    h = h.upper()
    return {"H0": "local", "H1": "docker", "H2": "k8s", "H3": "proxmox"}[h]


def _apply_tooling_env(t: str, env: MutableMapping[str, str]) -> None:
    """Apply environment toggles for tooling based on T dimension.

    Policy (from docs/guides/sandbox_profiles.md):
    - T2: do not enable tools (pure text). Optionally allow search if callers set it explicitly.
    - T1: enable web-search only (INSPECT_ENABLE_WEB_SEARCH=1); do not enable exec or browser.
    - T0: enable exec (INSPECT_ENABLE_EXEC=1); browser optional and left off by default.

    Existing explicit envs (if already set by caller) are respected; we do not overwrite
    a non-empty value. This makes profiles a safe default layer that users can override.
    """
    t = t.upper()
    if t == "T2":
        # Explicitly disable exec, browser, and web-search for text-only
        env["INSPECT_ENABLE_EXEC"] = "0"
        env["INSPECT_ENABLE_WEB_BROWSER"] = "0"
        env["INSPECT_ENABLE_WEB_SEARCH"] = "0"
        return
    if t == "T1":
        # Web-only
        env["INSPECT_ENABLE_WEB_SEARCH"] = "1"
        env["INSPECT_ENABLE_EXEC"] = "0"
        env["INSPECT_ENABLE_WEB_BROWSER"] = "0"
        return
    # T0
    env["INSPECT_ENABLE_EXEC"] = "1"
    # Browser stays opt-in; callers can set INSPECT_ENABLE_WEB_BROWSER=1 explicitly


def resolve_profile_from_env(env: Mapping[str, str] | None = None) -> SandboxProfile | None:
    """Resolve and apply a profile from INSPECT_PROFILE if set.

    Returns the resolved SandboxProfile or None if not configured.
    Side effects: applies tool toggles to the provided env (defaults to os.environ).
    Also emits a tool_event with the selected profile metadata.
    """
    if env is None:
        env = os.environ
    raw = (env.get("INSPECT_PROFILE") or "").strip()
    if not raw:
        return None

    t, h, n = parse_profile(raw)
    sandbox = _map_host_isolation(h)

    # Apply tooling toggles as defaults
    target_env: MutableMapping[str, str]
    try:
        # Prefer the provided mapping when it behaves like a mutable env
        if hasattr(env, "setdefault") and callable(getattr(env, "setdefault")):
            target_env = env  # type: ignore[assignment]
        else:
            raise TypeError
    except Exception:
        # Fallback to process env if a read-only Mapping was passed
        target_env = os.environ  # type: ignore[assignment]

    _apply_tooling_env(t, target_env)

    # Stronger safe defaults for host isolation in prod-like profiles.
    # When H >= H1 (docker/k8s/proxmox), default to:
    # - Read-only filesystem guard in sandbox mode
    # - Forced sandbox preflight to avoid silent fallbacks
    # Respect explicit overrides set by the caller (do not overwrite).
    try:
        if h.upper() in {"H1", "H2", "H3"}:
            target_env.setdefault("INSPECT_AGENTS_FS_READ_ONLY", "1")
            target_env.setdefault("INSPECT_SANDBOX_PREFLIGHT", "force")
    except Exception:
        # Defaulting must never raise; continue best-effort
        pass

    # Emit observability event for auditability
    try:
        log_tool_event(
            name="profile",
            phase="info",
            extra={
                "t": t,
                "h": h,
                "n": n,
                "sandbox": sandbox,
                "source": "env",
            },
        )
    except Exception:
        # Observability must not alter control flow
        pass

    return SandboxProfile(t=t, h=h, n=n, sandbox=sandbox)


__all__ = [
    "SandboxProfile",
    "parse_profile",
    "resolve_profile_from_env",
]
