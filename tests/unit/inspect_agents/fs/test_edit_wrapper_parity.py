import asyncio


def test_edit_file_wrapper_accepts_expected_count_and_dry_run(monkeypatch):
    # Store mode
    monkeypatch.delenv("INSPECT_AGENTS_FS_MODE", raising=False)
    monkeypatch.delenv("INSPECT_AGENTS_TYPED_RESULTS", raising=False)

    from inspect_agents.tools import edit_file, write_file
    from inspect_agents.tools_files import FilesParams, ReadParams, files_tool

    # Seed
    w = write_file()
    asyncio.run(w(file_path="w.txt", content="foo foo", instance="wrap"))

    # Dry run: should not mutate but report replaced=2 in typed mode when enabled; here we just ensure it doesn't error
    e = edit_file()
    asyncio.run(
        e(
            file_path="w.txt",
            old_string="foo",
            new_string="bar",
            replace_all=True,
            expected_count=2,
            dry_run=True,
            instance="wrap",
        )
    )

    # Apply with expected_count=2
    asyncio.run(
        e(file_path="w.txt", old_string="foo", new_string="bar", replace_all=True, expected_count=2, instance="wrap")
    )

    # Verify mutated via unified reader
    f = files_tool()
    out = asyncio.run(
        f(params=FilesParams(root=ReadParams(command="read", file_path="w.txt", offset=0, limit=10, instance="wrap")))
    )
    if isinstance(out, str):
        assert "bar" in out
    else:
        # typed result (lines)
        joined = "\n".join(out.lines)
        assert "bar" in joined
