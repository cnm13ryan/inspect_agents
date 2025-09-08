# Environment Flags Reference

Centralized reference for environment variables that control providers/models,
tools, filesystem/sandbox, quarantine limits, logging, caching, and CI/test
behavior in this repo. Each section lists defaults, when-to-use guidance, and
example exports. See env_templates/inspect.env for a ready-to-copy template.

Links: guides on tools and safety
- Tool umbrellas and guidance: ../guides/tool-umbrellas.md
- Stateless vs stateful: ../guides/stateless-vs-stateful-tools-harmonized.md
- Sub-agent quarantine: ../guides/subagents.md
- Filesystem sandbox guardrails: ../adr/0004-filesystem-sandbox-guardrails.md
- Model roles + precedence: ../adr/0002-model-roles-map.md


## How Configuration Loads (Precedence)

- Real environment variables (highest precedence)
- Repository .env (if present)
- File pointed at by `INSPECT_ENV_FILE`
- Example template: env_templates/inspect.env (lowest precedence)

Tip
- Point the runner to a file: `--env-file env_templates/inspect.env`
- Or export: `export INSPECT_ENV_FILE=env_templates/inspect.env`

## Generated — Common Environment Flags

The blocks below are generated from a single machine‑readable spec to avoid drift between docs and templates. Do not edit between the markers by hand.

<!-- BEGIN GENERATED: ENV_REFERENCE -->
<!-- GENERATED: do not edit by hand -->

#### Approvals & Policies
| Env | Type | Default | Sensitive | Description |
|---|---|---:|---:|---|
| `INSPECT_APPROVAL_PRESET` | enum |  | no | Approvals preset: ci \| dev \| prod (optional). |

#### Debug
| Env | Type | Default | Sensitive | Description |
|---|---|---:|---:|---|
| `INSPECT_AGENTS_SUPPRESS_TOOL_WRAPPER_WARN` | bool | False | no | Suppress DeprecationWarning from legacy file wrappers (CI noise). |
| `INSPECT_MODEL_DEBUG` | bool | False | no | Enable model resolver debug logs. |
| `INSPECT_PRUNE_DEBUG` | bool | False | no | Emit prune/truncation info logs in iterative loop. |

#### Filesystem & Sandbox
| Env | Type | Default | Sensitive | Description |
|---|---|---:|---:|---|
| `INSPECT_AGENTS_FS_MAX_BYTES` | int | 5000000 | no | Maximum per‑file byte ceiling (OOM guard). |
| `INSPECT_AGENTS_FS_MODE` | string | store | no | Filesystem mode: store (in‑memory) \| sandbox (host‑routed). |
| `INSPECT_AGENTS_FS_READ_ONLY` | bool | False | no | Sandbox read‑only mode: block write/edit/delete; allow ls/read. |
| `INSPECT_AGENTS_FS_ROOT` | path | /repo | no | Absolute root for sandbox confinement. |
| `INSPECT_AGENTS_TOOL_TIMEOUT` | int | 15 | no | Default per‑tool timeout (seconds). |
| `INSPECT_AGENTS_TYPED_RESULTS` | bool | False | no | Return typed tool result models instead of plain strings/lists. |
| `INSPECT_SANDBOX_LOG_PATHS` | bool | False | no | Log fs_root/tool context in sandbox preflight warnings. |
| `INSPECT_SANDBOX_PREFLIGHT` | string | auto | no | Sandbox preflight mode: auto \| skip \| force. |
| `INSPECT_SANDBOX_PREFLIGHT_TTL_SEC` | int | 300 | no | Preflight result cache TTL seconds. |

#### Iterative Agent
| Env | Type | Default | Sensitive | Description |
|---|---|---:|---:|---|
| `INSPECT_ITERATIVE_MAX_STEPS` | int |  | no | Maximum reasoning/tool steps (unset disables). |
| `INSPECT_ITERATIVE_TIME_LIMIT` | int |  | no | Real-time budget in seconds (unset disables). |
| `INSPECT_PER_MSG_TOKEN_CAP` | int | 0 | no | Per-message token cap (0 disables). |
| `INSPECT_PRODUCTIVE_TIME` | bool | False | no | Subtract provider retry wait from time budget (where supported). |
| `INSPECT_PRUNE_AFTER_MESSAGES` | int | 120 | no | Threshold to apply global prune. |
| `INSPECT_PRUNE_KEEP_LAST` | int | 40 | no | Tail size to retain during pruning. |
| `INSPECT_TRUNCATE_LAST_K` | int | 200 | no | Keep last K messages during token-aware truncation. |

