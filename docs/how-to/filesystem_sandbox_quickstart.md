# Filesystem Sandbox — Quickstart (inspect_agents)

This page summarizes how the filesystem tools behave in sandbox mode and shows how to enable it safely. For full details, see the comprehensive guide: [Filesystem Tools — Store vs Sandbox](filesystem.md).

## What sandbox mode does

- Routes `ls`, `read_file`, `write_file`, `edit_file`, and `files` operations through Inspect’s sandbox tools (`text_editor`, `bash_session`) after a lightweight preflight. Operations are confined under a root (default `/repo`), symlinks are denied, and a size ceiling applies. Deletion is intentionally disabled in sandbox mode.  
  See: filesystem.md (Modes, Routing, Delete Policy, Confinement & Symlinks).

## Enable sandbox mode

```bash
export INSPECT_AGENTS_FS_MODE=sandbox         # enable sandbox FS routing
export INSPECT_AGENTS_FS_ROOT=/repo          # absolute root for confinement (default: /repo)

# Optional: preflight behavior
export INSPECT_SANDBOX_PREFLIGHT=auto        # auto|skip|force (default auto)
export INSPECT_SANDBOX_PREFLIGHT_TTL_SEC=300 # cache result (seconds)
```

Behavior:
- `auto` (default): check once and fall back to in‑memory store if the sandbox is unavailable; emit a one‑time warning.
- `skip`: don’t check; behave as not ready (store fallback) without a warning (useful for tests/CI).
- `force`: require sandbox; raise immediately if unavailable.

## Read‑only posture (optional)

```bash
export INSPECT_AGENTS_FS_MODE=sandbox
export INSPECT_AGENTS_FS_READ_ONLY=1   # allow ls/read; block write/edit/delete
```

When enabled, write/edit/delete return a short error (`SandboxReadOnly`). Use this for demos or regulated workflows.

## Delete policy

- `delete_file` is supported only in store mode. In sandbox mode, delete is disabled and returns `SandboxUnsupported` (or `SandboxReadOnly` when read‑only is set). Prefer the unified `files` tool with the `trash` command to move paths into a per‑run trash directory under `/.trash/<unix_ts>/…`.

## Path policies and safety

- Confinement: paths must reside under `INSPECT_AGENTS_FS_ROOT`; out‑of‑root access is rejected before editor calls.
- Symlink denial: operations are denied on symlinks for safety.
- Size ceiling: `INSPECT_AGENTS_FS_MAX_BYTES` caps read/edit/write sizes.
- Optional allow/deny globs (evaluated relative to the root):
  - `INSPECT_FS_DENY` — comma‑separated patterns to deny.
  - `INSPECT_FS_ALLOW` — when set, only matched paths are allowed; non‑matches are implicitly denied.

## Minimal example (with fallback semantics)

```python
import asyncio, os

# Enable sandbox; when preflight fails, tools fall back to the in‑memory store
os.environ["INSPECT_AGENTS_FS_MODE"] = "sandbox"

from inspect_agents.tools import write_file, read_file, ls

async def main():
    w = write_file(); r = read_file(); l = ls()
    await w(file_path="/repo/demo.txt", content="Hello\nSandbox")
    print(await l())                      # may show ["/repo/demo.txt"]
    print(await r(file_path="/repo/demo.txt", offset=0, limit=10))

asyncio.run(main())
```

Notes
- In environments without a ready sandbox provider, the example transparently falls back to store mode (no host FS writes) and logs a one‑time preflight warning in the tool events stream.
- To strictly require sandbox routing, set `INSPECT_SANDBOX_PREFLIGHT=force`.

## Sandbox mode errors (quick examples)

Catch `ToolException` and print short error codes/messages you can expect in sandbox mode.

```python
import asyncio, os
from inspect_agents.exceptions import ToolException

# Always enable sandbox mode for these examples
os.environ["INSPECT_AGENTS_FS_MODE"] = "sandbox"

async def main():
    # 1) SandboxUnsupported — delete is disabled in sandbox mode
    try:
        from inspect_agents.tools import delete_file
        d = delete_file()
        await d(file_path="/repo/blocked.txt")
    except ToolException as e:
        print("delete:", str(e))     # → SandboxUnsupported

    # 2) SandboxReadOnly — write/edit/delete blocked when read-only flag is set
    os.environ["INSPECT_AGENTS_FS_READ_ONLY"] = "1"
    try:
        from inspect_agents.tools import write_file
        w = write_file()
        await w(file_path="/repo/ro.txt", content="x")
    except ToolException as e:
        print("write:", str(e))      # → SandboxReadOnly
    finally:
        os.environ["INSPECT_AGENTS_FS_READ_ONLY"] = "0"

    # 3) PolicyDenied — path matches a deny/allow policy
    os.environ["INSPECT_FS_DENY"] = "secret/**"
    try:
        from inspect_agents.tools_files import files_tool, FilesParams, TrashParams
        tool = files_tool()
        await tool(params=FilesParams(root=TrashParams(command="trash", file_path="/repo/secret/a.txt")))
    except ToolException as e:
        # Message includes details; detect by substring
        print("trash:", "PolicyDenied" if "PolicyDenied" in str(e) else str(e))

asyncio.run(main())
```

Tip: `PolicyDenied` messages include the matching rule and the effective root; see the “Path policies and safety” section above.

## See also
- Full guide: [Filesystem Tools — Store vs Sandbox](filesystem.md)
- Approvals and presets: [Approvals & Policies](approvals.md)
