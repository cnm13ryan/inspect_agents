# Examples Index

This repo’s examples are grouped by intent so you can quickly find the right entrypoint and avoid path confusion.

Canonical guide for the research example: `docs/getting-started/research_example.md`.

## Layout

- tasks/: Inspect CLI tasks (run with `inspect eval`)
  - `examples/tasks/prompt_task.py` — single-sample ad‑hoc prompt task.
  - `examples/tasks/iterative_task.py` — iterative agent (no submit) task.
  - `examples/tasks/research_task.py` — research composition as an Inspect task (optionally via YAML config).

- runners/: Python scripts that run agents directly (no Inspect CLI required)
  - `examples/runners/supervisor_runner.py` — minimal supervisor runner.
  - `examples/runners/research_runner.py` — research composition runner.
  - `examples/runners/iterative_runner.py` — iterative agent runner (no submit).
  - `examples/runners/profiled_runner.py` — Tx.Hx.Nx profile selector for iterative runs.

- demos/: Small, self‑contained demonstration scripts
  - `examples/demos/simple_arch_demo.py` — simple architecture demo (supervisor/iterative modes).
  - `examples/demos/subagent_approvals_demo.py` — handoff exclusivity + approvals demo (offline).

- configs/: Example configurations
  - `examples/configs/research/supervisor.yaml` — YAML composition for the research supervisor.

## Quick Start

- Inspect CLI (tasks)
  - `uv run inspect eval examples/tasks/prompt_task.py -T prompt="Write a concise overview of LangGraph"`
  - `uv run inspect eval examples/tasks/iterative_task.py -T prompt="List repo files and propose a small refactor plan"`
  - YAML config: `uv run inspect eval examples/tasks/research_task.py -T config=examples/configs/research/supervisor.yaml -T prompt="Research topic..."`

- Python runners
  - `uv run python examples/runners/supervisor_runner.py "What is Inspect‑AI?"`
  - `uv run python examples/runners/research_runner.py --enable-web-search "Research LangGraph vs Inspect"`
  - `uv run python examples/runners/iterative_runner.py --time-limit 120 --max-steps 20 "List repo files and summarize"`
  - `uv run python examples/runners/profiled_runner.py --profile T1.H1.N1 "Curate arXiv papers by Quantinuum (2025)"`

- Demos
  - `uv run python examples/demos/simple_arch_demo.py --mode supervisor "Research topic..."`
  - `uv run python examples/demos/subagent_approvals_demo.py --preset dev`

## CLI Reference

This section documents the example commands with argument tables. Defaults are the values used when you omit the flag. See docs/reference/environment.md for provider/model env and tool toggles.

### Inspect CLI Tasks (run with `inspect eval`)

Usage examples

```bash
# Ad‑hoc prompt task
uv run inspect eval examples/tasks/prompt_task.py -T prompt="Write a concise overview of LangGraph" -T attempts=1

# Iterative agent as a task
uv run inspect eval examples/tasks/iterative_task.py \
  -T prompt="List files and propose a small refactor plan" \
  -T time_limit=300 -T max_steps=30 -T enable_exec=true -T enable_web_search=true

# Research composition (inline or YAML config)
uv run inspect eval examples/tasks/research_task.py \
  -T prompt="Curate arXiv papers Quantinuum published in 2025" \
  -T attempts=1 -T enable_web_search=true
uv run inspect eval examples/tasks/research_task.py \
  -T config=examples/configs/research/supervisor.yaml -T prompt="Research topic..."
```

prompt_task.py (examples/tasks/prompt_task.py)

| Argument | Type | Default | Description | Related env |
|---|---|---:|---|---|
| `prompt` | str | "Find the latest publication from Quantinuum in arxiv" | Single input sample text. | Model/provider/env per docs/reference/environment.md |
| `attempts` | int | 1 | Number of agent attempts (submit semantics). | — |

iterative_task.py (examples/tasks/iterative_task.py)