#### Observability
| Env | Type | Default | Sensitive | Description |
|---|---|---:|---:|---|
| `INSPECT_LIMIT_NEARING_THRESHOLD` | float | 0.8 | no | Runner near-limit threshold (0<val<1). |
| `INSPECT_LOG_DIR` | path | .inspect/logs | no | Transcript/log output directory. |
| `INSPECT_MAX_TOOL_OUTPUT` | int | 16384 | no | Global tool-output cap bytes (0 disables). |
| `INSPECT_TOOL_OBS_TRUNCATE` | int | 200 | no | Max chars for string fields in tool logs. |
| `INSPECT_TRACE_FILE` | path |  | no | Optional trace file path. |

#### Providers & Models
| Env | Type | Default | Sensitive | Description |
|---|---|---:|---:|---|
| `DEEPAGENTS_MODEL_PROVIDER` | string | ollama | no | Model provider when model lacks explicit prefix (e.g., ollama, lm-studio, openai). |
| `INSPECT_EVAL_MODEL` | string |  | no | Explicit Inspect model id (may include provider prefix). |

#### Retries & Backoff
| Env | Type | Default | Sensitive | Description |
|---|---|---:|---:|---|
| `INSPECT_RETRY_DISABLE_TENACITY` | bool | False | no | Bypass Tenacity; use fallback retry loop. |
| `INSPECT_RETRY_INITIAL_SECONDS` | float | 1.0 | no | Initial backoff seconds. |
| `INSPECT_RETRY_JITTER` | float | 0.0 | no | Optional jitter seconds (>0 to enable). |
| `INSPECT_RETRY_MAX_ATTEMPTS` | int | 6 | no | Max attempts including first call. |
| `INSPECT_RETRY_MAX_SECONDS` | float | 60.0 | no | Max backoff seconds. |

#### Tool Toggles
| Env | Type | Default | Sensitive | Description |
|---|---|---:|---:|---|
| `INSPECT_ENABLE_EXEC` | bool | False | no | Enable bash() and python() tools (requires sandbox). |
| `INSPECT_ENABLE_TEXT_EDITOR_TOOL` | bool | False | no | Expose text_editor() tool directly (FS tools already route to it in sandbox). |
| `INSPECT_ENABLE_THINK` | bool | on when unset | no | Enable think() helper (lightweight; defaults to on when unset). |
| `INSPECT_ENABLE_WEB_BROWSER` | bool | False | no | Enable web_browser() tools (requires sandbox + Playwright). |
| `INSPECT_ENABLE_WEB_SEARCH` | bool | False | no | Enable web_search() tool (requires Tavily or Google CSE keys). |
| `INSPECT_WEB_SEARCH_INTERNAL` | string |  | no | Prefer internal provider for web search augmentation (e.g., openai, anthropic). |
<!-- END GENERATED: ENV_REFERENCE -->

### Copy‑Paste Template Snippet

<!-- BEGIN GENERATED: ENV_TEMPLATE -->
```bash
# GENERATED: do not edit by hand

## Approvals & Policies
# INSPECT_APPROVAL_PRESET=

## Debug
# INSPECT_AGENTS_SUPPRESS_TOOL_WRAPPER_WARN=0
# INSPECT_MODEL_DEBUG=0
# INSPECT_PRUNE_DEBUG=0

## Filesystem & Sandbox
# INSPECT_AGENTS_FS_MAX_BYTES=5000000
# INSPECT_AGENTS_FS_MODE=store
# INSPECT_AGENTS_FS_READ_ONLY=0
# INSPECT_AGENTS_FS_ROOT=/repo
# INSPECT_AGENTS_TOOL_TIMEOUT=15
# INSPECT_AGENTS_TYPED_RESULTS=0
# INSPECT_SANDBOX_LOG_PATHS=0
# INSPECT_SANDBOX_PREFLIGHT=auto
# INSPECT_SANDBOX_PREFLIGHT_TTL_SEC=300

## Iterative Agent
# INSPECT_ITERATIVE_MAX_STEPS=
# INSPECT_ITERATIVE_TIME_LIMIT=
# INSPECT_PER_MSG_TOKEN_CAP=0
# INSPECT_PRODUCTIVE_TIME=0
# INSPECT_PRUNE_AFTER_MESSAGES=120
# INSPECT_PRUNE_KEEP_LAST=40
# INSPECT_TRUNCATE_LAST_K=200

## Observability
# INSPECT_LIMIT_NEARING_THRESHOLD=0.8
# INSPECT_LOG_DIR=.inspect/logs
# INSPECT_MAX_TOOL_OUTPUT=16384
# INSPECT_TOOL_OBS_TRUNCATE=200
# INSPECT_TRACE_FILE=

## Providers & Models
# DEEPAGENTS_MODEL_PROVIDER=ollama
# INSPECT_EVAL_MODEL=

## Retries & Backoff
# INSPECT_RETRY_DISABLE_TENACITY=0
# INSPECT_RETRY_INITIAL_SECONDS=1.0
# INSPECT_RETRY_JITTER=0.0
# INSPECT_RETRY_MAX_ATTEMPTS=6
# INSPECT_RETRY_MAX_SECONDS=60.0

## Tool Toggles
# INSPECT_ENABLE_EXEC=0
# INSPECT_ENABLE_TEXT_EDITOR_TOOL=0
# INSPECT_ENABLE_THINK=
# INSPECT_ENABLE_WEB_BROWSER=0
# INSPECT_ENABLE_WEB_SEARCH=0
# INSPECT_WEB_SEARCH_INTERNAL=

```bash<!-- END GENERATED: ENV_TEMPLATE -->

