"""Guards against future drift in truthy helpers.

Ensures `inspect_agents.fs.truthy` (and its underscore alias) are delegated to
the centralized implementation in `inspect_agents.settings.truthy`.
"""

from __future__ import annotations


def test_fs_truthy_is_settings_truthy() -> None:
    from inspect_agents import fs, settings

    # Identity check: fs.truthy must be the same function object as settings.truthy
    assert fs.truthy is settings.truthy
    # Alias check: underscore alias remains a direct alias for one cycle
    assert fs._truthy is settings.truthy
