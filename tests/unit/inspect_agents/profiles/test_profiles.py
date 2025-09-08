import pytest


def test_parse_profile_ok():
    from inspect_agents.profiles import parse_profile

    assert parse_profile("T1.H2.N0") == ("T1", "H2", "N0")
    assert parse_profile("t0.h3.n2") == ("T0", "H3", "N2")


def test_parse_profile_invalid():
    from inspect_agents.profiles import parse_profile

    with pytest.raises(ValueError):
        parse_profile("bad")
    with pytest.raises(ValueError):
        parse_profile("T3.H0.N0")


def test_resolve_profile_applies_env_and_logs(caplog):
    from inspect_agents.profiles import resolve_profile_from_env

    env = {
        "INSPECT_PROFILE": "T1.H1.N2",
        # Start with conservative toggles; resolver should override for T1
        "INSPECT_ENABLE_WEB_SEARCH": "0",
        "INSPECT_ENABLE_EXEC": "0",
        "INSPECT_ENABLE_WEB_BROWSER": "1",  # should be forced off for T1
    }

    caplog.set_level("INFO", logger="inspect_agents.tools")
    prof = resolve_profile_from_env(env)

    assert prof is not None
    assert (prof.t, prof.h, prof.n, prof.sandbox) == ("T1", "H1", "N2", "docker")

    # Env toggles reflect web-only
    assert env["INSPECT_ENABLE_WEB_SEARCH"] == "1"
    assert env["INSPECT_ENABLE_EXEC"] == "0"
    assert env["INSPECT_ENABLE_WEB_BROWSER"] == "0"

    # A tool_event with profile metadata is logged
    logs = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "tool_event" in logs
    assert '"tool": "profile"' in logs
    assert '"sandbox": "docker"' in logs


def test_resolve_profile_t0_exec_only(caplog):
    from inspect_agents.profiles import resolve_profile_from_env

    env = {
        "INSPECT_PROFILE": "T0.H0.N0",
        # Start with explicit no-search/no-browser; T0 should only enable exec
        "INSPECT_ENABLE_WEB_SEARCH": "0",
        "INSPECT_ENABLE_EXEC": "0",
        "INSPECT_ENABLE_WEB_BROWSER": "0",
    }

    caplog.set_level("INFO", logger="inspect_agents.tools")
    prof = resolve_profile_from_env(env)

    assert prof is not None and prof.sandbox == "local"
    assert env["INSPECT_ENABLE_EXEC"] == "1"
    # Other toggles unchanged (still off)
    assert env["INSPECT_ENABLE_WEB_SEARCH"] == "0"
    assert env["INSPECT_ENABLE_WEB_BROWSER"] == "0"


def test_resolve_profile_t2_text_only(caplog):
    from inspect_agents.profiles import resolve_profile_from_env

    env = {
        "INSPECT_PROFILE": "T2.H3.N0",
        # Seed toggles on to ensure they are turned off for T2
        "INSPECT_ENABLE_WEB_SEARCH": "1",
        "INSPECT_ENABLE_EXEC": "1",
        "INSPECT_ENABLE_WEB_BROWSER": "1",
    }

    caplog.set_level("INFO", logger="inspect_agents.tools")
    prof = resolve_profile_from_env(env)

    assert prof is not None and prof.sandbox == "proxmox"
    assert env["INSPECT_ENABLE_EXEC"] == "0"
    assert env["INSPECT_ENABLE_WEB_BROWSER"] == "0"
    assert env["INSPECT_ENABLE_WEB_SEARCH"] == "0"