### When Settings Take Effect

- Most environment flags are read at process start and/or when the relevant component is constructed. For example, standard tool toggles are applied when tools are built for an agent, and runner options are read when the runner starts.
- There is no global hot reload. Changing environment variables after startup does not retroactively update already-constructed agents/configs/tools. Restart the process (or rebuild the agent/config and re-run the command) to apply changes.


## Conventions

- Truthy booleans — unless stated otherwise, boolean flags interpret the following values as true (case-insensitive): `1`, `true`, `yes`, `on`. Unset, empty, or any other value is treated as false.

## Environment & Settings API

- Prefer the centralized helpers in `inspect_agents.settings` when reading environment variables in code: `truthy`, `int_env`, `float_env`, and `str_env`.
- These helpers ensure consistent parsing and defaults across modules and reduce drift with docs and examples.
- The Settings API also exposes `typed_results_enabled()` and `default_tool_timeout()` used by tools and FS utilities.

References
- API docs: ../api/settings.md
- Code examples in this repo use `from inspect_agents import settings as s` and then `s.truthy(os.getenv("FLAG"))`, or `s.int_env("VAR", default=10, minimum=1)`, etc.


## Providers & Models (Role Mapping, Precedence)

- `DEEPAGENTS_MODEL_PROVIDER` (default: `ollama`)
  - Selects the provider when no explicit model prefix is given.
  - Examples: `ollama`, `lm-studio`, `openai`, `anthropic`, `google`, `groq`,
    `mistral`, `perplexity`, `fireworks`, `grok`, `goodfire`, `openrouter`.

- Role mapping (set per role; role name uppercased, hyphens→underscores)
  - `INSPECT_ROLE_<ROLE>_MODEL` — full path (`openai/gpt-4o-mini`) or bare
    tag (`llama3.1`).
  - `INSPECT_ROLE_<ROLE>_PROVIDER` — only needed if model is a bare tag.

- Global override (optional)
  - `INSPECT_EVAL_MODEL` — full Inspect model string (e.g., `openai/gpt-4o-mini`).
    If set to `none/none`, the override is ignored.

- Provider-specific keys and tags
  - Local providers
    - `OLLAMA_MODEL_NAME` (e.g., `llama3.1:8b`), optional `OLLAMA_BASE_URL`.
    - `LM_STUDIO_BASE_URL`, `LM_STUDIO_MODEL_NAME` (default `local-model`),
      `LM_STUDIO_API_KEY` (placeholder token OK for local).
  - Remote providers (require API keys + model tag)
    - `OPENAI_API_KEY` (sensitive), `OPENAI_MODEL`
    - `ANTHROPIC_API_KEY` (sensitive), `ANTHROPIC_MODEL`
    - `GOOGLE_API_KEY` (sensitive), `GOOGLE_MODEL`
    - `GROQ_API_KEY` (sensitive), `GROQ_MODEL`
    - `MISTRAL_API_KEY` (sensitive), `MISTRAL_MODEL`
    - `PERPLEXITY_API_KEY` (sensitive), `PERPLEXITY_MODEL`
    - `FIREWORKS_API_KEY` (sensitive), `FIREWORKS_MODEL`
    - `GROK_API_KEY` (sensitive), `GROK_MODEL`
    - `GOODFIRE_API_KEY` (sensitive), `GOODFIRE_MODEL`
    - `OPENROUTER_API_KEY` (sensitive), `OPENROUTER_MODEL`
  - OpenAI‑compatible vendors via `openai-api/<vendor>` also use
    `<VENDOR>_API_KEY` and `<VENDOR>_MODEL` (e.g., `LM_STUDIO_*`).

