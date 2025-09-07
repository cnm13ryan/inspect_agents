---
title: "edit_file Reference"
status: draft
kind: builtin
mode: stateless
owner: docs
---

# edit_file

## Overview
- Performs a single‑string replace (first occurrence by default; or all with a flag) and writes the result back.
- Use for targeted, atomic edits.
- Classification: stateless.

## Parameters
- file_path: string — Target file. Required.
- old_string: string — Text to replace. Required.
- new_string: string — Replacement text. Required.
- replace_all: bool — Replace all occurrences when true (default: false).
- instance: string — Optional `Files` instance name for isolation.

### Safer Edits (via unified `files` tool)
- expected_count: int | null — Assert how many replacements should occur. On mismatch, the operation errors with `ExpectedCountMismatch: expected X, got Y` and nothing is written.
- dry_run: bool — When true, perform validation/counting and return the number of replacements that would occur, but do not modify the file.

Notes
- The deprecated `edit_file` wrapper now also accepts `expected_count` and `dry_run` for parity. Prefer the unified [`files`](files.md) tool for new integrations.

## Result Schema
- Default: string — Summary message (e.g., “Updated file <path>”).
- Typed (when `INSPECT_AGENTS_TYPED_RESULTS=1`): `{ path: string, replaced: int, summary: string }` (`FileEditResult`).
  - Note: In sandbox mode the reported `replaced` count may be approximate.
  - When `dry_run=true`, no mutation occurs; `replaced` reports the count that would be applied.

## Timeouts & Limits
- Execution timeout: 15s; no explicit size cap; string replace semantics.

## Sandbox Notes
- When `INSPECT_AGENTS_FS_MODE=sandbox` and sandbox is available, routes to `text_editor('str_replace', path, old_str, new_str)`. If the sandbox is unavailable, it falls back to the in‑memory store.
- Delete operations are disabled in sandbox mode (applies across file tools); `delete_file` is store‑only.
- `expected_count` and `dry_run` behavior (when using `files`): because the editor does not return a replacement count, the tool performs a light pre‑read (`view`) to count occurrences when these flags are set. If the expected count mismatches, the edit is rejected before writing. In `dry_run` the write is skipped entirely.

## Examples
### Typed vs Legacy (quick look)

Args
```json
{"file_path": "app.py", "old_string": "foo", "new_string": "bar"}
```

Typed
```json
{ "path": "app.py", "replaced": 1, "summary": "Updated file app.py" }
```

Legacy
```
Updated file app.py
```

See also: [Typed Results vs Legacy Outputs](typed_results.md).

### Safer Edits via `files` (recommended)
Single replacement with count assertion
```json
{
  "params": {
    "command": "edit",
    "file_path": "app.py",
    "old_string": "foo()",
    "new_string": "bar()",
    "replace_all": false,
    "expected_count": 1
  }
}
```

Dry run preview, replace all
```json
{
  "params": {
    "command": "edit",
    "file_path": "README.md",
    "old_string": "v1.0",
    "new_string": "v2.0",
    "replace_all": true,
    "dry_run": true
  }
}
```

Mismatch example (raises)
```json
{
  "params": {
    "command": "edit",
    "file_path": "config.toml",
    "old_string": "port = 8080",
    "new_string": "port = 8081",
    "replace_all": true,
    "expected_count": 2
  }
}
```
Response: `ToolException: ExpectedCountMismatch: expected 2, got 1`

### Wrapper usage with safeguards
Although deprecated, the wrapper accepts the same safety fields for convenience:
```json
{
  "file_path": "app.py",
  "old_string": "foo()",
  "new_string": "bar()",
  "replace_all": false,
  "expected_count": 1,
  "dry_run": true
}
```

## Safety & Best Practices
- Prefer precise `old_string` values; test a single replacement before enabling `replace_all`.
- For bulk edits, use `dry_run=true` first, then apply with `expected_count` to guard against drift.

## Troubleshooting
- String not found — Verify the exact `old_string` (including whitespace and casing).
- ExpectedCountMismatch — Your `expected_count` does not match how many replacements would be applied (1 when `replace_all=false`; else the number of occurrences). Adjust the expectation or the query.

## Source of Truth
- Code: src/inspect_agents/tools_files.py (execute_edit), src/inspect_agents/tools.py (edit_file wrapper)
- See also: [files](files.md) (unified files tool)
