"""Pytest configuration for filesystem tests.

This module provides fixtures and configuration for filesystem-related tests.
"""

import pytest


@pytest.fixture(autouse=True)
def reset_fs_access_facade():
    """Reset the filesystem access façade before each test.

    This fixture ensures that tests which patch tools_files module attributes
    (like _use_sandbox_fs, _get_sandbox_adapter, _max_bytes, etc.) have those
    patches take effect, even though the façade is created lazily.

    The reset happens before each test so that the façade will be recreated
    on first use within the test, picking up any monkeypatches.
    """
    from inspect_agents import tools_files

    tools_files._reset_fs_access()
    yield
    # Optionally reset after test too, though before is sufficient
    tools_files._reset_fs_access()
