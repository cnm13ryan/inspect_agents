def _tool_names(tools: list[object]) -> set[str]:
    names: set[str] = set()
    for t in tools:
        try:
            name = getattr(t, "name", None) or getattr(t, "__name__", None)
            if isinstance(name, str) and name.strip():
                names.add(name.strip().lower())
        except Exception:
            # Ignore tools we cannot introspect
            pass
    return names


def test_standard_tools_excludes_bash_session(monkeypatch):
    # Enable all toggles that could expand the tool list; policy must still hold
    monkeypatch.setenv("INSPECT_ENABLE_THINK", "1")
    monkeypatch.setenv("INSPECT_ENABLE_WEB_SEARCH", "1")
    monkeypatch.setenv("INSPECT_ENABLE_EXEC", "1")
    monkeypatch.setenv("INSPECT_ENABLE_WEB_BROWSER", "1")
    monkeypatch.setenv("INSPECT_ENABLE_TEXT_EDITOR_TOOL", "1")

    # Force store mode to avoid requiring a sandbox for this invariant check
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "store")

    # PYTHONPATH in CI should already include src:external/inspect_ai per repo docs
    from inspect_agents.tools import standard_tools

    names = _tool_names(standard_tools())
    assert "bash_session" not in names, "standard_tools() must never surface bash_session"
