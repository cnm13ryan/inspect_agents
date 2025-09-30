"""Pytest fixtures for observability tests.

This conftest ensures that tests which monkeypatch inspect_agents.observability._EFFECTIVE_LIMIT_LOGGED
also synchronize the state with the underlying TelemetryService singleton.
"""

import pytest


@pytest.fixture(autouse=True)
def sync_effective_limit_logged(monkeypatch):
    """Auto-fixture to sync _EFFECTIVE_LIMIT_LOGGED between module and service.

    This fixture wraps monkeypatch.setattr to detect when tests patch
    inspect_agents.observability._EFFECTIVE_LIMIT_LOGGED and automatically
    sync that value to the TelemetryService singleton.
    """
    original_setattr = monkeypatch.setattr

    def patched_setattr(target, name, value=..., raising=True):
        # Call original setattr
        result = original_setattr(target, name, value, raising)

        # If patching observability._EFFECTIVE_LIMIT_LOGGED, sync to service
        try:
            import inspect_agents.observability as obs_module
            from inspect_agents.telemetry import get_service

            if target is obs_module or (
                isinstance(target, str) and "observability" in target and name == "_EFFECTIVE_LIMIT_LOGGED"
            ):
                # Sync the value to the service
                service = get_service()
                if value is not ...:
                    service._effective_limit_logged = value
        except Exception:
            # Never let sync failures break tests
            pass

        return result

    monkeypatch.setattr = patched_setattr
    yield
