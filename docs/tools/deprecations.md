---
title: "Deprecations & Migrations — File Tools"
status: draft
kind: docs
mode: stateless
owner: docs
---

# Deprecations & Migrations — File Tools

Purpose: provide a single, copy‑pasteable guide to migrate from legacy file wrappers to the unified `files` tool. Wrappers remain available for backward compatibility; prefer `files` for new work.

## Deprecation Warnings
- The legacy wrappers now emit a `DeprecationWarning` when executed to steer migrations.
- Visibility: set `PYTHONWARNINGS=default` (or run `pytest` without suppressing `DeprecationWarning`) to surface the notice.
- CI noise control: set `INSPECT_AGENTS_SUPPRESS_TOOL_WRAPPER_WARN=1` to suppress wrapper warnings in automated runs.

## At‑a‑Glance Mapping

| Legacy wrapper | Unified command | Notes |
| --- | --- | --- |
| `read_file` | `files` with `{ command: "read" }` | Same defaults: `offset=0`, `limit=2000` lines, per‑line 2000‑char truncation. |
| `write_file` | `files` with `{ command: "write" }` | Writes or creates a path in the virtual store/sandbox. |
| `edit_file` | `files` with `{ command: "edit" }` | Supports `replace_all`; unified tool also supports `expected_count`, `dry_run`. |
| `delete_file` | `files` with `{ command: "delete" }` | Store‑mode only; sandbox mode intentionally disables delete. |

Basis: each wrapper is a backward‑compatible shim that delegates to `files_tool()` internally.

## Before/After Examples

### read_file → files(read)

Before (wrapper)
```json
{ "file_path": "README.md", "offset": 0, "limit": 200 }
```

After (unified)
```json
{ "params": { "command": "read", "file_path": "README.md", "offset": 0, "limit": 200 } }
```

### write_file → files(write)

Before (wrapper)
```json
{ "file_path": "docs/note.md", "content": "Hello" }
```

After (unified)
```json
{ "params": { "command": "write", "file_path": "docs/note.md", "content": "Hello" } }
```

### edit_file → files(edit)

Before (wrapper)
```json
{ "file_path": "app.py", "old_string": "foo()", "new_string": "bar()", "replace_all": false }
```

After (unified; safer)
```json
{ "params": { "command": "edit", "file_path": "app.py", "old_string": "foo()", "new_string": "bar()", "replace_all": false, "expected_count": 1 } }
```

Optional dry‑run
```json
{ "params": { "command": "edit", "file_path": "README.md", "old_string": "v1.0", "new_string": "v2.0", "replace_all": true, "dry_run": true } }
```

Wrapper parity
```json
// The wrapper also accepts these safety fields for convenience
{ "file_path": "app.py", "old_string": "foo()", "new_string": "bar()", "expected_count": 1, "dry_run": true }
```

### delete_file → files(delete)

Before (wrapper)
```json
{ "file_path": "docs/note.md" }
```

After (unified)
```json
{ "params": { "command": "delete", "file_path": "docs/note.md" } }
```

Store‑mode only
- Delete is disabled in sandbox mode by design. Use `INSPECT_AGENTS_FS_MODE=store` for delete operations.

## Sandbox vs Store Notes
- Sandbox (`INSPECT_AGENTS_FS_MODE=sandbox`): read/write/edit route via the host editor; delete is disabled. Paths are confined under `INSPECT_AGENTS_FS_ROOT` and symlinks are denied.
- Store (`INSPECT_AGENTS_FS_MODE=store`, default): all operations use the in‑memory virtual Files store; delete is supported.

## Why migrate?
- One tool to learn and document; consistent safety knobs (`expected_count`, `dry_run`, byte ceilings).
- Typed results support for richer, structured outputs when `INSPECT_AGENTS_TYPED_RESULTS=1`.

## Related Docs
- Unified tool: [files](files.md)
- Wrappers: [read_file](read_file.md), [write_file](write_file.md), [edit_file](edit_file.md), [delete_file](delete_file.md)
