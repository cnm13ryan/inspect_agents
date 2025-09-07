import json
import logging


def _collect_observability_events(caplog):
    events = []
    for rec in caplog.records:
        msg = rec.getMessage()
        if isinstance(msg, str) and msg.startswith("tool_event "):
            try:
                payload = json.loads(msg[len("tool_event ") :])
                if payload.get("tool") == "observability" and payload.get("phase") == "info":
                    events.append(payload)
            except Exception:
                pass
    return events


def test_effective_limit_prefers_generate_config_over_env_log_once(caplog, monkeypatch):
    # Arrange fresh state and a GenerateConfig value overriding env
    from inspect_ai.model._generate_config import GenerateConfig, set_active_generate_config

    import inspect_agents.observability as obs

    # Reset one-time gate and set config/env
    monkeypatch.setattr(obs, "_EFFECTIVE_LIMIT_LOGGED", False, raising=False)
    set_active_generate_config(GenerateConfig(max_tool_output=3072))
    monkeypatch.setenv("INSPECT_MAX_TOOL_OUTPUT", "8192")

    # Capture logs from our package loggers
    caplog.set_level(logging.INFO, logger="inspect_agents")
    caplog.set_level(logging.INFO, logger="inspect_agents.tools")

    # Act: trigger two tool events; observability info should emit once
    obs.log_tool_event(name="dummy", phase="start")
    obs.log_tool_event(name="dummy", phase="start")

    # Assert: exactly one observability info event with config-precedence value
    obs_events = _collect_observability_events(caplog)
    assert len(obs_events) == 1
    assert obs_events[0].get("effective_tool_output_limit") == 3072
    # Source only distinguishes env vs default; env present → "env"
    assert obs_events[0].get("source") == "env"


def test_effective_limit_uses_generate_config_without_env_source_default(caplog, monkeypatch):
    # Arrange fresh state: explicit GenerateConfig, no env
    from inspect_ai.model._generate_config import GenerateConfig, set_active_generate_config

    import inspect_agents.observability as obs

    monkeypatch.setattr(obs, "_EFFECTIVE_LIMIT_LOGGED", False, raising=False)
    set_active_generate_config(GenerateConfig(max_tool_output=2048))
    monkeypatch.delenv("INSPECT_MAX_TOOL_OUTPUT", raising=False)

    caplog.set_level(logging.INFO, logger="inspect_agents")
    caplog.set_level(logging.INFO, logger="inspect_agents.tools")

    # Act: trigger two tool events; observability info should emit once
    obs.log_tool_event(name="dummy", phase="start")
    obs.log_tool_event(name="dummy", phase="start")

    # Assert: exactly one event; effective comes from config; source is "default"
    obs_events = _collect_observability_events(caplog)
    assert len(obs_events) == 1
    assert obs_events[0].get("effective_tool_output_limit") == 2048
    assert obs_events[0].get("source") == "default"
