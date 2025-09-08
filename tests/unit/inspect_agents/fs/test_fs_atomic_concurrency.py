import asyncio

from inspect_ai.util._store import Store, init_subtask_store

from inspect_agents.tools import edit_file, read_file, write_file


def _fresh_store() -> Store:
    s = Store()
    init_subtask_store(s)
    return s


def test_concurrent_edits_apply_both_changes():
    """Two overlapping edits on different substrings should both persist.

    This guards against lost updates where both tasks read the same base
    content and write their own version, potentially clobbering the other
    change. With per-path locking around the read-modify-write, the final
    content reflects both edits regardless of ordering.
    """

    _fresh_store()
    w = write_file()
    r = read_file()
    e = edit_file()

    async def _setup():
        await w(file_path="race.txt", content="ABCDEF")

    asyncio.run(_setup())

    async def _edit_a():
        # Replace AB -> ab
        await e(file_path="race.txt", old_string="AB", new_string="ab", replace_all=False)

    async def _edit_b():
        # Replace CD -> cd
        await e(file_path="race.txt", old_string="CD", new_string="cd", replace_all=False)

    async def _race():
        # Launch concurrently to exercise locking
        t1 = asyncio.create_task(_edit_a())
        t2 = asyncio.create_task(_edit_b())
        await asyncio.gather(t1, t2)
        return await r(file_path="race.txt")

    out = asyncio.run(_race())
    # Expect both edits applied regardless of ordering
    assert out.endswith("abcdEF")
