import json
import logging


def _collect_observability_info_events(records):
    events = []
    for rec in records:
        msg = rec.getMessage()
        if isinstance(msg, str) and msg.startswith("tool_event "):
            try:
                payload = json.loads(msg[len("tool_event ") :])
            except Exception:
                continue
            if payload.get("tool") == "observability" and payload.get("phase") == "info":
                events.append(payload)
    return events


def test_one_time_cap_log_with_env_source(caplog, monkeypatch):
    # Fresh state for observability & upstream generate config
    from inspect_ai.model._generate_config import GenerateConfig, set_active_generate_config

    import inspect_agents.observability as obs

    # Reset one-time guard and ensure no explicit config limit
    monkeypatch.setattr(obs, "_EFFECTIVE_LIMIT_LOGGED", False, raising=False)
    set_active_generate_config(GenerateConfig())

    # Provide env to set the effective limit and source
    monkeypatch.setenv("INSPECT_MAX_TOOL_OUTPUT", "8192")

    # Capture logs from package loggers used by observability
    caplog.set_level(logging.INFO, logger="inspect_agents")
    caplog.set_level(logging.INFO, logger="inspect_agents.tools")

    before = len(caplog.records)

    # First real tool event triggers deferred one-time cap log
    obs.log_tool_event(name="files:ls", phase="start")

    # Second event should NOT emit another cap log
    obs.log_tool_event(name="files:ls", phase="start")

    obs_events = _collect_observability_info_events(caplog.records[before:])
    assert len(obs_events) == 1, f"expected one cap log, got {len(obs_events)}: {obs_events}"
    assert obs_events[0].get("effective_tool_output_limit") == 8192
    assert obs_events[0].get("source") == "env"


def test_one_time_cap_log_default_when_no_env(caplog, monkeypatch):
    # Fresh state; explicit config has no limit; env absent
    from inspect_ai.model._generate_config import GenerateConfig, set_active_generate_config

    import inspect_agents.observability as obs

    monkeypatch.setattr(obs, "_EFFECTIVE_LIMIT_LOGGED", False, raising=False)
    set_active_generate_config(GenerateConfig())
    monkeypatch.delenv("INSPECT_MAX_TOOL_OUTPUT", raising=False)

    caplog.set_level(logging.INFO, logger="inspect_agents")
    caplog.set_level(logging.INFO, logger="inspect_agents.tools")

    before = len(caplog.records)

    # First real tool event triggers cap log with fallback default (16 KiB)
    obs.log_tool_event(name="files:ls", phase="start")

    # Extra call should not produce additional cap logs
    obs.log_tool_event(name="files:ls", phase="start")

    obs_events = _collect_observability_info_events(caplog.records[before:])
    assert len(obs_events) == 1
    assert obs_events[0].get("effective_tool_output_limit") == 16 * 1024
    assert obs_events[0].get("source") == "default"