!!! note "Upstream Inspect‑AI environment variables"
    Some environment variables are defined and consumed by the upstream Inspect‑AI CLI/runtime rather than this repository. Common examples include:

    - `INSPECT_EVAL_MODEL_ARGS`
    - `INSPECT_EVAL_MODEL_CONFIG`
    - `INSPECT_EVAL_MODEL_ROLE`

    For the complete list and semantics, see the upstream options reference in this repo checkout: external/inspect_ai/docs/options.qmd.

    - Direct path (local checkout): [external/inspect_ai/docs/options.qmd](../../external/inspect_ai/docs/options.qmd)
    - When using the Inspect CLI, also see its built‑in `inspect eval --help`.

Resolution order (highest wins)
1) Explicit `model` with provider prefix (contains `/`).
2) Role mapping via `INSPECT_ROLE_<ROLE>_*`; otherwise use `inspect/<role>`.
3) `INSPECT_EVAL_MODEL` (when set to a concrete model, not `none/none`).
4) Provider: function arg → `DEEPAGENTS_MODEL_PROVIDER` → `ollama`.
5) Provider‑specific defaults/validation.

Debugging
- `INSPECT_MODEL_DEBUG` — boolean (truthy values like `1/true/yes/on`; default off).
  - When set, the resolver emits INFO logs detailing model resolution and role
    mapping, including `role`, `provider_arg`, `model_arg`, `role_env_model`,
    `role_env_provider`, `env_inspect_eval_model`, the computed `final`, and the
    decision `path`. Use this to troubleshoot why a particular model/provider
    was selected.

Example
```bash
export INSPECT_MODEL_DEBUG=1
```

Examples
```bash
# Force OpenAI across the board
export DEEPAGENTS_MODEL_PROVIDER=openai
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-4o-mini

# Role mapping: grader uses a specific OpenAI model; others keep defaults
export INSPECT_ROLE_GRADER_PROVIDER=openai
export INSPECT_ROLE_GRADER_MODEL=gpt-4o-mini

# Local defaults
export OLLAMA_MODEL_NAME=llama3.1:8b
export LM_STUDIO_BASE_URL=http://127.0.0.1:1234/v1
export LM_STUDIO_MODEL_NAME=local-model
export LM_STUDIO_API_KEY=lm-studio
```

Security note — treat API keys as secrets
- Never commit provider keys to source control.
- Prefer platform secret stores and point `INSPECT_ENV_FILE` at a mounted file.


One‑time fallback hint (local‑first)
- When no explicit model, role mapping, or provider config is set, the resolver falls back to `ollama/<tag>` and emits a one‑time INFO log mentioning `final_fallback_ollama`. Configure one of the following to avoid implicit local fallback:
  - Set a full model: `INSPECT_EVAL_MODEL=openai/gpt-4o-mini`
  - Or set provider + model: `DEEPAGENTS_MODEL_PROVIDER=openai` and `OPENAI_MODEL=gpt-4o-mini`
  - Or use role mapping: `INSPECT_ROLE_GRADER_PROVIDER=openai` and `INSPECT_ROLE_GRADER_MODEL=gpt-4o-mini`
  - To disable a previously set global override without clearing env, use the sentinel: `INSPECT_EVAL_MODEL=none/none` (ignored by the resolver)


## Model Retries & Backoff

- `INSPECT_RETRY_MAX_ATTEMPTS` — max attempts including the first (default `6`).
- `INSPECT_RETRY_INITIAL_SECONDS` — initial backoff (default `1.0`).
- `INSPECT_RETRY_MAX_SECONDS` — cap on backoff (default `60.0`).
- `INSPECT_RETRY_JITTER` — if `> 0`, adds jitter to waits in seconds (default `0`).
- `INSPECT_RETRY_DISABLE_TENACITY` — truthy values (`1/true/yes/on`) bypass the Tenacity‑based path and force the fallback retry loop even when Tenacity is installed (default off).

Precedence
- Function args passed to `generate_with_retry_time(...)` take precedence over env; if an arg is `None`, the env var is consulted; otherwise the built‑in default applies.
- Tenacity selection precedence for the wrapper: `force_fallback` kwarg > `INSPECT_RETRY_DISABLE_TENACITY` > auto‑detect of Tenacity availability.

Developer note
- The retry wrapper `inspect_agents._model_retry.generate_with_retry_time(...)` accepts an optional kwarg `force_fallback: bool | None = None`. Set `True` to bypass Tenacity regardless of env; leave as `None` to defer to `INSPECT_RETRY_DISABLE_TENACITY`.

Examples
```bash
# Force fallback loop and set a tight, deterministic retry budget
export INSPECT_RETRY_DISABLE_TENACITY=1
export INSPECT_RETRY_MAX_ATTEMPTS=3
export INSPECT_RETRY_INITIAL_SECONDS=0.01
export INSPECT_RETRY_MAX_SECONDS=0.02
export INSPECT_RETRY_JITTER=0
```

