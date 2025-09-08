"""Deprecation shim for examples.inspect.exploration.planner_tool.

This module now lives under examples.lib.exploration.planner_tool.
We preserve monkeypatch compatibility by forwarding `_load_planner`
into the library module at call time.
"""

from __future__ import annotations

import warnings as _warnings

from examples.lib.exploration import planner_tool as _lib  # type: ignore

_warnings.warn(
    "examples.inspect.exploration.planner_tool is deprecated; use examples.lib.exploration.planner_tool.",
    DeprecationWarning,
    stacklevel=2,
)

# Expose a patchable symbol matching historical tests
_load_planner = _lib._load_planner  # type: ignore[attr-defined]


def planner_tool():  # -> Tool
    # If tests monkeypatch this module's _load_planner, propagate that override
    try:  # pragma: no cover - trivial assignment
        _lib._load_planner = _load_planner  # type: ignore[attr-defined]
    except Exception:
        pass
    return _lib.planner_tool()
