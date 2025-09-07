import json
import logging

import pytest

# This module duplicates coverage now provided by
# tests/inspect_agents/test_observability_logging.py. Skip to avoid
# double-emitting/duplicating the one-time cap-log assertions.
pytestmark = pytest.mark.skip(
    reason="Redundant with tests/inspect_agents/test_observability_logging.py (one-time cap log)."
)


def test_observability_once_log_direct_calls(caplog, monkeypatch):
    # Fresh state for observability and generate config
    from inspect_ai.model._generate_config import GenerateConfig, set_active_generate_config

    import inspect_agents.observability as obs

    monkeypatch.setattr(obs, "_EFFECTIVE_LIMIT_LOGGED", False, raising=False)
    set_active_generate_config(GenerateConfig())

    # Apply env override to make the source deterministic
    monkeypatch.setenv("INSPECT_MAX_TOOL_OUTPUT", "4096")

    # Capture logs at our package logger
    caplog.set_level(logging.INFO, logger="inspect_agents")
    caplog.set_level(logging.INFO, logger="inspect_agents.tools")

    # Call log_tool_event twice; the observability info should appear once
    obs.log_tool_event(name="dummy", phase="start")
    obs.log_tool_event(name="dummy", phase="start")

    events = []
    for rec in caplog.records:
        msg = rec.getMessage()
        if isinstance(msg, str) and msg.startswith("tool_event "):
            try:
                payload = json.loads(msg[len("tool_event ") :])
                events.append(payload)
            except Exception:
                pass

    obs_events = [e for e in events if e.get("tool") == "observability" and e.get("phase") == "info"]
    assert len(obs_events) == 1
    assert obs_events[0].get("effective_tool_output_limit") == 4096
    assert obs_events[0].get("source") == "env"
