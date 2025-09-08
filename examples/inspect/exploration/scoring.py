"""Deprecation shim for examples.inspect.exploration.scoring.

Moved to examples.lib.exploration.scoring. This shim re-exports the API.
"""

from __future__ import annotations

import warnings as _warnings

from examples.lib.exploration.scoring import *  # noqa: F401,F403

_warnings.warn(
    "examples.inspect.exploration.scoring is deprecated; use examples.lib.exploration.scoring.",
    DeprecationWarning,
    stacklevel=2,
)
