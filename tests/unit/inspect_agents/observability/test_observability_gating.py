import json
import logging


def _cap_logs(caplog):
    records = []
    for rec in caplog.records:
        msg = rec.getMessage()
        if isinstance(msg, str) and msg.startswith("tool_event "):
            try:
                payload = json.loads(msg[len("tool_event ") :])
                records.append(payload)
            except Exception:
                pass
    return records


def _cap_observability_once_events(caplog):
    return [
        e
        for e in _cap_logs(caplog)
        if e.get("tool") == "observability" and e.get("phase") == "info" and "effective_tool_output_limit" in e
    ]


def test_cap_log_skips_limits_then_emits_on_first_real_tool(caplog, monkeypatch):
    # Arrange fresh state: no explicit config limit; env provides limit
    from inspect_ai.model._generate_config import GenerateConfig, set_active_generate_config

    import inspect_agents.observability as obs

    # Reset one-time guard and config
    monkeypatch.setattr(obs, "_EFFECTIVE_LIMIT_LOGGED", False, raising=False)
    set_active_generate_config(GenerateConfig())
    monkeypatch.setenv("INSPECT_MAX_TOOL_OUTPUT", "4096")

    # Capture package logs
    caplog.set_level(logging.INFO, logger="inspect_agents")
    caplog.set_level(logging.INFO, logger="inspect_agents.tools")

    # Act: first emit an internal limits event (should NOT trigger cap log)
    obs.log_tool_event(name="limits", phase="info", extra={"event": "limit_nearing"})
    # Then a real tool event; this should trigger the one-time cap log
    obs.log_tool_event(name="files:read", phase="start")

    # Assert: exactly one observability cap log with expected value and ordering
    events = _cap_logs(caplog)
    once = _cap_observability_once_events(caplog)
    assert len(once) == 1, f"expected one cap log, got {len(once)}: {once}"
    assert once[0]["effective_tool_output_limit"] == 4096
    assert once[0]["source"] == "env"

    # Ensure the cap log appeared with/after the real tool event, not before
    first_files_idx = next(i for i, e in enumerate(events) if e.get("tool") == "files:read")
    cap_idx = next(
        i
        for i, e in enumerate(events)
        if e.get("tool") == "observability" and e.get("phase") == "info" and "effective_tool_output_limit" in e
    )
    assert cap_idx >= first_files_idx, "cap log must not precede first real tool event"


def test_cap_log_skips_internal_observability_then_real_tool_emits_once(caplog, monkeypatch):
    # Arrange fresh state
    from inspect_ai.model._generate_config import GenerateConfig, set_active_generate_config

    import inspect_agents.observability as obs

    monkeypatch.setattr(obs, "_EFFECTIVE_LIMIT_LOGGED", False, raising=False)
    set_active_generate_config(GenerateConfig())
    monkeypatch.setenv("INSPECT_MAX_TOOL_OUTPUT", "2048")

    caplog.set_level(logging.INFO, logger="inspect_agents")
    caplog.set_level(logging.INFO, logger="inspect_agents.tools")

    # Act: emit an internal observability event first (should NOT trigger cap log)
    obs.log_tool_event(name="observability", phase="info", extra={"note": "diagnostic"})
    # Two distinct real tool events; cap log should still emit only once
    obs.log_tool_event(name="files:write", phase="start")
    obs.log_tool_event(name="files:read", phase="start")

    once = _cap_observability_once_events(caplog)
    assert len(once) == 1, f"expected exactly one cap log, got {len(once)}: {once}"
    assert once[0]["effective_tool_output_limit"] == 2048
    assert once[0]["source"] == "env"