## Approvals & Presets

- `INSPECT_APPROVAL_PRESET` — `ci | dev | prod`. When set, and when callers do not pass an explicit `approval=[...]` to the runner, `run_agent(...)` auto‑initializes approvals using the chosen preset before starting the Inspect run.
  - `ci`: approve all tools (no‑op gate).
  - `dev`: include handoff exclusivity; escalate sensitive tools (e.g., `write_file`, `text_editor`, `bash`, `python`, `web_browser_*`).
  - `prod`: include handoff exclusivity; terminate sensitive tools with redacted context.
  - Parallel kill‑switch is included in the preset chain but only enforces when a kill‑switch env is truthy (see next section).

Notes
- The env preset is ignored when an explicit `approval=[...]` is provided (explicit wins).

Examples
```bash
export INSPECT_APPROVAL_PRESET=dev
```


## Tool Toggles (When to Use)

- `INSPECT_ENABLE_THINK` (default: on when unset) — lightweight; safe to enable.
- `INSPECT_ENABLE_WEB_SEARCH` (default: off unless a provider is configured)
  - External providers
    - `TAVILY_API_KEY` (recommended for simplicity)
    - `GOOGLE_CSE_API_KEY` + `GOOGLE_CSE_ID`
  - Internal provider preference: `INSPECT_WEB_SEARCH_INTERNAL`
    (`openai|anthropic|perplexity|gemini|grok`) — optional augment.
- `INSPECT_ENABLE_EXEC` (bash, python) — keep off unless running in a sandbox
  with approvals.
- `INSPECT_ENABLE_WEB_BROWSER` — heavy; enable only with sandbox + approvals.
- `INSPECT_ENABLE_TEXT_EDITOR_TOOL` — optional; the file tools call the editor
  internally in sandbox mode, so exposing it directly is rarely needed.

Policy note
- There is no environment flag in this repo to expose `bash_session`. It is reserved for internal use by the filesystem sandbox adapter and is never returned by `standard_tools()`. Enabling `INSPECT_ENABLE_EXEC` exposes only the single‑shot `bash()` and `python()` tools (no persistent shell session).

Examples
```bash
# Enable light helpers
export INSPECT_ENABLE_THINK=1
export INSPECT_ENABLE_WEB_SEARCH=1
export TAVILY_API_KEY=...

# Power tools (only in sandboxed/dev environments)
export INSPECT_ENABLE_EXEC=1
export INSPECT_ENABLE_WEB_BROWSER=1
export INSPECT_ENABLE_TEXT_EDITOR_TOOL=1
```

See: ../guides/tool-umbrellas.md and ../getting-started/inspect_agents_quickstart.md


## Parallel Tool Execution (Kill‑Switch)

- `INSPECT_DISABLE_TOOL_PARALLEL` — truthy values (`1/true/yes/on`) force
  serial approval for non‑handoff tools within a single assistant turn. When the
  model emits multiple `tool_calls` and no handoff is present, only the first
  non‑handoff tool is approved; subsequent non‑handoff calls are rejected. A
  standardized transcript ToolEvent is emitted with
  `metadata.source="policy/parallel_kill_switch"` for skipped calls.
  Effective only when approval policies are active (the `dev`/`prod` presets
  include this policy; `ci` does not). Handoff tools remain serial and are
  governed by the handoff‑exclusivity policy.
- `INSPECT_TOOL_PARALLELISM_DISABLE` — legacy alias; supported for backward
  compatibility, but prefer `INSPECT_DISABLE_TOOL_PARALLEL`.

Examples
```bash
export INSPECT_DISABLE_TOOL_PARALLEL=1   # allow only the first non‑handoff tool per turn
```


## Filesystem & Sandbox (Mode, Safety, Limits)

- `INSPECT_AGENTS_FS_MODE` — `store` (default) | `sandbox`
  - `store`: in‑memory virtual FS (isolated per run).
  - `sandbox`: routes file ops through Inspect’s sandbox tools
    (`text_editor`; `bash_session` for `ls`).
- `INSPECT_AGENTS_TOOL_TIMEOUT` — per‑call tool timeout in seconds (default 15).
- `INSPECT_AGENTS_TYPED_RESULTS` — `1/true` to return typed objects from tools
  instead of strings/lists (default off).
- `INSPECT_SANDBOX_PREFLIGHT` — `auto` (default) | `skip` | `force`
  - `auto`: perform preflight; on failure, log a one‑time `files:sandbox_preflight` warning and fall back to store.
  - `skip`: return `False` from the preflight without logging; callers fall back deterministically.
  - `force`: perform preflight and raise on failure (no fallback). Intended for operator workflows where sandbox is mandatory.
