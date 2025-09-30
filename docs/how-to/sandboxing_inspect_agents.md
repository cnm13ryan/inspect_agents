# Sandboxing in `inspect_agents` (Inspect Agents path)

This guide explains how sandboxing is implemented and used by the Inspect‑AI–native path under `src/inspect_agents/`, and how it integrates with Inspect’s core sandbox API. It is more detailed than the brief instructions in `examples/research/README.md` and is intended for maintainers and advanced users.

## Concepts and Components

- Inspect Task sandbox: Each `Task` can specify a sandbox provider via the `sandbox` parameter. Shorthands are supported: a plain string (e.g., `"local"`) or a tuple `(type, config)` maps to an internal `SandboxEnvironmentSpec`. 〖F:external/inspect_ai/src/inspect_ai/_eval/task/task.py†L59-L66〗 〖F:external/inspect_ai/src/inspect_ai/util/_sandbox/environment.py†L404-L423〗
- Resolution and defaults: When evaluating tasks, Inspect resolves the sandbox, optionally auto‑detecting provider‑specific config files from the task’s run directory (e.g., a Docker compose file). 〖F:external/inspect_ai/src/inspect_ai/_eval/loader.py†L178-L216〗
- Runtime access: Tools that need a sandbox call `sandbox()` to obtain the per‑sample sandbox environment; if none exists, a `ProcessLookupError` is raised with a clear message. 〖F:external/inspect_ai/src/inspect_ai/util/_sandbox/context.py†L23-L41〗 〖F:external/inspect_ai/src/inspect_ai/util/_sandbox/context.py†L132-L136〗
- Providers:
  - `local`: Built‑in provider that runs commands in a per‑sample temporary working directory. 〖F:external/inspect_ai/src/inspect_ai/util/_sandbox/local.py†L21-L31〗
  - `docker`: Containerized provider (configurable via provider files such as compose/Dockerfile; see provider implementation for details). 〖F:external/inspect_ai/src/inspect_ai/util/_sandbox/docker/docker.py†L1-L60〗

## How `inspect_agents` Uses Sandboxing

### Exec tools (bash/python)

- The standard execution tools in Inspect (`bash()`, `python()`) invoke the active sandbox with `sandbox_env(...).exec(...)`. These tools are added to `inspect_agents` via `standard_tools()` when `INSPECT_ENABLE_EXEC=1` is set. 〖F:external/inspect_ai/src/inspect_ai/tool/_tools/_execute.py†L22-L57〗 〖F:external/inspect_ai/src/inspect_ai/tool/_tools/_execute.py†L62-L109〗 〖F:src/inspect_agents/tools.py†L357-L363〗
- If a sandbox is not provided for the current sample/task, calling these tools raises `ProcessLookupError("No sandbox environment has been provided …")`. This is the error observed in `eval.json`. 〖F:eval.json†L83-L85〗
- Fix pattern in this repo: set `sandbox="local"` on the Task (or another provider) so exec tools have an environment. Example implemented in `examples/tasks/iterative_task.py`. 〖F:examples/tasks/iterative_task.py†L50-L57〗

### Filesystem tools

- `inspect_agents` provides file tools (`ls`, `read_file`, `write_file`, `edit_file`). They operate in two modes, controlled by `INSPECT_AGENTS_FS_MODE`:
  - `store` (default): in‑memory virtual FS; safe for CI.
  - `sandbox`: routes through Inspect’s host tools (`text_editor`, `bash_session`) after a preflight. 〖F:docs/how-to/filesystem.md†L5-L14〗 〖F:docs/how-to/filesystem.md†L16-L34〗
- Preflight and fallback: When `sandbox` mode is enabled, the tools run a quick preflight against the sandbox service. On failure, they fall back to the in‑memory store by default. Behavior is controlled by env flags: `INSPECT_SANDBOX_PREFLIGHT=auto|skip|force`, `INSPECT_SANDBOX_PREFLIGHT_TTL_SEC`, and `INSPECT_SANDBOX_LOG_PATHS`. 〖F:src/inspect_agents/tools_files.py†L56-L66〗 〖F:docs/how-to/filesystem.md†L44-L63〗
- Deletion: `delete_file` is disabled in sandbox FS mode by design; supported only in `store` mode. 〖F:docs/how-to/filesystem.md†L68-L76〗

### Web/browser tools

- Web search is opt‑in via `INSPECT_ENABLE_WEB_SEARCH=1` plus provider keys; it does not require a sandbox.
- Browser tools (`web_browser`) are heavy and require a sandbox; they are disabled by default in `standard_tools()`. 〖F:src/inspect_agents/tools.py†L365-L369〗

### Approvals (tool gating)

- `inspect_agents` includes approval presets and policies. Presets: `ci` (approve all), `dev` (escalate then reject sensitive tools), `prod` (terminate sensitive tools). Sensitive tools include `bash`, `python`, `write_file`, `text_editor`, and `web_browser_*`. 〖F:src/inspect_agents/approval/presets.py†L19-L110〗
- Activate policies per Task via `approval=...` or programmatically by calling `activate_approval_policies(...)`. 〖F:src/inspect_agents/approval/facade.py†L33-L43〗

