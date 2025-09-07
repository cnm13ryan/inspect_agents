#!/usr/bin/env python3
"""
Inspect Agents — Environment Configurator

Interactive helper that generates .env files aligned with env_templates/inspect.env
and the environment reference in docs/reference/environment.md. It covers:
  - Providers & models (LM‑Studio, Ollama, remote providers via keys)
  - Web search providers (Tavily, Google CSE)
  - Tool toggles
  - Approvals & parallelism policies
  - Filesystem & sandbox settings (advanced preflight/limits)
  - Iterative agent budgets (time/steps/pruning)
  - Logging, tracing, and tool‑output truncation
  - Quarantine & per‑agent limits

Writes .env at the repo root and examples/inspect/.env (legacy) unless disabled.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

# --------------------------
# Utilities
# --------------------------


def get_repo_root() -> Path:
    """Find the repository root directory."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / ".git").exists() or (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent


def create_env_file(path: Path | str, content: str) -> None:
    """Create or update an .env file with the given content."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"✓ Wrote {p}")


def _truthy(s: str) -> bool:
    return s.strip().lower() in {"1", "true", "yes", "y", "on"}


def ask(prompt: str, *, default: str | None = None, allow_empty: bool = True) -> str:
    suffix = f" [default: {default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    if not val and default is not None:
        return default
    if not val and not allow_empty:
        return default or ""
    return val


def ask_bool(prompt: str, *, default: bool = False) -> bool:
    suffix = " [Y/n]" if default else " [y/N]"
    ans = input(f"{prompt}{suffix}: ").strip()
    return _truthy(ans) if ans else default


def choose(prompt: str, options: list[str], *, default_idx: int = 0) -> str:
    for i, opt in enumerate(options, start=1):
        mark = "*" if (i - 1) == default_idx else " "
        print(f"  {i}. {opt} {mark}")
    while True:
        sel = input(f"{prompt} (1-{len(options)}): ").strip()
        if not sel:
            return options[default_idx]
        if sel.isdigit():
            idx = int(sel) - 1
            if 0 <= idx < len(options):
                return options[idx]
        print("Please enter a valid number.")


# --------------------------
# Builders (return lines)
# --------------------------


def build_header() -> list[str]:
    return [
        "###############################################",
        "# Inspect Agents — Centralized Environment",
        "#",
        "# Copy this file or point to it with:",
        '#   uv run python examples/inspect/run.py --env-file env_templates/inspect.env "..."',
        "# or export:",
        "#   export INSPECT_ENV_FILE=env_templates/inspect.env",
        "#",
        "# Values here act as defaults. They will NOT override values set in:",
        "# - real environment variables",
        "# - repo root .env",
        "# - examples/inspect/.env (legacy)",
        "###############################################",
        "",
    ]


def build_providers_section() -> list[str]:
    lines: list[str] = []
    print("\nProviders & Models")
    print("Configure your local model provider.")
    provider = choose("Choose provider", ["lm-studio", "ollama"], default_idx=0)

    lines += [
        "# Provider selection",
        "# One of: ollama | lm-studio | openai | ...",
        f"DEEPAGENTS_MODEL_PROVIDER={provider}",
        "",
    ]

    if provider == "lm-studio":
        base_url = ask("LM‑Studio base URL", default="http://127.0.0.1:1234/v1")
        # Optionally query models (best‑effort, no hard dep)
        default_model = "local-model"
        model = ask("LM‑Studio model name", default=default_model)
        lines += [
            "# LM Studio (OpenAI-compatible local server)",
            f"LM_STUDIO_BASE_URL={base_url}",
            f"LM_STUDIO_MODEL_NAME={model}",
            "LM_STUDIO_API_KEY=lm-studio",
            "",
        ]
    else:  # ollama
        # List models if ollama exists (non-fatal)
        try:  # pragma: no cover - best-effort UX only
            import subprocess

            res = subprocess.run(["ollama", "list"], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                print("\nAvailable Ollama models:")
                for line in res.stdout.strip().splitlines()[1:]:
                    if line.strip():
                        print("  -", line.split()[0])
        except Exception:
            pass

        model = ask("Ollama model name", default="llama3.1:8b")
        base_url = ask("Ollama base URL (optional)", default="http://localhost:11434")
        lines += [
            "# Ollama (local)",
            f"OLLAMA_MODEL_NAME={model}",
            f"OLLAMA_BASE_URL={base_url}",
            "",
        ]

    # Role mapping examples (commented)
    lines += [
        "# Role mapping (optional; examples — uncomment and customize)",
        "# INSPECT_ROLE_GRADER_PROVIDER=openai",
        "# INSPECT_ROLE_GRADER_MODEL=gpt-4o-mini",
        "# INSPECT_ROLE_RESEARCHER_PROVIDER=ollama",
        "# INSPECT_ROLE_RESEARCHER_MODEL=llama3.1:8b",
        "",
    ]

    # Remote provider keys (commented)
    lines += [
        "# Remote providers (set when using non-local providers)",
        "# OPENAI_API_KEY=",
        "# OPENAI_MODEL=",
        "# ANTHROPIC_API_KEY=",
        "# ANTHROPIC_MODEL=",
        "# GOOGLE_API_KEY=",
        "# GOOGLE_MODEL=",
        "# GROQ_API_KEY=",
        "# GROQ_MODEL=",
        "# MISTRAL_API_KEY=",
        "# MISTRAL_MODEL=",
        "# PERPLEXITY_API_KEY=",
        "# PERPLEXITY_MODEL=",
        "# FIREWORKS_API_KEY=",
        "# FIREWORKS_MODEL=",
        "# GROK_API_KEY=",
        "# GROK_MODEL=",
        "# GOODFIRE_API_KEY=",
        "# GOODFIRE_MODEL=",
        "# OPENROUTER_API_KEY=",
        "# OPENROUTER_MODEL=",
        "",
    ]

    return lines


def build_web_search_section() -> list[str]:
    lines: list[str] = [
        "# Web Search (pick one external provider)",
        "# Tavily (recommended for simplicity)",
    ]
    enable_search = ask_bool("Enable web search tools?", default=False)
    if not enable_search:
        lines += [
            "# TAVILY_API_KEY=your_tavily_api_key",
            "",
            "# Google Custom Search Engine",
            "# GOOGLE_CSE_API_KEY=your_google_cse_api_key",
            "# GOOGLE_CSE_ID=your_google_cse_id",
            "",
        ]
        return lines

    choice = choose("Choose search provider", ["tavily", "google-cse"], default_idx=0)
    if choice == "tavily":
        tavily = ask("Enter Tavily API key", allow_empty=False)
        lines += [f"TAVILY_API_KEY={tavily}", ""]
        # Comment Google for reference
        lines += [
            "# Google Custom Search Engine",
            "# GOOGLE_CSE_API_KEY=your_google_cse_api_key",
            "# GOOGLE_CSE_ID=your_google_cse_id",
            "",
        ]
    else:
        gkey = ask("Enter Google CSE API key", allow_empty=False)
        gid = ask("Enter Google CSE ID", allow_empty=False)
        lines += [
            "# Google Custom Search Engine",
            f"GOOGLE_CSE_API_KEY={gkey}",
            f"GOOGLE_CSE_ID={gid}",
            "",
        ]
        # Comment Tavily for reference
        lines += ["# TAVILY_API_KEY=your_tavily_api_key", ""]
    return lines


def build_fs_section() -> list[str]:
    print("\nFilesystem & Sandbox")
    lines: list[str] = []
    mode = choose("FS mode", ["store (in‑memory)", "sandbox (host‑routed)"])
    fs_mode = "store" if mode.startswith("store") else "sandbox"
    lines += [
        "# Inspect Agents behavior",
        "# Use 'store' (default) for in-memory virtual FS, or 'sandbox' to route",
        "# file operations to Inspect's host text editor tool (requires sandbox setup).",
        f"INSPECT_AGENTS_FS_MODE={fs_mode}",
        "",
    ]

    if fs_mode == "sandbox":
        ro = ask_bool(
            "Sandbox read-only? (blocks write/edit/delete; allows ls/read)",
            default=False,
        )
        if ro:
            lines += [
                "# Sandbox read-only mode: when FS_MODE=sandbox and this flag is truthy (1/true),",
                '# write/edit/delete are blocked (tools raise ToolException "SandboxReadOnly" and',
                "# log a tool_event error). Listing/reading remain allowed. No effect in store mode.",
                "INSPECT_AGENTS_FS_READ_ONLY=1",
                "",
            ]
        else:
            lines += [
                "# INSPECT_AGENTS_FS_READ_ONLY=1",
                "",
            ]

    # Log directory (default to standardized path)
    log_dir = ask("Transcript output dir", default=".inspect/logs/")
    lines += [
        "# Transcript output directory",
        f"INSPECT_LOG_DIR={log_dir}",
        "",
    ]

    return lines


def build_tools_section() -> list[str]:
    print("\nTool Toggles")
    lines: list[str] = ["# Standard tool toggles (opt-in for heavy tools)"]
    if ask_bool("Enable THINK helper?", default=True):
        lines.append("INSPECT_ENABLE_THINK=1")
    else:
        lines.append("# INSPECT_ENABLE_THINK=1")

    if ask_bool("Enable web_search tools?", default=False):
        lines.append("INSPECT_ENABLE_WEB_SEARCH=1")
    else:
        lines.append("# INSPECT_ENABLE_WEB_SEARCH=1")

    if ask_bool("Enable EXEC tools (bash/python)?", default=False):
        lines.append("INSPECT_ENABLE_EXEC=1")
    else:
        lines.append("# INSPECT_ENABLE_EXEC=0")

    if ask_bool("Enable WEB_BROWSER tools?", default=False):
        lines.append("INSPECT_ENABLE_WEB_BROWSER=1")
    else:
        lines.append("# INSPECT_ENABLE_WEB_BROWSER=0")

    if ask_bool("Expose TEXT_EDITOR tool explicitly?", default=False):
        lines.append("INSPECT_ENABLE_TEXT_EDITOR_TOOL=1")
    else:
        lines.append("# INSPECT_ENABLE_TEXT_EDITOR_TOOL=0")

    lines.append("")
    return lines


def build_quarantine_section() -> list[str]:
    print("\nQuarantine & Handoff Filters")
    lines: list[str] = [
        "# Quarantine / Handoff Filters (repo-wide defaults with per-agent overrides)",
        "#",
        "# Controls how conversation history is filtered when handing off to sub‑agents.",
        "#",
        "# Mode:",
        "#   - strict (default): remove tools/system, keep only the last boundary message.",
        "#   - scoped: strict + append a small JSON summary of current Todos/Files.",
        "#   - off: identity (no filtering) — only use for debugging.",
    ]

    mode = choose("Default quarantine mode", ["strict", "scoped", "off"], default_idx=0)
    lines += [f"# INSPECT_QUARANTINE_MODE={mode}"]

    inherit = ask_bool("Cascade parent filter to nested handoffs?", default=True)
    lines += ["#", "# Inheritance (cascade parent filter to nested handoffs):"]
    lines += [
        "#   1 (default) = inherit; 0 = do not inherit. When inheritance is enabled and a",
        "#   parent active filter exists, the global default will NOT override it.",
        f"# INSPECT_QUARANTINE_INHERIT={'1' if inherit else '0'}",
        "#",
        "# Per-agent override (wins over inheritance/global). The <agent> suffix is",
        "# normalized to lower-case; non-alphanumeric → underscore; multiple underscores",
        "# collapsed; trimmed at ends. Examples:",
        "#   INSPECT_QUARANTINE_MODE__researcher=scoped",
        '#   INSPECT_QUARANTINE_MODE__research_assistant_v2=strict  # from "Research Assistant v2"',
        "#",
        "# Scoped summary size guards (only when mode=scoped):",
        "# INSPECT_SCOPED_MAX_BYTES=2048",
        "# INSPECT_SCOPED_MAX_TODOS=10",
        "# INSPECT_SCOPED_MAX_FILES=20",
        "",
    ]
    return lines


def build_approvals_section() -> list[str]:
    print("\nApprovals & Parallelism")
    lines: list[str] = ["## Approvals & Presets"]
    choice = choose("Approval preset (optional)", ["none", "dev", "prod", "ci"], default_idx=0)
    if choice != "none":
        lines += [f"INSPECT_APPROVAL_PRESET={choice}"]
    else:
        lines += ["# INSPECT_APPROVAL_PRESET=dev"]

    # Parallel kill-switch
    if ask_bool("Enable parallel kill-switch for non-handoff tools?", default=False):
        lines += ["INSPECT_DISABLE_TOOL_PARALLEL=1"]
    else:
        lines += ["# INSPECT_DISABLE_TOOL_PARALLEL=1", "# INSPECT_TOOL_PARALLELISM_DISABLE=1  # legacy alias"]
    lines.append("")
    return lines


def build_fs_advanced_section() -> list[str]:
    print("\nFilesystem — Advanced")
    lines: list[str] = ["## Filesystem & Sandbox (advanced)"]
    mode = choose("Sandbox preflight mode", ["auto", "skip", "force"], default_idx=0)
    ttl = ask("Preflight TTL seconds", default="300")
    root = ask("Sandbox FS root (absolute)", default="/repo")
    max_bytes = ask("Max file bytes (OOM guard)", default="5000000")
    timeout = ask("Default tool timeout (sec)", default="15")
    typed = ask_bool("Return typed tool results?", default=False)
    lines += [
        f"# INSPECT_SANDBOX_PREFLIGHT={mode}",
        f"# INSPECT_SANDBOX_PREFLIGHT_TTL_SEC={ttl}",
        "# INSPECT_SANDBOX_LOG_PATHS=0",
        f"# INSPECT_AGENTS_FS_ROOT={root}",
        f"# INSPECT_AGENTS_FS_MAX_BYTES={max_bytes}",
        f"# INSPECT_AGENTS_TOOL_TIMEOUT={timeout}",
        ("INSPECT_AGENTS_TYPED_RESULTS=1" if typed else "# INSPECT_AGENTS_TYPED_RESULTS=1"),
        "",
    ]
    return lines


def build_iterative_section() -> list[str]:
    print("\nIterative Agent Budgets")
    lines: list[str] = ["## Iterative Agent (time/steps/pruning)"]
    if not ask_bool("Configure iterative budgets now?", default=False):
        lines += [
            "# INSPECT_ITERATIVE_TIME_LIMIT=60",
            "# INSPECT_ITERATIVE_MAX_STEPS=10",
            "# INSPECT_PRUNE_AFTER_MESSAGES=120",
            "# INSPECT_PRUNE_KEEP_LAST=40",
            "# INSPECT_PER_MSG_TOKEN_CAP=0",
            "# INSPECT_TRUNCATE_LAST_K=200",
            "# INSPECT_PRODUCTIVE_TIME=1",
            "",
        ]
        return lines

    tlim = ask("Time limit seconds (empty to skip)", default="")
    steps = ask("Max steps (empty to skip)", default="")
    prune_after = ask("Prune after messages (<=0 disables)", default="120")
    keep_last = ask("Prune keep last", default="40")
    cap = ask("Per-message token cap (0 disables)", default="0")
    last_k = ask("Truncate last K messages", default="200")
    prod = ask_bool("Enable productive-time accounting?", default=True)

    if tlim:
        lines += [f"INSPECT_ITERATIVE_TIME_LIMIT={tlim}"]
    else:
        lines += ["# INSPECT_ITERATIVE_TIME_LIMIT=60"]
    if steps:
        lines += [f"INSPECT_ITERATIVE_MAX_STEPS={steps}"]
    else:
        lines += ["# INSPECT_ITERATIVE_MAX_STEPS=10"]
    lines += [
        f"INSPECT_PRUNE_AFTER_MESSAGES={prune_after}",
        f"INSPECT_PRUNE_KEEP_LAST={keep_last}",
        f"INSPECT_PER_MSG_TOKEN_CAP={cap}",
        f"INSPECT_TRUNCATE_LAST_K={last_k}",
        ("INSPECT_PRODUCTIVE_TIME=1" if prod else "# INSPECT_PRODUCTIVE_TIME=1"),
        "",
    ]
    return lines


def build_observability_section() -> list[str]:
    print("\nLogging, Tracing & Truncation")
    lines: list[str] = ["## Logging & Observability"]
    trace = ask("Trace file path (empty to skip)", default="")
    trunc = ask("Tool log string truncate (chars)", default="200")
    cap = ask("Global tool-output cap bytes (0=disable; empty=skip)", default="")
    if trunc:
        lines += [f"# INSPECT_TOOL_OBS_TRUNCATE={trunc}"]
    else:
        lines += ["# INSPECT_TOOL_OBS_TRUNCATE=200"]
    if trace:
        lines += [f"# INSPECT_TRACE_FILE={trace}"]
    else:
        lines += ["# INSPECT_TRACE_FILE=logs/inspect_ai/trace.log"]
    if cap:
        lines += [f"# INSPECT_MAX_TOOL_OUTPUT={cap}"]
    else:
        lines += ["# INSPECT_MAX_TOOL_OUTPUT=16384"]

    # Runner near-limit telemetry
    near = ask("Runner near-limit threshold (0<val<1)", default="0.8")
    lines += [f"# INSPECT_LIMIT_NEARING_THRESHOLD={near}"]

    # Debug toggles
    model_dbg = ask_bool("Enable model resolver debug logs?", default=False)
    lines += ["INSPECT_MODEL_DEBUG=1" if model_dbg else "# INSPECT_MODEL_DEBUG=1"]
    prune_dbg = ask_bool("Enable prune/truncation debug logs?", default=False)
    lines += ["INSPECT_PRUNE_DEBUG=1" if prune_dbg else "# INSPECT_PRUNE_DEBUG=1"]

    # Suppress legacy wrapper warnings (CI noise reduction)
    suppress = ask_bool("Suppress legacy file wrapper DeprecationWarnings?", default=False)
    lines += [
        ("INSPECT_AGENTS_SUPPRESS_TOOL_WRAPPER_WARN=1" if suppress else "# INSPECT_AGENTS_SUPPRESS_TOOL_WRAPPER_WARN=1")
    ]

    lines.append("")
    return lines


def build_executor_prescan_section() -> list[str]:
    print("\nExecutor Pre‑Scan (optional)")
    lines: list[str] = ["## Handoff Pre‑Scan (optional)"]
    prescan = ask_bool("Enable executor pre-scan (first handoff wins)?", default=False)
    lines += ["INSPECT_EXECUTOR_PRESCAN_HANDOFF=1" if prescan else "# INSPECT_EXECUTOR_PRESCAN_HANDOFF=1"]
    mirror = ask_bool(
        "Also mirror policy event for skipped calls?",
        default=False,
    )
    lines += [
        ("INSPECT_EXECUTOR_PRESCAN_MIRROR_POLICY=1" if mirror else "# INSPECT_EXECUTOR_PRESCAN_MIRROR_POLICY=1"),
        "",
    ]
    return lines


def assemble_lines(sections: Iterable[list[str]]) -> str:
    lines: list[str] = []
    for sec in sections:
        lines.extend(sec)
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    print("🧠🤖 Inspect Agents Environment Configurator")
    print("===========================================")
    print(
        "This will generate .env files mirroring env_templates/inspect.env with\n"
        "inline explanations from docs/reference/environment.md.\n"
    )

    # Sections
    header = build_header()
    providers = build_providers_section()
    web_search = build_web_search_section()
    tools = build_tools_section()
    approvals = build_approvals_section()
    executor_prescan = build_executor_prescan_section()
    fs = build_fs_section()
    fs_adv = build_fs_advanced_section()
    iterative = build_iterative_section()
    observability = build_observability_section()
    quarantine = build_quarantine_section()

    content = assemble_lines(
        [
            header,
            providers,
            web_search,
            tools,
            approvals,
            executor_prescan,
            fs,
            fs_adv,
            iterative,
            observability,
            quarantine,
        ]
    )

    repo_root = get_repo_root()
    root_env = repo_root / ".env"
    examples_env = repo_root / "examples" / "inspect" / ".env"

    print("\n📁 Writing configuration files...")
    create_env_file(root_env, content)
    create_env_file(examples_env, content)

    print("\n✅ Configuration complete!")
    print("Next steps:")
    print("- Install deps: uv sync")
    print("- Run Inspect example:")
    print('  uv run python examples/inspect/run.py "Write a short overview of Inspect‑AI"')
    print("  # Or point to this env file with --env-file or INSPECT_ENV_FILE")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
