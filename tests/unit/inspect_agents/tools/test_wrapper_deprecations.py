import asyncio
import warnings

import pytest


def test_read_file_emits_deprecation_warning(monkeypatch):
    monkeypatch.delenv("INSPECT_AGENTS_SUPPRESS_TOOL_WRAPPER_WARN", raising=False)
    from inspect_agents.tools import read_file

    t = read_file()
    with pytest.warns(DeprecationWarning):
        with pytest.raises(Exception):
            asyncio.run(t(file_path="__no_such_file__.txt", offset=0, limit=1))


def test_write_file_emits_deprecation_warning(monkeypatch):
    monkeypatch.delenv("INSPECT_AGENTS_SUPPRESS_TOOL_WRAPPER_WARN", raising=False)
    from inspect_agents.tools import write_file

    t = write_file()
    with pytest.warns(DeprecationWarning):
        asyncio.run(t(file_path="wr_warn.txt", content="ok", instance="warn"))


def test_edit_file_emits_deprecation_warning(monkeypatch):
    monkeypatch.delenv("INSPECT_AGENTS_SUPPRESS_TOOL_WRAPPER_WARN", raising=False)
    # Seed via unified tool to avoid extra wrapper warnings
    from inspect_agents.tools import edit_file
    from inspect_agents.tools_files import FilesParams, WriteParams, files_tool

    f = files_tool()
    asyncio.run(
        f(
            params=FilesParams(
                root=WriteParams(command="write", file_path="ed_warn.txt", content="hello", instance="warn")
            )
        )
    )

    t = edit_file()
    with pytest.warns(DeprecationWarning):
        asyncio.run(
            t(
                file_path="ed_warn.txt",
                old_string="hello",
                new_string="hello!",
                replace_all=False,
                instance="warn",
            )
        )


def test_delete_file_emits_deprecation_warning(monkeypatch):
    monkeypatch.delenv("INSPECT_AGENTS_SUPPRESS_TOOL_WRAPPER_WARN", raising=False)
    from inspect_agents.tools import delete_file
    from inspect_agents.tools_files import FilesParams, WriteParams, files_tool

    # Create a file via unified tool
    f = files_tool()
    asyncio.run(
        f(
            params=FilesParams(
                root=WriteParams(command="write", file_path="del_warn.txt", content="bye", instance="warn")
            )
        )
    )

    t = delete_file()
    with pytest.warns(DeprecationWarning):
        asyncio.run(t(file_path="del_warn.txt", instance="warn"))


def test_wrapper_warning_can_be_suppressed(monkeypatch):
    monkeypatch.setenv("INSPECT_AGENTS_SUPPRESS_TOOL_WRAPPER_WARN", "1")
    from inspect_agents.tools import read_file

    t = read_file()
    # Pytest 8 no longer accepts pytest.warns(None). Use stdlib warnings capture
    # to ensure no DeprecationWarning is emitted when suppression env is set.
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        try:
            asyncio.run(t(file_path="__no_such_file__.txt", offset=0, limit=1))
        except Exception:
            pass
    assert not any(issubclass(w.category, DeprecationWarning) for w in record)