## Lifecycle and Data Flow

1) Task creation: you specify a sandbox provider in `Task(...)`. Inspect resolves it into a `SandboxEnvironmentSpec`, optionally detecting provider config files in the task’s source/run directory. 〖F:external/inspect_ai/src/inspect_ai/_eval/task/task.py†L59-L66〗 〖F:external/inspect_ai/src/inspect_ai/_eval/loader.py†L188-L206〗
2) Sample start: Inspect creates per‑sample sandbox environments by calling the selected provider’s `sample_init`, proxies them, sets context vars, and (optionally) copies sample files and runs setup. 〖F:external/inspect_ai/src/inspect_ai/util/_sandbox/context.py†L147-L176〗
3) Tool call: A tool (e.g., `python`) calls `sandbox_env(...).exec(...)`; the provider executes the command within that environment (e.g., temporary directory for `local`). 〖F:external/inspect_ai/src/inspect_ai/tool/_tools/_execute.py†L98-L104〗 〖F:external/inspect_ai/src/inspect_ai/util/_sandbox/local.py†L49-L80〗
4) Cleanup: On sample completion/interruption, providers clean up (e.g., `TemporaryDirectory` removed by `local`). 〖F:external/inspect_ai/src/inspect_ai/util/_sandbox/local.py†L41-L47〗

## Integrating Sandboxing into `inspect_agents`

### Minimal pattern (Tasks)

```python
from inspect_agents import build_iterative_agent
from inspect_agents.approval import approval_preset
from inspect_ai import Task

agent = build_iterative_agent(...)
return Task(
    dataset=..., solver=agent,
    sandbox="local",                     # or ("docker", "compose.yaml")
    approval=approval_preset("dev"),     # optional: stricter gate
)
```

### Docker sandbox (inspect‑tool‑support + Playwright)

Use the Docker sandbox with the official inspect‑tool‑support image to run the stateful web_browser tools (Playwright) in an isolated, ready‑to‑go environment.

What this gives you
- A sandbox service exposing the `inspect-tool-support` CLI on PATH (required by web_browser_*). 【F:external/inspect_ai/src/inspect_ai/tool/_tool_support_helpers.py‑ L114-L126】
- A maintained base image `aisiuk/inspect-tool-support` that bundles Playwright and the browser runtimes. 【F:external/inspect_ai/src/inspect_ai/tool/_tool_support_helpers.py‑ L123-L131】
- Auto‑detection of `compose.yaml` / `docker-compose.yml` or even a `Dockerfile`; if none is found, Inspect can synthesize a minimal compose that uses the same image. 【F:external/inspect_ai/src/inspect_ai/util/_sandbox/docker/config.py‑ L8-L16】【F:external/inspect_ai/src/inspect_ai/util/_sandbox/docker/config.py‑ L48-L59】【F:external/inspect_ai/src/inspect_ai/util/_sandbox/docker/config.py‑ L33-L46】

Quick start (Compose)
1) Create `compose.yaml` at your task’s run directory (project root is common):

```yaml
services:
  default:
    image: "aisiuk/inspect-tool-support"
    init: true
    # Optional: give the container network access for browsing
    # network_mode: bridge
```

2) Enable browser tools and run your task with a Docker sandbox:

```bash
export INSPECT_ENABLE_WEB_BROWSER=1
uv run inspect eval examples/tasks/research_task.py \
  -T prompt="Open https://example.com and summarize the heading" \
  -T config=examples/configs/research/supervisor.yaml \
  --sandbox docker
```

Notes
- You can also set the sandbox in code: `Task(..., sandbox="docker")`. Inspect will auto‑resolve the compose/Dockerfile if present in the task’s run dir. 【F:external/inspect_ai/src/inspect_ai/_eval/task/task.py‑ L62】【F:external/inspect_ai/src/inspect_ai/_eval/loader.py‑ L190-L209】
- If no compose/Dockerfile is present, Inspect may create a temporary `.compose.yaml` that uses `aisiuk/inspect-tool-support`. 【F:external/inspect_ai/src/inspect_ai/util/_sandbox/docker/config.py‑ L60-L86】
- The browser tools family is opt‑in via `INSPECT_ENABLE_WEB_BROWSER=1`; they’re not enabled by default. 【F:src/inspect_agents/tools.py‑ L181-L189】

Alternative: custom Dockerfile
If you maintain your own image, ensure the CLI is installed and on PATH (simplified excerpt):

```Dockerfile
ENV PATH="$PATH:/opt/inspect_tool_support/bin"
RUN python -m venv /opt/inspect_tool_support \
 && /opt/inspect_tool_support/bin/pip install inspect-tool-support \
 && /opt/inspect_tool_support/bin/inspect-tool-support post-install
```

This mirrors the guidance used by Inspect’s tool support helper. 【F:external/inspect_ai/src/inspect_ai/tool/_tool_support_helpers.py‑ L131-L159】