- `INSPECT_SANDBOX_PREFLIGHT_TTL_SEC` — cache TTL in seconds for the preflight result (default `300`). Set `0` to disable caching and recheck each call.
- `INSPECT_SANDBOX_LOG_PATHS` — `1/true` to enrich the `files:sandbox_preflight` warning with contextual fields like `fs_root` and `tool`.
- `INSPECT_AGENTS_FS_READ_ONLY` — `1/true` enables audited read‑only mode in
  sandbox. When `INSPECT_AGENTS_FS_MODE=sandbox` and this flag is truthy,
  write/edit/delete operations are blocked: the files tool raises a
  `ToolException("SandboxReadOnly")` and emits a `tool_event` with
  `phase="error"` and `error="SandboxReadOnly"`. Listing and reading remain
  allowed. Has no effect in `store` mode.
- `INSPECT_AGENTS_FS_ROOT` — absolute root path for sandbox confinement (default `/repo`). Must be an absolute path; non‑absolute values are converted to absolute.
- `INSPECT_AGENTS_FS_MAX_BYTES` — maximum allowed file size in bytes for read/write/edit operations (default `5_000_000`).

See also
- Design discussion and pending decisions: ../design/open-questions.md#filesystem-sandbox-%E2%80%94-read-only-mode-new

Safety notes
- In sandbox mode, delete is intentionally disabled in the file tool to avoid
  removing host files.
- Paths are not validated for traversal; rely on sandbox isolation for
  untrusted input.

Examples
```bash
export INSPECT_AGENTS_FS_MODE=sandbox
export INSPECT_SANDBOX_PREFLIGHT=auto
export INSPECT_SANDBOX_PREFLIGHT_TTL_SEC=300
export INSPECT_SANDBOX_LOG_PATHS=1
export INSPECT_AGENTS_FS_READ_ONLY=1   # block write/edit/delete; allow ls/read
export INSPECT_AGENTS_FS_ROOT=/repo    # absolute path for sandbox confinement
export INSPECT_AGENTS_FS_MAX_BYTES=5000000  # per‑file byte ceiling
export INSPECT_AGENTS_TOOL_TIMEOUT=20
export INSPECT_AGENTS_TYPED_RESULTS=1
```

See: ../adr/0004-filesystem-sandbox-guardrails.md and ../guides/tool-umbrellas.md


## Quarantine & Limits (Sub‑Agent Handoffs)

- `INSPECT_QUARANTINE_MODE` — `strict` (default) | `scoped` | `off`
  - `strict`: remove tools/system; keep only boundary message.
  - `scoped`: strict + append small JSON summary of Todos/Files.
  - `off`: identity (debug only).
- `INSPECT_QUARANTINE_INHERIT` — `1/true` to cascade the parent filter to
  nested handoffs (default on).
- Per‑agent override: `INSPECT_QUARANTINE_MODE__<agent_name>` (normalized to
  lowercase; non‑alphanumeric→`_`; collapsed underscores).
- Scoped caps (when `mode=scoped`)
  - `INSPECT_SCOPED_MAX_BYTES` (default 2048)
  - `INSPECT_SCOPED_MAX_TODOS` (default 10)
  - `INSPECT_SCOPED_MAX_FILES` (default 20)

Examples
```bash
export INSPECT_QUARANTINE_MODE=strict
export INSPECT_QUARANTINE_INHERIT=1
export INSPECT_QUARANTINE_MODE__researcher=scoped
export INSPECT_SCOPED_MAX_BYTES=2048
```

See: ../guides/subagents.md

### Per‑Agent Handoff Limits (Env)

Operators can set time/message/token budgets for specific sub‑agents without editing code or YAML. Agent names are normalized the same way as quarantine overrides: lower‑cased; non‑alphanumeric → `_`; repeated underscores collapsed.

- `INSPECT_LIMIT_TIME__<agent>`: time budget in seconds (float > 0)
- `INSPECT_LIMIT_MESSAGES__<agent>`: message budget (int > 0)
- `INSPECT_LIMIT_TOKENS__<agent>`: token budget (int > 0)

Precedence
- Explicit limits passed to the handoff (programmatic or YAML) win when non‑empty.
- If the sub‑agent config omits `limits` or sets an empty list, env budgets apply.

#### Precedence & Empty List — Examples

Note: non‑empty YAML `limits` > per‑agent env. An explicit empty list `limits: []` means “no explicit limits”, so env‑derived limits (if set) will apply.

Examples (YAML + Env)

1) YAML without `limits` + env → env applies

```yaml
subagents:
  - name: researcher
    mode: handoff
    tools: [web_search]
    # no `limits` key
```

