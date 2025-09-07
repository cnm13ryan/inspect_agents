# Model Resolver Explain — CLI Example

A tiny helper script demonstrates the new model resolver “explain” trace for operators.

- Script: `examples/inspect/model_explain.py`
- Modes: human-readable table (default) or `--json` for machine-readable output.

## Usage

- Explicit provider/model (short path):

```bash
python examples/inspect/model_explain.py --model openai/gpt-4o-mini --json
```

Example JSON output:

```json
{
  "ok": true,
  "final": "openai/gpt-4o-mini",
  "trace": {
    "final": "openai/gpt-4o-mini",
    "steps": [
      {
        "env_inspect_eval_model": null,
        "final_candidate": "openai/gpt-4o-mini",
        "model_arg": "openai/gpt-4o-mini",
        "path": "explicit_model_with_provider",
        "provider_arg": null,
        "role": null,
        "role_env_model": null,
        "role_env_provider": null
      }
    ]
  }
}
```

- Role mapping (no env → role indirection):

```bash
python examples/inspect/model_explain.py --role coder
```

- Default (no args → local-first):

```bash
python examples/inspect/model_explain.py
```

If a remote provider is selected without required API keys, the script exits non‑zero and prints the attached trace; add `--json` to capture a structured error payload.
