from collections.abc import Iterable


def _tool_names(tools: Iterable[object]) -> set[str]:
    from inspect_ai.tool._tool_def import ToolDef

    names: set[str] = set()
    for tool in tools:
        try:
            tdef = tool if isinstance(tool, ToolDef) else ToolDef(tool)
            names.add(tdef.name)
        except Exception:
            # Ignore uninspectable callables; presets should not include them.
            pass
    return names


def test_minimal_fs_preset_only_todo_and_fs(monkeypatch):
    monkeypatch.delenv("INSPECT_ENABLE_THINK", raising=False)
    monkeypatch.delenv("INSPECT_ENABLE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSPECT_ENABLE_EXEC", raising=False)
    monkeypatch.delenv("INSPECT_ENABLE_WEB_BROWSER", raising=False)
    monkeypatch.delenv("INSPECT_ENABLE_TEXT_EDITOR_TOOL", raising=False)

    from inspect_agents.tools import minimal_fs_preset

    names = _tool_names(minimal_fs_preset())
    assert names == {
        "write_todos",
        "update_todo_status",
        "write_file",
        "read_file",
        "ls",
        "edit_file",
    }


def test_full_safe_preset_respects_disabled_standard(monkeypatch):
    monkeypatch.setenv("INSPECT_ENABLE_THINK", "0")
    monkeypatch.setenv("INSPECT_ENABLE_WEB_SEARCH", "0")
    monkeypatch.setenv("INSPECT_ENABLE_EXEC", "0")
    monkeypatch.setenv("INSPECT_ENABLE_WEB_BROWSER", "0")
    monkeypatch.setenv("INSPECT_ENABLE_TEXT_EDITOR_TOOL", "0")

    from inspect_agents.tools import full_safe_preset

    names = _tool_names(full_safe_preset())
    assert {
        "write_todos",
        "update_todo_status",
        "write_file",
        "read_file",
        "ls",
        "edit_file",
    } == names
    assert "bash_session" not in names


def test_full_safe_preset_includes_exec_when_enabled(monkeypatch):
    monkeypatch.setenv("INSPECT_ENABLE_THINK", "0")
    monkeypatch.setenv("INSPECT_ENABLE_WEB_SEARCH", "0")
    monkeypatch.setenv("INSPECT_ENABLE_WEB_BROWSER", "0")
    monkeypatch.setenv("INSPECT_ENABLE_TEXT_EDITOR_TOOL", "0")
    monkeypatch.setenv("INSPECT_ENABLE_EXEC", "1")

    from inspect_agents.tools import full_safe_preset

    names = _tool_names(full_safe_preset())
    assert {"bash", "python"}.issubset(names)
    assert "bash_session" not in names
