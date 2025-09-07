# Model Resolver — Explain API

The model resolver now exposes a typed, machine‑readable trace so operators and tests can verify how a final model string was chosen and why failures occur.

- API: `resolve_model_explain(provider: str | None = None, model: str | None = None, role: str | None = None) -> tuple[str, ModelResolutionTrace]`
- Types: `ModelResolutionTrace`, `ModelResolutionStep`, and `ResolveModelError` (carries `.trace` and `.final_step`).
- Backwards‑compatible: existing `resolve_model(...)` behavior is unchanged; it delegates internally and still raises `RuntimeError` with the same messages.

## What the Trace Contains

Each resolution hop appends a `ModelResolutionStep`:

- `path`: label of the decision branch (e.g., `explicit_model_with_provider`, `role_env_mapping`, `env_INSPECT_EVAL_MODEL`, `provider_openai`, `provider_openai_api_<vendor>`, `provider_ollama`, `fallback_model_with_provider`, `final_fallback_ollama`).
- `provider_arg`, `model_arg`, `role`: raw function arguments.
- `role_env_model`, `role_env_provider`: values derived from `INSPECT_ROLE_<ROLE>_MODEL` / `_PROVIDER` when role mapping is used.
- `env_inspect_eval_model`: current `INSPECT_EVAL_MODEL` value.
- `final_candidate`: the model string candidate selected at this step (if any).

The `ModelResolutionTrace.final` field holds the final resolved model string when successful.

## Examples

Resolve an explicit provider/model (short path):

```python
from inspect_agents import resolve_model_explain
final, trace = resolve_model_explain(model="openai/gpt-4o-mini")
print(final)           # "openai/gpt-4o-mini"
print(trace.steps[-1].path)  # "explicit_model_with_provider"
```

Resolve by role mapping via env:

```python
import os
from inspect_agents import resolve_model_explain
os.environ["INSPECT_ROLE_CODER_MODEL"] = "gpt-4o-mini"
os.environ["INSPECT_ROLE_CODER_PROVIDER"] = "openai"
os.environ["OPENAI_API_KEY"] = "<redacted>"
final, trace = resolve_model_explain(role="coder")
# final == "openai/gpt-4o-mini"
# trace steps include "role_env_mapping" and end with "provider_openai"
```

OpenAI‑compatible vendor (LM Studio):

```python
import os
from inspect_agents import resolve_model_explain
os.environ["LM_STUDIO_API_KEY"] = "x"
os.environ["LM_STUDIO_MODEL"] = "qwen3"
final, trace = resolve_model_explain(provider="openai-api/lm-studio")
# final == "openai-api/lm-studio/qwen3"
# trace.steps[-1].path == "provider_openai_api_lm-studio"
```

INSPECT_EVAL_MODEL override and sentinel:

```python
import os
from inspect_agents import resolve_model_explain
os.environ["INSPECT_EVAL_MODEL"] = "openai/gpt-4o-mini"
final, trace = resolve_model_explain()
# final == "openai/gpt-4o-mini" via "env_INSPECT_EVAL_MODEL"

# Disable via sentinel
os.environ["INSPECT_EVAL_MODEL"] = "none/none"
final2, trace2 = resolve_model_explain()
# final2 starts with "ollama/"; path is "provider_ollama" or "final_fallback_ollama"
```

## Common Failure Messages (and Fixes)

- "Provider 'openai' requires OPENAI_API_KEY to be set."
  - Set `OPENAI_API_KEY` (or the vendor‑specific `*_API_KEY` for `openai-api/<vendor>`), then retry.

- "Model not specified for provider '<name>'. Set the 'model' argument or <NAME>_MODEL environment variable."
  - Either pass `model=...` to the function, or set `<PROVIDER>_MODEL` (e.g., `OPENAI_MODEL=gpt-4o-mini`). For `openai-api/<vendor>`, set `<VENDOR>_MODEL` (e.g., `LM_STUDIO_MODEL`).

- Role mapping returns `inspect/<role>` instead of a concrete model.
  - No `INSPECT_ROLE_<ROLE>_MODEL` was configured. Either set that (optionally with `INSPECT_ROLE_<ROLE>_PROVIDER`) or allow runtime to route `inspect/<role>`.

- Unexpected local fallback to Ollama.
  - The resolver default is local‑first if no provider/model/role mapping is set. Set `INSPECT_EVAL_MODEL`, or configure `DEEPAGENTS_MODEL_PROVIDER` and the corresponding `<PROVIDER>_MODEL` to avoid implicit fallback.

## When to Use `resolve_model_explain`

- CI and unit tests that need to assert precedence and exact decision paths.
- CLI UX and operator tooling to surface actionable diagnostics instead of scraping logs.
- Debugging environment issues (`INSPECT_EVAL_MODEL`, role mappings, provider API keys) quickly.

`resolve_model(...)` remains the top‑level helper when a string is sufficient and structured diagnostics are not needed.

See also: CLI companion example in docs/cli/model_explain.md for a ready‑to‑run script that prints the trace in table or JSON form.
