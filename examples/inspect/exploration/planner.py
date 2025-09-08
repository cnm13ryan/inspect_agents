"""Deprecation shim for examples.inspect.exploration.planner.

Moved to examples.lib.exploration.planner. This shim re-exports the public API.
"""

from __future__ import annotations

import warnings as _warnings

from examples.lib.exploration.planner import *  # noqa: F401,F403

_warnings.warn(
    "examples.inspect.exploration.planner is deprecated; use examples.lib.exploration.planner.",
    DeprecationWarning,
    stacklevel=2,
)
