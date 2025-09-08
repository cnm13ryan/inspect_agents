#!/usr/bin/env python3
"""
Shared utilities for example runners.

Goals
- Ensure the repository's `src/` takes precedence over any installed package.
- Load environment files with consistent, non-overriding precedence.

Semantics
- "No override": earlier sources win; later files only fill in missing vars.
- Precedence (highest → lowest among files):
  1) Explicit `INSPECT_ENV_FILE` if set
  2) `<repo>/.env`
  3) `<example_dir>/.env` (runner-specific convenience)
  4) `<repo>/env_templates/inspect.env` (template defaults; optional)

If `python-dotenv` is unavailable, a minimal fallback loader applies the same
ordering and "no override" behavior for simple KEY=VALUE lines.
"""

from __future__ import annotations

import importlib.util as _il
import os
import sys
from pathlib import Path
from types import ModuleType

__all__ = [
    "ensure_repo_src_on_path",
    "load_env_files",
    "print_effective_tool_output_limit",
    "import_by_path",
]


def _default_repo_root() -> Path:
    """Best-effort repository root based on this file location.

    Assumes this module lives under `<repo>/examples/_utils.py`.
    """
    # examples/_utils.py -> parent is examples/, grandparent is repo root
    return Path(__file__).resolve().parents[1]


def ensure_repo_src_on_path(repo_root: Path | None = None) -> None:
    """Ensure `<repo>/src` is first on `sys.path`.

    This makes local sources take precedence over any installed distribution.
    Idempotent and safe to call multiple times.
    """
    root = repo_root or _default_repo_root()
    src_dir = root / "src"
    try:
        s = str(src_dir)
        if s not in sys.path:
            sys.path.insert(0, s)
    except Exception:
        # Path adjustments are best-effort; proceed if the environment forbids it
        return


def _load_kv_file(path: Path) -> None:
    """Minimal KEY=VALUE parser that does not override existing vars.

    - Ignores empty lines and comments (# ...)
    - Strips wrapping single/double quotes
    - Best-effort: swallows parsing errors per-file
    """
    if not path or not path.exists():
        return
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        # Fallback loader is best-effort only
        return


def load_env_files(example_dir: Path | None, include_template: bool = True) -> None:
    """Load environment files with consistent precedence and no overrides.

    Parameters
    - example_dir: directory for the calling runner (e.g., `Path(__file__).parent`).
    - include_template: if True, apply `<repo>/env_templates/inspect.env` last.

    Behavior
    - Honors `INSPECT_ENV_FILE` if set, applying it first.
    - Later files only set variables that are not already defined.
    - Uses `python-dotenv` when available; otherwise falls back to `_load_kv_file`.
    """
    repo_root = (example_dir.parent if example_dir else None) or _default_repo_root()
    explicit = os.getenv("INSPECT_ENV_FILE")

    try:
        # Prefer python-dotenv when available
        from dotenv import load_dotenv  # type: ignore

        if explicit:
            load_dotenv(explicit, override=False)
        load_dotenv(repo_root / ".env", override=False)
        if example_dir is not None:
            load_dotenv(example_dir / ".env", override=False)
        if include_template:
            load_dotenv(repo_root / "env_templates" / "inspect.env", override=False)
        return
    except Exception:
        # Minimal fallback: same ordering, no override
        if explicit:
            _load_kv_file(Path(explicit))
        _load_kv_file(repo_root / ".env")
        if example_dir is not None:
            _load_kv_file(example_dir / ".env")
        if include_template:
            _load_kv_file(repo_root / "env_templates" / "inspect.env")


def print_effective_tool_output_limit(label: str = "Tool-output cap") -> None:
    """Print the effective tool-output limit and its source.

    Uses inspect_agents.observability.get_effective_tool_output_limit(), falling
    back silently if the helper or upstream deps are unavailable.
    """
    try:
        from inspect_agents.observability import get_effective_tool_output_limit

        limit, source = get_effective_tool_output_limit()
        print(f"{label}: {limit} bytes ({source})")
    except Exception:
        # Best-effort only; absence should not break example runners
        return


def import_by_path(name: str, path: Path) -> ModuleType:
    """Import a Python module by file path with clear errors.

    Parameters
    - name: logical module name to assign (used in tracebacks only)
    - path: filesystem path to the module (``.py`` file)

    Returns
    - The loaded module object (``types.ModuleType``)

    Notes
    - This helper avoids site-packages name collisions (e.g., a third-party
      ``examples`` package) by importing from an explicit path.
    - Callers should keep a minimal bootstrap to import this function itself
      when ``examples._utils`` cannot be safely imported via sys.path.
    """
    spec = _il.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"Unable to load {name} from {path}")
    mod = _il.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return mod