```bash
export INSPECT_LIMIT_MESSAGES__researcher=8
```

Effect: researcher handoff is capped at 8 messages via env.

2) YAML with `limits: []` + env → env applies

```yaml
subagents:
  - name: researcher
    mode: handoff
    tools: [web_search]
    limits: []  # explicit empty list
```

```bash
export INSPECT_LIMIT_TIME__researcher=60
```

Effect: researcher handoff is capped at 60 seconds via env.

3) YAML with non‑empty `limits` + env → YAML wins

```yaml
subagents:
  - name: researcher
    mode: handoff
    tools: [web_search]
    limits:
      - type: messages
        max: 3
```

```bash
export INSPECT_LIMIT_MESSAGES__researcher=8
```

Effect: researcher handoff is capped at 3 messages (YAML overrides env).

Examples
```bash
# Cap the Researcher handoff at 60s and 8 messages
export INSPECT_LIMIT_TIME__researcher=60
export INSPECT_LIMIT_MESSAGES__researcher=8

# Budget the Writer by messages only
export INSPECT_LIMIT_MESSAGES__writer=8

# Cap the Grader by tokens
export INSPECT_LIMIT_TOKENS__grader=6000
```


## Runner Time‑Limit Telemetry

Emit an early "nearing" signal for the top‑level wall‑clock budget so operators can observe and react before a hard timeout.

- `INSPECT_LIMIT_NEARING_THRESHOLD` — fraction in (0,1); default `0.8`.
  - When a runner time limit is supplied to `run_agent(..., limits=[time_limit(S)])`, the runner schedules a single timer at `threshold * S` seconds that logs an info event:
    - `tool="limits"`, `phase="info"`, `event="limit_nearing"`, `scope="runner"`, `kind="time"`, plus `threshold` (seconds) and `used` (seconds).
  - The timer is cancelled on early completion to avoid stray logs.

Examples
```bash
# Fire the near‑limit event halfway to the limit
export INSPECT_LIMIT_NEARING_THRESHOLD=0.5
```

Sample log payload (single‑line JSON following the `tool_event` prefix):
```json
{"tool":"limits","phase":"info","event":"limit_nearing","scope":"runner","kind":"time","threshold":2.0,"used":1.0}
```


## Iterative Agent

- `INSPECT_PRUNE_DEBUG` — boolean (truthy values like `1/true/yes/on`; default off). When enabled, emits info‑level logs about pruning and per‑message truncation decisions inside the iterative loop to aid threshold tuning (also enabled when `INSPECT_MODEL_DEBUG` is truthy).

Examples
```bash
export INSPECT_PRUNE_DEBUG=1
```


## Logging & Display

- `INSPECT_LOG_DIR` — transcript directory (default `.inspect/logs`).
- `INSPECT_TOOL_OBS_TRUNCATE` — max chars for string fields in tool logs before
  truncation (default 200).
- `INSPECT_TRACE_FILE` — optional tracing file path (recognized by Inspect
  runtime; useful during reviews).
- `INSPECT_AGENTS_SUPPRESS_TOOL_WRAPPER_WARN` — boolean (truthy values like `1/true/yes/on`; default off). When enabled, suppresses `DeprecationWarning` messages emitted by legacy Files wrapper tools to reduce CI noise while migrating to the unified `files_tool`.

Examples
```bash
export INSPECT_LOG_DIR=.inspect/logs
export INSPECT_TOOL_OBS_TRUNCATE=200
export INSPECT_TRACE_FILE=logs/inspect_ai/trace.log
# Suppress legacy wrapper deprecation warnings in CI
export INSPECT_AGENTS_SUPPRESS_TOOL_WRAPPER_WARN=1
```


## Tool Output & Truncation

- `INSPECT_MAX_TOOL_OUTPUT` — maximum tool output in bytes (low precedence
  override). Parsed as a non-negative integer; `0` disables truncation. This
  is a coarse control for CI/ops and is only applied when no explicit per-call
  `max_output` and no per-run `GenerateConfig.max_tool_output` are set. If
  provided, the first tool event logs a one-time structured line:
  `tool_event {"tool":"observability","phase":"info","effective_tool_output_limit":N,"source":"env|default"}`.
Default (when unset and no config override): `16384` bytes.

Examples
```bash
# Cap tool outputs at 8 KiB across a run unless code sets an explicit limit
export INSPECT_MAX_TOOL_OUTPUT=8192

# Disable truncation (be careful: prompts can grow quickly)
export INSPECT_MAX_TOOL_OUTPUT=0
```

### Environment & Limits — Effective Tool‑Output Cap

What is actually enforced at runtime follows this precedence:

- Per‑call argument `max_output` (highest; passed by the tool invocation)
- Active `GenerateConfig.max_tool_output` ("config")
- `INSPECT_MAX_TOOL_OUTPUT` ("env")
- Built‑in default of 16 KiB ("default")

Query the currently effective cap (side‑effect free):

```python
from inspect_agents.observability import get_effective_tool_output_limit
limit, source = get_effective_tool_output_limit()  # (bytes, 'config'|'env'|'default')
print(limit, source)
```

CLI one‑liner (prints a single line):

```bash
uv run python examples/debug/show_limits.py
# -> Tool-output cap: 16384 bytes (default)
```

Notes
- The helper does not inspect per‑call `max_output` (that is dynamic per tool call).
- Example runners print the effective cap line at startup for quick visibility.


## Cache & Retries

- `UV_CACHE_DIR` — cache directory for `uv` package installs (build speed).
- Retries: no repo‑specific knobs; provider SDKs may define their own.

Examples
```bash
export UV_CACHE_DIR=.uv-cache
```


## Test / CI Knobs

- `CI=1` — enable CI mode in tools/tests where honored.
- `NO_NETWORK=1` — default offline tests; ensure deterministic behavior.
- Useful pytest envs (optional):
  - `PYTEST_ADDOPTS="--maxfail=1 -q"`
  - `PYTHONWARNINGS=default`
  - `PYTHONHASHSEED=0`

Examples
```bash
export CI=1
export NO_NETWORK=1
export PYTEST_ADDOPTS="--maxfail=1 -q"
```


## Environment Files & Templates

- Point runners to a file with `--env-file` or `INSPECT_ENV_FILE`.
- Start from env_templates/inspect.env and customize as needed.

Examples
```bash
uv run python examples/runners/supervisor_runner.py --env-file env_templates/inspect.env "..."
export INSPECT_ENV_FILE=env_templates/inspect.env
```
### CLI Flags ↔ Env Mapping

Use these flags with the example Python runners; they reflect into the same env toggles used by the library.

| CLI flag | Equivalent env | Notes |
|---|---|---|
| `--enable-think` | `INSPECT_ENABLE_THINK=1` | Lightweight helper; on by default unless explicitly set falsy. |
| `--enable-web-search` | `INSPECT_ENABLE_WEB_SEARCH=1` | Requires provider keys (Tavily or Google CSE). |
| `--enable-exec` | `INSPECT_ENABLE_EXEC=1` | Requires sandbox; enable only in sandbox/dev. |
| `--enable-web-browser` | `INSPECT_ENABLE_WEB_BROWSER=1` | Heavy; requires sandbox + Playwright. |
| `--enable-text-editor-tool` | `INSPECT_ENABLE_TEXT_EDITOR_TOOL=1` | Optional; FS tools route to the editor in sandbox mode. |

Note: These flags are surfaced by the example runners (e.g., supervisor_runner.py). See the Examples README for runner-specific details.

## Platform Appendix — Secure Injection of Environment

This appendix shows minimal, working examples to inject sensitive keys safely. Adjust names/paths to your deployment.

### Kubernetes (Secret mounted as file)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: inspect-env
type: Opaque
stringData:
  inspect.env: |
    OPENAI_API_KEY=...   # sensitive
    INSPECT_ENABLE_WEB_SEARCH=1
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: inspect-agents
spec:
  template:
    spec:
      containers:
        - name: app
          image: your/image:tag
          env:
            - name: INSPECT_ENV_FILE
              value: /etc/inspect/inspect.env
          volumeMounts:
            - name: inspect-env
              mountPath: /etc/inspect
              readOnly: true
      volumes:
        - name: inspect-env
          secret:
            secretName: inspect-env
```

Notes
- For single keys, you may instead use `env.valueFrom.secretKeyRef` per key.
- No global hot reload: update the Secret and restart Pods to apply changes.

### Docker Compose (secrets + env-file pointer)

```yaml
version: "3.9"
services:
  app:
    image: your/image:tag
    environment:
      INSPECT_ENV_FILE: /run/secrets/inspect_env
    secrets:
      - inspect_env
secrets:
  inspect_env:
    file: ./secrets/inspect.env   # contains OPENAI_API_KEY=..., etc.
```

Precedence
- Service `environment:` entries override values from `env_file`/secrets; process env at runtime overrides both.

### systemd (EnvironmentFile)

```ini
[Service]
EnvironmentFile=/etc/inspect/inspect.env
# Optional single-key override (discouraged for secrets)
# Environment=OPENAI_API_KEY=...
```

Usage
- Place `/etc/inspect/inspect.env` with `0600` perms and root ownership.
- Apply changes with: `sudo systemctl daemon-reload && sudo systemctl restart <unit>`.