Troubleshooting
- ProcessLookupError: “No sandbox environment has been provided …” — add `sandbox="docker"` on the Task or pass `--sandbox docker` in CLI. 【F:external/inspect_ai/src/inspect_ai/util/_sandbox/context.py‑ L132-L136】
- PrerequisiteError about `inspect-tool-support` — confirm you’re using the `aisiuk/inspect-tool-support` image or that your Dockerfile installed the CLI and added it to PATH. 【F:external/inspect_ai/src/inspect_ai/tool/_tool_support_helpers.py‑ L114-L126】
- No network from the browser — remove `network_mode: none` if present and ensure the container has outbound network access.

### Enabling execution tools

- Add `-T enable_exec=true` to your task run or set `INSPECT_ENABLE_EXEC=1` before constructing the agent. This causes `standard_tools()` to include `bash()`/`python()` (still subject to approvals). 〖F:examples/tasks/iterative_task.py†L36-L38〗 〖F:src/inspect_agents/tools.py†L357-L363〗

### Filesystem mode and preflight

- Default file tools use the in‑memory store. To route through host sandbox editor/shell, set:

```bash
export INSPECT_AGENTS_FS_MODE=sandbox
# Optional preflight controls
export INSPECT_SANDBOX_PREFLIGHT=auto   # or skip|force
export INSPECT_SANDBOX_PREFLIGHT_TTL_SEC=300
export INSPECT_SANDBOX_LOG_PATHS=1
```

See the FS guide for behavior, limits, and delete policy. 〖F:docs/how-to/filesystem.md†L44-L76〗

## Provider Notes

- Local sandbox:
  - Executes under a per‑sample temp dir; `user` parameter is ignored (runs as current user). 〖F:external/inspect_ai/src/inspect_ai/util/_sandbox/local.py†L61-L66〗 〖F:external/inspect_ai/src/inspect_ai/util/_sandbox/local.py†L67-L79〗
  - Enforces output size limits via Inspect’s `SandboxEnvironmentLimits`. 〖F:external/inspect_ai/src/inspect_ai/util/_sandbox/local.py†L71-L79〗
- Docker sandbox:
  - Supports deriving sandbox config from known files and setting up container execution. See the provider for details and Compose integration. 〖F:external/inspect_ai/src/inspect_ai/util/_sandbox/docker/docker.py†L1-L60〗

## Security & Approvals Guidance

- Default to approvals when enabling exec or browser tools; prefer `dev` in shared environments and `prod` for stricter enforcement. 〖F:src/inspect_agents/approval/presets.py†L74-L110〗
- Keep filesystem tools in `store` mode for CI to avoid host writes; switch to `sandbox` mode only when you need host interactions and preflight is green. 〖F:docs/how-to/filesystem.md†L44-L63〗
- Consider setting `INSPECT_AGENTS_FS_READ_ONLY=1` for demonstrations or regulated workflows (ls/read allowed; write/edit/delete raise). See environment docs in this repo.

## Troubleshooting

- `ProcessLookupError: No sandbox environment has been provided ...`
  - Set `sandbox="local"` (or a valid provider) on the Task; confirm no CLI override replaced it. 〖F:eval.json†L83-L85〗 〖F:examples/tasks/iterative_task.py†L50-L57〗
- macOS user‑data permissions (e.g., writes under `~/Library/Application Support/inspect_ai/`):
  - Redirect logs/traces with `INSPECT_LOG_DIR=./logs` and `INSPECT_TRACE_FILE=./logs/trace.log`, or run outside a restricted OS sandbox. Inspect’s sample buffers use the OS user data directory by default.
- Missing packages in `python` tool runs:
  - Install required modules in your venv (`pip install ...`) or approve a `bash("pip install ...")` call.

## References (code pointers)

- Task sandbox API and spec resolution: 〖F:external/inspect_ai/src/inspect_ai/_eval/task/task.py†L59-L66〗 〖F:external/inspect_ai/src/inspect_ai/util/_sandbox/environment.py†L404-L423〗 〖F:external/inspect_ai/src/inspect_ai/_eval/loader.py†L178-L216〗
- Sandbox context and errors: 〖F:external/inspect_ai/src/inspect_ai/util/_sandbox/context.py†L23-L41〗 〖F:external/inspect_ai/src/inspect_ai/util/_sandbox/context.py†L132-L136〗
- Providers: local and docker: 〖F:external/inspect_ai/src/inspect_ai/util/_sandbox/local.py†L21-L31〗 〖F:external/inspect_ai/src/inspect_ai/util/_sandbox/docker/docker.py†L1-L60〗
- Exec tools using sandbox: 〖F:external/inspect_ai/src/inspect_ai/tool/_tools/_execute.py†L22-L57〗 〖F:external/inspect_ai/src/inspect_ai/tool/_tools/_execute.py†L62-L109〗
- `inspect_agents` integration: approvals and tool toggles: 〖F:src/inspect_agents/approval/presets.py†L19-L110〗 〖F:src/inspect_agents/tools.py†L357-L369〗 〖F:docs/how-to/filesystem.md†L44-L76〗

---
If you need a deeper provider (Docker) example, I can add a minimal Compose file and a matching Task configuration.
