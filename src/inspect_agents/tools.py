from __future__ import annotations

# ruff: noqa: E402
"""Inspect‑native tools for Inspect Agents.

Currently includes:
- write_todos: update the shared Todos list in the Store
"""

import os
import warnings
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

# Avoid importing inspect_ai.tool at module import time; tests stub package
if TYPE_CHECKING:  # pragma: no cover - only for type checkers
    from inspect_ai.tool._tool import Tool  # noqa: F401
    from inspect_ai.tool._tool_def import ToolDef  # noqa: F401
    from inspect_ai.tool._tool_params import ToolParams  # noqa: F401
    from inspect_ai.util._json import json_schema  # noqa: F401
    from inspect_ai.util._store_model import store_as  # noqa: F401

import json
import logging

from . import fs as _fs
from .exceptions import ToolException
from .settings import (
    truthy as _truthy,
)
from .settings import (
    typed_results_enabled as _use_typed_results,
)
from .state import Todo, Todos
from .tools_files import (
    DeleteParams,
    EditParams,
    FileDeleteResult,
    FileEditResult,
    FileListResult,
    FileMoveResult,
    FileReadResult,
    FilesParams,
    FileStatResult,
    FileWriteResult,
    LsParams,
    MkdirParams,
    MoveParams,
    ReadParams,
    StatParams,
    WriteParams,
    files_tool,
)


def _redact_and_truncate(payload: dict[str, Any] | None, max_len: int | None = None) -> dict[str, Any]:
    # Backwards-compat shim: delegate to observability
    from .observability import _redact_and_truncate as _impl

    return _impl(payload, max_len)


def _log_tool_event(
    name: str,
    phase: str,
    args: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
    t0: float | None = None,
) -> float:
    """Backward-compat wrapper delegating to observability.log_tool_event."""
    from .observability import log_tool_event as _impl

    return _impl(name=name, phase=phase, args=args, extra=extra, t0=t0)


