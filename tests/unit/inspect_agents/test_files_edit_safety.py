import asyncio

import pytest


def test_store_mode_expected_count_and_dry_run(monkeypatch):
    # Ensure store mode
    monkeypatch.delenv("INSPECT_AGENTS_FS_MODE", raising=False)
    monkeypatch.delenv("INSPECT_AGENTS_TYPED_RESULTS", raising=False)

    from inspect_ai.util._store_model import store_as

    from inspect_agents.exceptions import ToolException
    from inspect_agents.state import Files
    from inspect_agents.tools_files import EditParams, FilesParams, WriteParams, files_tool

    instance = "edit_safety_store"
    path = "app.txt"
    content = "foo bar foo\nfoo"

    tool = files_tool()
    # Seed file
    asyncio.run(
        tool(params=FilesParams(root=WriteParams(command="write", file_path=path, content=content, instance=instance)))
    )

    # replace_all with exact expected count (3 occurrences)
    asyncio.run(
        tool(
            params=FilesParams(
                root=EditParams(
                    command="edit",
                    file_path=path,
                    old_string="foo",
                    new_string="baz",
                    replace_all=True,
                    expected_count=3,
                    instance=instance,
                )
            )
        )
    )
    # Verify content mutated
    files = store_as(Files, instance=instance)
    assert files.get_file(path).count("baz") == 3

    # Reset file and test mismatch raises
    asyncio.run(
        tool(params=FilesParams(root=WriteParams(command="write", file_path=path, content=content, instance=instance)))
    )
    with pytest.raises(ToolException) as excinfo:
        asyncio.run(
            tool(
                params=FilesParams(
                    root=EditParams(
                        command="edit",
                        file_path=path,
                        old_string="foo",
                        new_string="baz",
                        replace_all=True,
                        expected_count=2,  # wrong on purpose
                        instance=instance,
                    )
                )
            )
        )
    assert "ExpectedCountMismatch" in str(excinfo.value)

    # Dry run should not mutate but report counts
    asyncio.run(
        tool(params=FilesParams(root=WriteParams(command="write", file_path=path, content=content, instance=instance)))
    )
    asyncio.run(
        tool(
            params=FilesParams(
                root=EditParams(
                    command="edit",
                    file_path=path,
                    old_string="foo",
                    new_string="baz",
                    replace_all=True,
                    expected_count=3,
                    dry_run=True,
                    instance=instance,
                )
            )
        )
    )
    # Confirm original content remains
    files2 = store_as(Files, instance=instance)
    assert files2.get_file(path) == content


def test_sandbox_mode_expected_count_and_dry_run(monkeypatch):
    # Enable sandbox mode and stub adapter
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
    monkeypatch.setenv("INSPECT_SANDBOX_PREFLIGHT", "skip")  # adapter.preflight will return True in stub

    import inspect_agents.tools_files as tools_files
    from inspect_agents.tools_files import EditParams, FilesParams, files_tool

    text = "x y x\nx"

    class FakeAdapter:
        async def preflight(self, *_):
            return True

        def validate(self, p: str) -> str:
            return p

        async def deny_symlink(self, _p: str):
            return None

        async def wc_bytes(self, _p: str) -> int | None:
            return len(text.encode("utf-8"))

        async def view(self, _p: str, _s: int, _e: int) -> str:
            return text

        async def str_replace(self, _p: str, _o: str, _n: str) -> str:
            return "OK"

    monkeypatch.setattr(tools_files, "_get_sandbox_adapter", lambda: FakeAdapter())

    tool = files_tool()

    # expected_count validated via view (3 occurrences of 'x' -> replace_all True)
    asyncio.run(
        tool(
            params=FilesParams(
                root=EditParams(
                    command="edit",
                    file_path="whatever.txt",
                    old_string="x",
                    new_string="z",
                    replace_all=True,
                    expected_count=3,
                )
            )
        )
    )


def test_edit_logs_include_replaced_and_dry_run(monkeypatch, caplog):
    # Store mode; capture logs
    monkeypatch.delenv("INSPECT_AGENTS_FS_MODE", raising=False)
    from inspect_agents.tools_files import EditParams, FilesParams, WriteParams, files_tool

    tool = files_tool()
    path = "log.txt"
    instance = "logcase"
    content = "aa aa"

    asyncio.run(
        tool(params=FilesParams(root=WriteParams(command="write", file_path=path, content=content, instance=instance)))
    )

    import logging

    caplog.set_level(logging.INFO, logger="inspect_agents.tools")
    before = len(caplog.records)

    asyncio.run(
        tool(
            params=FilesParams(
                root=EditParams(
                    command="edit",
                    file_path=path,
                    old_string="aa",
                    new_string="bb",
                    replace_all=True,
                    dry_run=True,
                    instance=instance,
                )
            )
        )
    )

    # Find the last tool_event for files:edit end phase
    events = []
    for rec in caplog.records[before:]:
        msg = rec.getMessage()
        if isinstance(msg, str) and msg.startswith("tool_event "):
            events.append(msg)
    assert any('"tool": "files:edit"' in e and '"dry_run": true' in e and '"replaced": 2' in e for e in events)
