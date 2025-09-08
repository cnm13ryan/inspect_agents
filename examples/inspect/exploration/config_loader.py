"""Deprecation shim for examples.inspect.exploration.config_loader.

Moved to examples.lib.exploration.config_loader. This shim re-exports the API.
"""

from __future__ import annotations

import warnings as _warnings

from examples.lib.exploration.config_loader import *  # noqa: F401,F403

_warnings.warn(
    "examples.inspect.exploration.config_loader is deprecated; use examples.lib.exploration.config_loader.",
    DeprecationWarning,
    stacklevel=2,
)