# Deprecation helper for legacy file tool wrappers
def _warn_wrapper(name: str) -> None:
    """Emit a deprecation warning for legacy wrapper tools.

    Suppressed when INSPECT_AGENTS_SUPPRESS_TOOL_WRAPPER_WARN=1 to keep CI quiet.
    """
    try:
        if os.getenv("INSPECT_AGENTS_SUPPRESS_TOOL_WRAPPER_WARN") in {"1", "true", "True", "YES", "yes"}:
            return
        warnings.warn(
            (
                f"{name} is deprecated and will be removed in a future release. "
                "Use files_tool() instead (e.g., files_tool()(params=FilesParams(root=...)))."
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        # Optional notice log for observability
        try:
            _log_tool_event(name=name, phase="notice", extra={"deprecated_wrapper": True})
        except Exception:
            pass
    except Exception:
        # Never fail a tool call due to warning machinery
        pass


# ToolException is provided centrally via inspect_agents.exceptions


# Delegate FS mode helpers to consolidated fs module for consistency
_fs_mode = _fs.fs_mode  # backward-compatible alias for tests/patch points
_use_sandbox_fs = _fs.use_sandbox_fs  # backward-compatible alias


## Delegated env helpers (centralized in settings.py)
## Keep symbol names for backward-compatible test patch points.


class TodoWriteResult(BaseModel):
    """Typed result for write_todos operations."""

    count: int
    summary: str


class TodoStatusResult(BaseModel):
    """Typed result for update_todo_status operations."""

    index: int
    status: str
    warning: str | None
    summary: str


def standard_tools() -> list[object]:
    """Return a list of standard Inspect‑AI tools.

    Controlled by environment flags to keep defaults safe:

    - INSPECT_ENABLE_THINK: enable `think()` (default: true)
    - INSPECT_ENABLE_WEB_SEARCH: enable `web_search(...)` when a provider is available
      (default: auto if Tavily or Google keys are set)
    - INSPECT_ENABLE_EXEC: enable `bash()` and `python()` (default: false)
    - INSPECT_ENABLE_WEB_BROWSER: enable `web_browser(...)` tools (default: false)
    - INSPECT_ENABLE_TEXT_EDITOR_TOOL: expose `text_editor()` as a tool (default: false)

    Notes:
    - Our file tools (read_file/write_file/edit_file/ls) already use `text_editor`
      internally when `INSPECT_AGENTS_FS_MODE=sandbox`; exposing `text_editor()`
      directly is optional and disabled by default.
    - Web search providers are auto‑configured using environment variables:
      Tavily (TAVILY_API_KEY) or Google CSE (GOOGLE_CSE_ID/GOOGLE_CSE_API_KEY).
    """
    tools: list[object] = []

    # Local imports to avoid heavy imports at module import time
    try:
        from inspect_ai.tool import think, web_search
        from inspect_ai.tool._tools._execute import bash
        from inspect_ai.tool._tools._execute import python as py_exec
        from inspect_ai.tool._tools._text_editor import text_editor
        from inspect_ai.tool._tools._web_browser import web_browser
    except Exception:
        # If inspect_ai is stubbed in tests, just return empty; callers can still use our built‑ins
        return tools

    # think()
    if not os.getenv("INSPECT_ENABLE_THINK") or _truthy(os.getenv("INSPECT_ENABLE_THINK", "1")):
        try:
            tools.append(think())
        except Exception:
            pass

    # web_search(...)
    enable_web_search_env = os.getenv("INSPECT_ENABLE_WEB_SEARCH")
    enable_web_search = (
        _truthy(enable_web_search_env)
        if enable_web_search_env is not None
        else (os.getenv("TAVILY_API_KEY") or (os.getenv("GOOGLE_CSE_ID") and os.getenv("GOOGLE_CSE_API_KEY")))
        is not None
    )
    if enable_web_search:
        try:
            providers_cfg: list[object] = []
            # Prefer internal provider if user explicitly requests via INSPECT_WEB_SEARCH_INTERNAL
            internal = (os.getenv("INSPECT_WEB_SEARCH_INTERNAL") or "").strip().lower()
            if internal in {"openai", "anthropic", "perplexity", "gemini", "grok"}:
                providers_cfg.append(internal)

            # Add external providers based on available credentials
            if os.getenv("TAVILY_API_KEY"):
                providers_cfg.append({"tavily": True})
            if os.getenv("GOOGLE_CSE_ID") and os.getenv("GOOGLE_CSE_API_KEY"):
                providers_cfg.append({"google": True})

            providers = providers_cfg or None
            tools.append(web_search(providers))
        except Exception:
            # If provider configuration is invalid or missing, skip silently
            pass

    # bash() and python() (disabled by default)
    if _truthy(os.getenv("INSPECT_ENABLE_EXEC")):
        try:
            tools.extend([bash(), py_exec()])
        except Exception:
            pass

    # web_browser (disabled by default; heavy)
    if _truthy(os.getenv("INSPECT_ENABLE_WEB_BROWSER")):
        try:
            tools.extend(web_browser())
        except Exception:
            pass

    # text_editor (disabled by default; only meaningful with sandbox FS)
    if _truthy(os.getenv("INSPECT_ENABLE_TEXT_EDITOR_TOOL")) and _use_sandbox_fs():
        try:
            tools.append(text_editor())
        except Exception:
            pass

    # Defensive policy: never surface any stateful shell session tool here.
    # In this repo, `bash_session` is reserved for internal FS sandbox plumbing
    # (see fs_adapter) and must not be exposed via the public `standard_tools()`
    # helper regardless of upstream defaults or env toggles.
    try:
        filtered: list[object] = []
        for t in tools:
            try:
                name = getattr(t, "name", None) or getattr(t, "__name__", None)
                if isinstance(name, str) and name.strip().lower() == "bash_session":
                    logging.getLogger(__name__).warning(
                        "Filtered out stateful tool 'bash_session' from standard_tools (internal-only)."
                    )
                    continue
            except Exception:
                # If we cannot introspect, keep the tool (fail-open) — tests enforce the policy.
                pass
            filtered.append(t)
        tools = filtered
    except Exception:
        # Never fail construction due to filtering; tests will catch regressions.
        pass

    return tools


def write_todos():  # -> Tool
    """Update the shared todo list.

    Accepts a list of todos and writes them to the shared Todos model in the
    current Inspect Store, returning a human-readable confirmation string.
    """

    # Local imports to avoid executing inspect_ai.tool __init__ during module import
    from inspect_ai.tool._tool import tool
    from inspect_ai.tool._tool_def import ToolDef
    from inspect_ai.tool._tool_params import ToolParams
    from inspect_ai.util._json import json_schema
    from inspect_ai.util._store_model import store_as

    @tool
    def _factory() -> Tool:
        async def execute(todos: list[Todo]) -> str | TodoWriteResult:
            # Add Pydantic validation layer for early error detection
            try:
                from .tool_types import TodoItem, WriteTodosParams

                # Convert Todo objects to TodoItem format for validation
                todo_items = []
                for todo in todos:
                    if hasattr(todo, "model_dump"):
                        todo_dict = todo.model_dump()
                    else:
                        # Handle case where todo might be a string or have different structure
                        if hasattr(todo, "content"):
                            content = todo.content
                        elif hasattr(todo, "text"):
                            content = todo.text
                        else:
                            content = str(todo)
                        todo_dict = {"content": content, "status": getattr(todo, "status", "pending")}
                    todo_items.append(TodoItem.model_validate(todo_dict))

                # Validate the complete parameters
                WriteTodosParams.model_validate({"todos": todo_items})
            except ImportError:
                # If tool_types not available, skip validation
                pass
            except Exception as e:
                raise ToolException(f"Invalid todo parameters: {str(e)}")

            _t0 = _log_tool_event(
                name="write_todos",
                phase="start",
                args={
                    "todos": [getattr(t, "title", None) or getattr(t, "text", None) or "todo" for t in todos],
                    "count": len(todos),
                },
            )
            model = store_as(Todos)
            model.set_todos(todos)
            rendered = [t.model_dump() if hasattr(t, "model_dump") else t for t in model.todos]
            summary = f"Updated todo list to {rendered}"
            _log_tool_event(
                name="write_todos",
                phase="end",
                extra={"ok": True, "count": len(todos)},
                t0=_t0,
            )
            if _use_typed_results():
                return TodoWriteResult(count=len(todos), summary=summary)
            return summary

        params = ToolParams()
        params.properties["todos"] = json_schema(list[Todo])  # type: ignore[arg-type]
        params.properties["todos"].description = "List of todo items to write"
        params.required.append("todos")

        return ToolDef(
            execute,
            name="write_todos",
            description="Update the shared todo list.",
            parameters=params,
        ).as_tool()

    return _factory()


def update_todo_status(*args, **kwargs):  # -> Tool or Awaitable
    """Update the status of a single todo item with validation.

    Behavior:
    - Called with no args/kwargs: returns a Tool instance (factory mode).
    - Called with parameters: returns an awaitable executing the tool (legacy direct-call compatibility).

    Enforces transitions: pending->in_progress, in_progress->completed.
    Allows pending->completed only when allow_direct_complete=True.
    Returns a JSON payload with optional 'warning' field when direct completion occurs.
    """

    from inspect_ai.tool._tool import tool
    from inspect_ai.tool._tool_def import ToolDef
    from inspect_ai.tool._tool_params import ToolParams
    from inspect_ai.util._json import json_schema
    from inspect_ai.util._store_model import store_as

    @tool
    def _factory() -> Tool:
        async def execute(
            todo_index: int,
            status: str,
            allow_direct_complete: bool = False,
        ) -> str | TodoStatusResult:
            # Add Pydantic validation layer for early error detection
            try:
                from .tool_types import UpdateTodoStatusParams

                # Validate all parameters using our stricter Pydantic model
                UpdateTodoStatusParams.model_validate(
                    {"todo_index": todo_index, "status": status, "allow_direct_complete": allow_direct_complete}
                )
            except ImportError:
                # If tool_types not available, skip validation
                pass
            except Exception as e:
                raise ToolException(f"Invalid todo status parameters: {str(e)}")

            _t0 = _log_tool_event(
                name="update_todo_status",
                phase="start",
                args={
                    "todo_index": todo_index,
                    "status": status,
                    "allow_direct_complete": allow_direct_complete,
                },
            )
            model = store_as(Todos)
            try:
                warning = model.update_status(
                    index=int(todo_index),
                    status=str(status),
                    allow_direct_complete=bool(allow_direct_complete),
                )

                message = f"Updated todo[{todo_index}] status to {status}"
                _log_tool_event(
                    name="update_todo_status",
                    phase="end",
                    extra={"ok": True, "warning": bool(warning)},
                    t0=_t0,
                )

                if _use_typed_results():
                    return TodoStatusResult(index=todo_index, status=status, warning=warning, summary=message)

                # Legacy JSON format for non-typed mode
                payload: dict = {
                    "ok": True,
                    "message": message,
                }
                if warning:
                    payload["meta"] = {"warning": warning}
                    try:
                        logging.getLogger(__name__).warning(warning)
                    except Exception:
                        pass
                return json.dumps(payload, ensure_ascii=False)
            except (IndexError, ValueError) as e:
                _log_tool_event(
                    name="update_todo_status",
                    phase="error",
                    extra={"ok": False, "error": type(e).__name__},
                    t0=_t0,
                )
                raise ToolException(f"Invalid todo operation: {str(e)}. Please check the todo index and status values.")
            except Exception as e:
                _log_tool_event(
                    name="update_todo_status",
                    phase="error",
                    extra={"ok": False, "error": type(e).__name__},
                    t0=_t0,
                )
                raise ToolException(f"Todo update failed: {str(e)}")

        params = ToolParams()
        params.properties["todo_index"] = json_schema(int)
        params.properties["todo_index"].description = "Index of the todo to update (0-based)"
        params.properties["status"] = json_schema(str)
        params.properties["status"].description = "New status: pending | in_progress | completed"
        params.properties["allow_direct_complete"] = json_schema(bool)
        params.properties["allow_direct_complete"].description = "Permit pending->completed directly (logs a warning)"
        params.properties["allow_direct_complete"].default = False
        params.required.extend(["todo_index", "status"])

        return ToolDef(
            execute,
            name="update_todo_status",
            description="Update the status of a single todo with validation.",
            parameters=params,
        ).as_tool()

    # Factory mode (no args): return a Tool
    if not args and not kwargs:
        return _factory()

    # Direct-call compatibility: return the awaitable from the Tool invocation
    tool_obj = _factory()
    return tool_obj(*args, **kwargs)


def ls():  # -> Tool
    """List all files in the Files store.

    DEPRECATED: Use files_tool() with command='ls' instead.
    This is a backward-compatible wrapper.

    Optionally scope to a Files(instance=...) for per-agent isolation.
    """
    from inspect_ai.tool._tool import tool
    from inspect_ai.tool._tool_def import ToolDef
    from inspect_ai.tool._tool_params import ToolParams
    from inspect_ai.util._json import json_schema

    @tool
    def _factory() -> Tool:
        async def execute(instance: str | None = None) -> list[str] | FileListResult:
            # Convert wrapper params to unified FilesParams and delegate to files tool
            params = LsParams(command="ls", instance=instance)
            files = files_tool()
            return await files(params=FilesParams(root=params))

        params = ToolParams()
        params.properties["instance"] = json_schema(str)
        params.properties["instance"].description = "Optional Files instance for isolation"

        return ToolDef(
            execute,
            name="ls",
            description="List all files in the virtual store.",
            parameters=params,
        ).as_tool()

    return _factory()


def read_file():  # -> Tool
    """Read a file with cat -n formatting and safety limits.

    DEPRECATED: Use files_tool() with command='read' instead.
    This is a backward-compatible wrapper.

    Mirrors legacy semantics: offset/limit by lines, per-line 2000-char truncation,
    and friendly error messages.
    """
    from inspect_ai.tool._tool import tool
    from inspect_ai.tool._tool_def import ToolDef
    from inspect_ai.tool._tool_params import ToolParams
    from inspect_ai.util._json import json_schema

    @tool
    def _factory() -> Tool:
        async def execute(
            file_path: str,
            offset: int = 0,
            limit: int = 2000,
            instance: str | None = None,
        ) -> str | FileReadResult:
            _warn_wrapper("read_file")
            # Convert wrapper params to unified FilesParams and delegate to files tool
            params = ReadParams(command="read", file_path=file_path, offset=offset, limit=limit, instance=instance)
            try:
                files = files_tool()
                return await files(params=FilesParams(root=params))
            except Exception as e:
                # Re-raise with correct ToolException type for backward compatibility
                if hasattr(e, "message") and e.message:
                    raise ToolException(e.message)
                else:
                    raise ToolException(str(e))

        params = ToolParams()
        params.properties["file_path"] = json_schema(str)
        params.properties["file_path"].description = "Path to read"
        params.properties["offset"] = json_schema(int)
        params.properties["offset"].description = "Line offset (0-based)"
        params.properties["offset"].default = 0
        params.properties["limit"] = json_schema(int)
        params.properties["limit"].description = "Max lines to return"
        params.properties["limit"].default = 2000
        params.properties["instance"] = json_schema(str)
        params.properties["instance"].description = "Optional Files instance for isolation"
        params.required.append("file_path")

        return ToolDef(
            execute,
            name="read_file",
            description="Read a file with numbered lines and truncation.",
            parameters=params,
        ).as_tool()

    return _factory()


def write_file():  # -> Tool
    """Write content to a file in the Files store.

    DEPRECATED: Use files_tool() with command='write' instead.
    This is a backward-compatible wrapper.
    """
    from inspect_ai.tool._tool import tool
    from inspect_ai.tool._tool_def import ToolDef
    from inspect_ai.tool._tool_params import ToolParams
    from inspect_ai.util._json import json_schema

    @tool
    def _factory() -> Tool:
        async def execute(
            file_path: str,
            content: str,
            instance: str | None = None,
        ) -> str | FileWriteResult:
            _warn_wrapper("write_file")
            # Convert wrapper params to unified FilesParams and delegate to files tool
            params = WriteParams(command="write", file_path=file_path, content=content, instance=instance)
            files = files_tool()
            return await files(params=FilesParams(root=params))

        params = ToolParams()
        params.properties["file_path"] = json_schema(str)
        params.properties["file_path"].description = "Path to write"
        params.properties["content"] = json_schema(str)
        params.properties["content"].description = "Content to write"
        params.properties["instance"] = json_schema(str)
        params.properties["instance"].description = "Optional Files instance for isolation"
        params.required.extend(["file_path", "content"])

        return ToolDef(
            execute,
            name="write_file",
            description="Write file content to the virtual store.",
            parameters=params,
        ).as_tool()

    return _factory()


def edit_file():  # -> Tool
    """Edit a file by replacing a string (first or all occurrences).

    DEPRECATED: Use files_tool() with command='edit' instead.
    This is a backward-compatible wrapper.
    """
    from inspect_ai.tool._tool import tool
    from inspect_ai.tool._tool_def import ToolDef
    from inspect_ai.tool._tool_params import ToolParams
    from inspect_ai.util._json import json_schema

    @tool
    def _factory() -> Tool:
        async def execute(
            file_path: str,
            old_string: str,
            new_string: str,
            replace_all: bool = False,
            expected_count: int | None = None,
            dry_run: bool = False,
            instance: str | None = None,
        ) -> str | FileEditResult:
            _warn_wrapper("edit_file")
            # Convert wrapper params to unified FilesParams and delegate to files tool
            params = EditParams(
                command="edit",
                file_path=file_path,
                old_string=old_string,
                new_string=new_string,
                replace_all=replace_all,
                expected_count=expected_count,
                dry_run=dry_run,
                instance=instance,
            )
            try:
                files = files_tool()
                return await files(params=FilesParams(root=params))
            except Exception as e:
                # Re-raise with correct ToolException type for backward compatibility
                if hasattr(e, "message") and e.message:
                    raise ToolException(e.message)
                else:
                    raise ToolException(str(e))

        params = ToolParams()
        params.properties["file_path"] = json_schema(str)
        params.properties["file_path"].description = "Path to edit"
        params.properties["old_string"] = json_schema(str)
        params.properties["old_string"].description = "String to replace"
        params.properties["new_string"] = json_schema(str)
        params.properties["new_string"].description = "Replacement string"
        params.properties["replace_all"] = json_schema(bool)
        params.properties["replace_all"].description = "Replace all occurrences if true"
        params.properties["replace_all"].default = False
        params.properties["expected_count"] = json_schema(int)
        params.properties[
            "expected_count"
        ].description = "Optional expected number of replacements; mismatches raise an error"
        params.properties["dry_run"] = json_schema(bool)
        params.properties["dry_run"].description = "When true, validate/count but do not modify the file"
        params.properties["dry_run"].default = False
        params.properties["instance"] = json_schema(str)
        params.properties["instance"].description = "Optional Files instance for isolation"
        params.required.extend(["file_path", "old_string", "new_string"])

        return ToolDef(
            execute,
            name="edit_file",
            description="Edit a file by replacing text.",
            parameters=params,
        ).as_tool()

    return _factory()


def delete_file():  # -> Tool
    """Delete a file from the Files store.

    This is a backward-compatible wrapper around files_tool() with command='delete'.
    Only works in store mode; sandbox mode is not yet supported.
    """
    from inspect_ai.tool._tool import tool
    from inspect_ai.tool._tool_def import ToolDef
    from inspect_ai.tool._tool_params import ToolParams
    from inspect_ai.util._json import json_schema

    @tool
    def _factory() -> Tool:
        async def execute(
            file_path: str,
            instance: str | None = None,
        ) -> str | FileDeleteResult:
            _warn_wrapper("delete_file")
            # Convert wrapper params to unified FilesParams and delegate to files tool
            params = DeleteParams(command="delete", file_path=file_path, instance=instance)
            try:
                files = files_tool()
                return await files(params=FilesParams(root=params))
            except Exception as e:
                # Re-raise with correct ToolException type for backward compatibility
                if hasattr(e, "message") and e.message:
                    raise ToolException(e.message)
                else:
                    raise ToolException(str(e))

        params = ToolParams()
        params.properties["file_path"] = json_schema(str)
        params.properties["file_path"].description = "Path to delete"
        params.properties["instance"] = json_schema(str)
        params.properties["instance"].description = "Optional Files instance for isolation"
        params.required.append("file_path")

        return ToolDef(
            execute,
            name="delete_file",
            description="Delete a file from the virtual store (store mode only).",
            parameters=params,
        ).as_tool()

    return _factory()


def mkdir():  # -> Tool
    """Create a directory (sandbox: mkdir; store: no-op) in the Files space.

    This is a thin wrapper around `files_tool()` with command='mkdir'.
    """
    from inspect_ai.tool._tool import tool
    from inspect_ai.tool._tool_def import ToolDef
    from inspect_ai.tool._tool_params import ToolParams
    from inspect_ai.util._json import json_schema

    @tool
    def _factory() -> Tool:  # type: ignore[override]
        async def execute(dir_path: str, instance: str | None = None) -> str:
            params = MkdirParams(command="mkdir", dir_path=dir_path, instance=instance)
            files = files_tool()
            return await files(params=FilesParams(root=params))

        params = ToolParams()
        params.properties["dir_path"] = json_schema(str)
        params.properties["dir_path"].description = "Directory path to create"
        params.properties["instance"] = json_schema(str)
        params.properties["instance"].description = "Optional Files instance for isolation"
        params.required.append("dir_path")

        return ToolDef(execute, name="mkdir", description="Create a directory", parameters=params).as_tool()

    return _factory()


def move_file():  # -> Tool
    """Move/rename a file within the Files space.

    Wrapper over `files_tool()` with command='move'.
    """
    from inspect_ai.tool._tool import tool
    from inspect_ai.tool._tool_def import ToolDef
    from inspect_ai.tool._tool_params import ToolParams
    from inspect_ai.util._json import json_schema

    @tool
    def _factory() -> Tool:  # type: ignore[override]
        async def execute(src_path: str, dst_path: str, instance: str | None = None) -> str | FileMoveResult:
            params = MoveParams(command="move", src_path=src_path, dst_path=dst_path, instance=instance)
            files = files_tool()
            return await files(params=FilesParams(root=params))

        params = ToolParams()
        params.properties["src_path"] = json_schema(str)
        params.properties["src_path"].description = "Source path"
        params.properties["dst_path"] = json_schema(str)
        params.properties["dst_path"].description = "Destination path"
        params.properties["instance"] = json_schema(str)
        params.properties["instance"].description = "Optional Files instance for isolation"
        params.required.extend(["src_path", "dst_path"])

        return ToolDef(execute, name="move_file", description="Move or rename a file", parameters=params).as_tool()

    return _factory()


def stat_file():  # -> Tool
    """Get basic path metadata (exists, type, size) in the Files space.

    Wrapper over `files_tool()` with command='stat'.
    """
    from inspect_ai.tool._tool import tool
    from inspect_ai.tool._tool_def import ToolDef
    from inspect_ai.tool._tool_params import ToolParams
    from inspect_ai.util._json import json_schema

    @tool
    def _factory() -> Tool:  # type: ignore[override]
        async def execute(path: str, instance: str | None = None) -> str | FileStatResult:
            params = StatParams(command="stat", path=path, instance=instance)
            files = files_tool()
            return await files(params=FilesParams(root=params))

        params = ToolParams()
        params.properties["path"] = json_schema(str)
        params.properties["path"].description = "Path to stat"
        params.properties["instance"] = json_schema(str)
        params.properties["instance"].description = "Optional Files instance for isolation"
        params.required.append("path")

        return ToolDef(execute, name="stat_file", description="Stat a path", parameters=params).as_tool()

    return _factory()
