from inspect_agents.profiles import resolve_profile_from_env


def test_prod_profile_sets_safe_fs_defaults():
    env = {
        "INSPECT_PROFILE": "T1.H2.N2",  # prod-like host isolation
    }

    prof = resolve_profile_from_env(env)
    assert prof is not None and prof.h == "H2"

    # Defaults applied for H>=H1
    assert env["INSPECT_AGENTS_FS_READ_ONLY"] == "1"
    assert env["INSPECT_SANDBOX_PREFLIGHT"] == "force"


def test_explicit_overrides_are_respected():
    env = {
        "INSPECT_PROFILE": "T1.H1.N0",
        # Caller intentionally disables read-only and sets preflight mode
        "INSPECT_AGENTS_FS_READ_ONLY": "0",
        "INSPECT_SANDBOX_PREFLIGHT": "auto",
    }

    prof = resolve_profile_from_env(env)
    assert prof is not None and prof.h == "H1"

    # Explicit values are preserved
    assert env["INSPECT_AGENTS_FS_READ_ONLY"] == "0"
    assert env["INSPECT_SANDBOX_PREFLIGHT"] == "auto"