| Argument | Type | Default | Description | Related env |
|---|---|---:|---|---|
| `prompt` | str | "List repository files and summarize key modules." | Task prompt text. | — |
| `time_limit` | int (sec) | 600 | Real‑time budget for the loop. | — |
| `max_steps` | int | 40 | Maximum reasoning/tool steps. | — |
| `enable_exec` | bool | false | Enables `bash()` and `python()` tools. | Sets `INSPECT_ENABLE_EXEC=1` |
| `enable_web_search` | bool | false | Enables `web_search()` tool. | Sets `INSPECT_ENABLE_WEB_SEARCH=1` + provider keys |

research_task.py (examples/tasks/research_task.py)

| Argument | Type | Default | Description | Related env |
|---|---|---:|---|---|
| `prompt` | str | "Write a short overview of Inspect‑AI" | Task prompt text. | — |
| `attempts` | int | 1 | Agent attempts (submit semantics). | — |
| `config` | str/path | — | Optional YAML composition (overrides inline defaults). | — |
| `enable_web_search` | bool | false | Enables `web_search()` in the composition. | Sets `INSPECT_ENABLE_WEB_SEARCH=1` + provider keys |

Tip: Standard tools (think, web_search, etc.) are available via env toggles; see docs/reference/environment.md and docs/tools/*.

### Python Runners (run with `python`)

Supervisor runner (examples/runners/supervisor_runner.py)

```bash
uv run python examples/runners/supervisor_runner.py "Write a short overview of LangGraph"
```

| Argument | Type | Default | Description | Related env |
|---|---|---:|---|---|
| `prompt` | str (positional, optional) | `$PROMPT` or example text | User prompt; falls back to `$PROMPT` then an in‑file default. | `PROMPT` |
| `--provider` | str | `DEEPAGENTS_MODEL_PROVIDER` or `lm-studio` | Model provider routing. | `DEEPAGENTS_MODEL_PROVIDER` |
| `--model` | str | `INSPECT_EVAL_MODEL` or unset | Explicit model id; may include provider prefix. | `INSPECT_EVAL_MODEL` |
| `--enable-think` | flag | false | Enable `think()` tool. | `INSPECT_ENABLE_THINK=1` |
| `--enable-web-search` | flag | false | Enable `web_search()` tool. | `INSPECT_ENABLE_WEB_SEARCH=1` + search keys |
| `--enable-exec` | flag | false | Enable `bash()` and `python()` tools. | `INSPECT_ENABLE_EXEC=1` |
| `--enable-web-browser` | flag | false | Enable browser tools. | `INSPECT_ENABLE_WEB_BROWSER=1` |
| `--enable-text-editor-tool` | flag | false | Expose editor tool directly. | `INSPECT_ENABLE_TEXT_EDITOR_TOOL=1` |

Iterative runner (examples/runners/iterative_runner.py)

```bash
uv run python examples/runners/iterative_runner.py --time-limit 300 --max-steps 20 "List repo files and summarize"
```

| Argument | Type | Default | Description | Related env |
|---|---|---:|---|---|
| `prompt` | str (positional, optional) | `$PROMPT` or example text | User prompt; falls back to `$PROMPT`. | `PROMPT` |
| `--time-limit` | int (sec) | 600 | Real‑time budget for the loop. | — |
| `--max-steps` | int | 40 | Maximum reasoning/tool steps. | — |
| `--enable-exec` | flag | false | Enable `bash()` and `python()` tools. | `INSPECT_ENABLE_EXEC=1` |
| `--provider` | str | `DEEPAGENTS_MODEL_PROVIDER` or `ollama` | Model provider routing. | `DEEPAGENTS_MODEL_PROVIDER` |
| `--model` | str | `INSPECT_EVAL_MODEL` or unset | Explicit model id; may include provider prefix. | `INSPECT_EVAL_MODEL` |

Research runner (examples/runners/research_runner.py)

```bash
uv run python examples/runners/research_runner.py --enable-web-search "What is Inspect‑AI?"
```

| Argument | Type | Default | Description | Related env |
|---|---|---:|---|---|
| `prompt` | str (positional, optional) | `$PROMPT` or example text | User prompt; falls back to `$PROMPT`. | `PROMPT` |
| `--provider` | str | `DEEPAGENTS_MODEL_PROVIDER` or `ollama` | Model provider routing. | `DEEPAGENTS_MODEL_PROVIDER` |
| `--model` | str | `INSPECT_EVAL_MODEL` or unset | Explicit model id; may include provider prefix. | `INSPECT_EVAL_MODEL` |
| `--enable-web-search` | flag | false | Enable `web_search()` tool. | `INSPECT_ENABLE_WEB_SEARCH=1` + search keys |
| `--approval` | enum | — | Apply approvals preset (`dev`|`ci`|`prod`). | — |
| `--config` | str/path | — | Load composition from YAML. | — |

Profiled runner (examples/runners/profiled_runner.py)

```bash
uv run python examples/runners/profiled_runner.py --profile T1.H1.N1 "Curate arXiv papers by Quantinuum (2025)"
```

| Argument | Type | Default | Description | Related env |
|---|---|---:|---|---|
| `prompt` | str (positional, optional) | `$PROMPT` or example text | User prompt; falls back to `$PROMPT`. | `PROMPT` |
| `--profile` | Tx.Hx.Nx | `T1.H1.N1` | Profile selector: T=Tooling (T0 unrestricted exec, T1 restricted web, T2 no exec); H=Host (H0 local, H1 docker, H2 k8s, H3 proxmox); N=Network (N0 full, N1 allow‑listed, N2 no external). | Sets tool/env toggles; maps H→Task.sandbox |
| `--tooling` | T0|T1|T2 | — | Override T component only. | Sets `INSPECT_ENABLE_*` accordingly |
| `--host` | H0|H1|H2|H3 | — | Override H component only. | Maps to Inspect sandbox (`local|docker|k8s|proxmox`) |
| `--net` | N0|N1|N2 | — | Override N component only. | For cluster/network policy integration |
| `--approval` | enum | `dev` | Approvals preset (`ci`|`dev`|`prod`). | — |
| `--time-limit` | int (sec) | 120 | Real‑time budget for the loop. | — |
| `--max-steps` | int | 20 | Maximum reasoning/tool steps. | — |
| `--enable-browser` | flag | false | Also enable browser tools (T0 only recommended). | `INSPECT_ENABLE_WEB_BROWSER=1` |
| `--enable-web-search` | flag | false | Enable `web_search()` tool. | `INSPECT_ENABLE_WEB_SEARCH=1` + search keys |
| `--log-dir` | path | `INSPECT_LOG_DIR` or `./logs` | Where to write logs and traces. | `INSPECT_LOG_DIR`, `INSPECT_TRACE_FILE` |

### Demos

simple_arch_demo.py (examples/demos/simple_arch_demo.py)

```bash
uv run python -m examples.demos.simple_arch_demo --mode supervisor "Research topic ..."
```

| Argument | Type | Default | Description |
|---|---|---:|---|
| `task` | str (positional) | — | The demo task string. |
| `--mode` | enum | `supervisor` | Choose agent style (`supervisor` or `iterative`). |
| `--dev-approvals` | flag | false | Enable dev approvals preset (handoff exclusivity, kill‑switch). |

subagent_approvals_demo.py (examples/demos/subagent_approvals_demo.py)

```bash
uv run python examples/demos/subagent_approvals_demo.py --preset dev
```

| Argument | Type | Default | Description | Related env |
|---|---|---:|---|---|
| `--preset` | enum | `dev` | Approvals preset (`ci`|`dev`|`prod`). | Default can be set with `DEMO_APPROVAL_PRESET` |

## Notes

- Paths and imports: each runner/task sets `REPO_ROOT = Path(__file__).resolve().parents[2]` so local `src/` code is imported from this repo.
- Environment: runners/tasks load `.env` from the repo root and their own folder (if present). You can also pass `--env-file` to runners that support it or set `INSPECT_ENV_FILE`.
- Providers: defaults prefer local providers (e.g., Ollama/LM Studio). Override via CLI flags or env (see docs/reference/environment.md).
