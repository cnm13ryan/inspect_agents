"""Streaming reads for large files (sandbox mode).

Verifies that execute_read() consumes adapter.view_chunks() in windows,
preserves numbering and 2000-char caps, and honors byte-ceiling preflight.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest


@pytest.mark.asyncio
async def test_read_streaming_sandbox_legacy_output(monkeypatch: pytest.MonkeyPatch) -> None:
    # Enable sandbox mode and skip preflight to avoid env dependencies
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
    monkeypatch.setenv("INSPECT_SANDBOX_PREFLIGHT", "skip")
    monkeypatch.setenv("INSPECT_AGENTS_FS_CHUNK_LINES", "2")  # force multiple chunks

    import inspect_agents.tools_files as tools_files
    from inspect_agents.tools_files import FilesParams, ReadParams, files_tool

    # Sample content spanning multiple chunks with one very long line (to test 2000-char cap)
    long_line = "x" * 2500
    content_lines = ["l1", "l2", "l3", long_line, "l5"]

    class FakeAdapter:
        def __init__(self) -> None:
            self.yields: int = 0

        async def preflight(self, *_: object) -> bool:
            return True

        def validate(self, p: str) -> str:
            return p

        async def deny_symlink(self, _p: str) -> None:  # pragma: no cover - behaviorless
            return None

        async def wc_bytes(self, _p: str) -> int | None:
            return len("\n".join(content_lines).encode("utf-8"))

        # view() should not be used by streaming path; guard just in case
        async def view(self, *_: object) -> str:  # pragma: no cover - defensive
            raise AssertionError("view() should not be called when view_chunks is available")

        async def view_chunks(
            self, _path: str, start_line: int, max_lines: int, *, chunk_size_lines: int = 512
        ) -> AsyncIterator[str]:
            assert start_line == 1
            assert chunk_size_lines == 2  # from env above
            # Respect max_lines when set (0 means unbounded in caller)
            limit = None if max_lines <= 0 else max_lines
            idx = 0
            while idx < len(content_lines) and (limit is None or limit > 0):
                take = min(chunk_size_lines, len(content_lines) - idx)
                if limit is not None:
                    take = min(take, limit)
                chunk = "\n".join(content_lines[idx : idx + take])
                self.yields += 1
                yield chunk
                idx += take
                if limit is not None:
                    limit -= take

    adapter = FakeAdapter()
    monkeypatch.setattr(tools_files, "_get_sandbox_adapter", lambda: adapter)
    # Legacy output (string), not typed results
    monkeypatch.setattr(tools_files, "_use_typed_results", lambda: False)

    tool = files_tool()
    params = FilesParams(root=ReadParams(command="read", file_path="big.txt", offset=0, limit=5))
    out = await tool(params)

    assert isinstance(out, str)
    lines = out.splitlines()
    # Numbering should be 1-based with padding (6 chars)
    assert lines[0].startswith("     1\t")
    assert lines[1].startswith("     2\t")
    assert lines[2].startswith("     3\t")
    assert lines[3].startswith("     4\t")
    assert lines[4].startswith("     5\t")
    # Long line is truncated to 2000 chars after the tab
    number_tab, truncated = lines[3].split("\t", 1)
    assert len(truncated) == 2000
    # Should have streamed via multiple yields
    assert adapter.yields >= 2


@pytest.mark.asyncio
async def test_read_streaming_sandbox_typed_results(monkeypatch: pytest.MonkeyPatch) -> None:
    # Enable sandbox mode and skip preflight
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
    monkeypatch.setenv("INSPECT_SANDBOX_PREFLIGHT", "skip")

    import inspect_agents.tools_files as tools_files
    from inspect_agents.tools_files import FileReadResult, FilesParams, ReadParams, files_tool

    content_lines = ["a", "b", "c"]

    class FakeAdapter:
        async def preflight(self, *_: object) -> bool:
            return True

        def validate(self, p: str) -> str:
            return p

        async def deny_symlink(self, _p: str) -> None:  # pragma: no cover - behaviorless
            return None

        async def wc_bytes(self, _p: str) -> int | None:
            return len("\n".join(content_lines).encode("utf-8"))

        async def view_chunks(
            self, _path: str, start_line: int, max_lines: int, *, chunk_size_lines: int = 512
        ) -> AsyncIterator[str]:
            assert start_line == 1
            # Emit everything in one chunk to keep this case simple
            yield "\n".join(content_lines)

    monkeypatch.setattr(tools_files, "_get_sandbox_adapter", lambda: FakeAdapter())
    monkeypatch.setattr(tools_files, "_use_typed_results", lambda: True)

    tool = files_tool()
    params = FilesParams(root=ReadParams(command="read", file_path="x.txt", offset=0, limit=2))
    result = await tool(params)

    assert isinstance(result, FileReadResult)
    # For typed results, lines are unpadded numbers with tabs
    assert result.lines == ["1\ta", "2\tb"]


@pytest.mark.asyncio
async def test_read_streaming_sandbox_size_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    # Enable sandbox mode and skip preflight
    monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
    monkeypatch.setenv("INSPECT_SANDBOX_PREFLIGHT", "skip")

    import inspect_agents.tools_files as tools_files
    from inspect_agents.tools_files import FilesParams, ReadParams, files_tool

    class FakeAdapter:
        async def preflight(self, *_: object) -> bool:
            return True

        def validate(self, p: str) -> str:
            return p

        async def deny_symlink(self, _p: str) -> None:  # pragma: no cover - behaviorless
            return None

        async def wc_bytes(self, _p: str) -> int | None:
            return 150  # Larger than the patched max below

        async def view_chunks(
            self, *_: object, **__: object
        ) -> AsyncIterator[str]:  # pragma: no cover - shouldn't be used
            yield "should not be read"

    # Patch adapter and small max_bytes to trigger preflight error
    monkeypatch.setattr(tools_files, "_get_sandbox_adapter", lambda: FakeAdapter())
    monkeypatch.setattr(tools_files, "_max_bytes", lambda: 100)

    tool = files_tool()
    params = FilesParams(root=ReadParams(command="read", file_path="too_big.txt"))

    with pytest.raises(Exception) as exc_info:
        await tool(params)
    msg = str(exc_info.value)
    assert "exceeds maximum size limit" in msg
    assert "150 bytes > 100 bytes" in msg
