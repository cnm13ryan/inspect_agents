"""Centralized tool presets and descriptors for inspect_agents.

This module provides a single source of truth for tool resolution logic,
prompt descriptions, and preset composition to eliminate duplication
across supervisor and iterative agents.
"""

from __future__ import annotations

import logging
import os

from .settings import truthy


def _use_sandbox_fs() -> bool:
    """Check if sandbox filesystem mode is enabled."""
    return os.getenv("INSPECT_AGENTS_FS_MODE", "").strip().lower() == "sandbox"


def resolve_standard_tools() -> list[object]:
    """Resolve standard Inspect‑AI tools based on environment configuration.

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
    if not os.getenv("INSPECT_ENABLE_THINK") or truthy(os.getenv("INSPECT_ENABLE_THINK", "1")):
        try:
            tools.append(think())
        except Exception:
            pass

    # web_search(...)
    enable_web_search_env = os.getenv("INSPECT_ENABLE_WEB_SEARCH")
    enable_web_search = (
        truthy(enable_web_search_env)
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
    if truthy(os.getenv("INSPECT_ENABLE_EXEC")):
        try:
            tools.extend([bash(), py_exec()])
        except Exception:
            pass

    # web_browser (disabled by default; heavy)
    if truthy(os.getenv("INSPECT_ENABLE_WEB_BROWSER")):
        try:
            tools.extend(web_browser())
        except Exception:
            pass

    # text_editor (disabled by default; only meaningful with sandbox FS)
    if truthy(os.getenv("INSPECT_ENABLE_TEXT_EDITOR_TOOL")) and _use_sandbox_fs():
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


def describe_standard_tools(all_tools: list[object]) -> str:
    """Return a prompt section describing available Inspect standard tools.

    Groups standard tools separately so the model understands additional
    capabilities beyond the Todo/FS utilities.
    """
    try:
        from inspect_ai.tool._tool_def import ToolDef
    except Exception:
        # If ToolDef is unavailable (e.g., in stubs), skip annotation
        return ""

    names = set()
    for t in all_tools:
        try:
            tdef = ToolDef(t) if not isinstance(t, ToolDef) else t
            names.add(tdef.name)
        except Exception:
            pass

    std_names: list[str] = []
    # Detect presence of representative tools
    if "think" in names:
        std_names.append("think")
    if "web_search" in names:
        std_names.append("web_search")
    if "bash" in names:
        std_names.append("bash")
    if "python" in names:
        std_names.append("python")
    # Web browser exposes multiple tool names; detect by go
    browser_present = any(n.startswith("web_browser_") for n in names)
    if browser_present:
        std_names.append("web_browser")
    if "text_editor" in names:
        std_names.append("text_editor")

    if not std_names:
        return ""

    std_list = ", ".join(std_names)
    return (
        "\n## Standard Tools\n\n"
        f"Additional standard tools are enabled: {std_list}.\n"
        "Use `web_search` to retrieve up‑to‑date information from the web when needed."
        " Prefer citing sources in your answer.\n"
    )


def resolve_builtin_tools(*, include_defaults: bool, code_only: bool = False) -> list[object]:
    """Resolve the complete builtin toolset based on configuration.

    Args:
        include_defaults: Whether to include default tools (todos, fs tools)
        code_only: If True, exclude standard tools regardless of env flags

    Returns:
        List of resolved tools combining defaults and standard tools as appropriate
    """
    tools: list[object] = []

    # Add default tools if requested
    if include_defaults:
        from .tools import minimal_fs_preset

        tools.extend(minimal_fs_preset())

    # Add standard tools unless code_only mode
    if not code_only:
        tools.extend(resolve_standard_tools())

    return tools


def resolve_supervisor_tools(*, include_defaults: bool) -> list[object]:
    """Resolve tools for the supervisor agent."""
    if include_defaults:
        from .tools import full_safe_preset

        return full_safe_preset()
    return []


def resolve_iterative_tools(*, include_defaults: bool, code_only: bool = False) -> list[object]:
    """Resolve tools for the iterative agent.

    - Always include Files tools (write/read/ls/edit) when include_defaults is True.
    - When `code_only=True`, exclude all "standard" tools (think, exec, search,
      browser, etc.) regardless of environment flags.
    - When `code_only=False` (default), append tools from `resolve_standard_tools()`
      based on env toggles.
    """
    tools: list[object] = []

    if include_defaults:
        from .tools import edit_file, ls, read_file, write_file

        tools.extend([write_file(), read_file(), ls(), edit_file()])

    if not code_only:
        tools.extend(resolve_standard_tools())

    return tools
