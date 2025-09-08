---
search:
  boost: 2
---

# Inspect Agents

Build, run, and evaluate reliable multi‑step LLM agents on top of Inspect‑AI — with safe defaults, rich tools, and a fast path from “hello world” to production.

- Fast to first success: install and run in minutes.
- Safe by default: approvals, sandboxing, and observability baked in.
- Batteries included: CLI, tools, and clear docs for every track.

## Quickstart

Choose your setup and run the commands below to install,
configure env files, and launch the docs locally.

=== "uv"

```bash
uv sync
uv run python env_templates/configure.py
uv run mkdocs serve
```

=== "pip"

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .
python env_templates/configure.py
mkdocs serve
```

Then open http://127.0.0.1:8000. Project docs live under `docs/` and the site is configured via `mkdocs.yml`.

## Choose Your Track

<div class="grid cards" markdown>

- **Tutorials** — Start here for an end‑to‑end, guided path from install to first working agent.

  [Get started](getting-started/inspect_agents_quickstart.md)

- **How‑to Guides** — Task‑oriented recipes (approvals, filesystem tools, sandboxing, operations).

  [Browse how‑to](how-to/index.md)

- **Reference** — API surfaces, environment flags, CLI commands, and built‑in tools.

  [Open reference](reference/index.md)

- **Explanation** — Concepts, architecture, and ADRs for deeper understanding and design decisions.

  [Read concepts](explanation/index.md)

- **CLI** — Run tasks, inspect logs, score runs, and more with the `inspect` command.

  [Use the CLI](cli/README.md)

- **Tools** — Catalog of built‑in tools (bash, files, web, python, think, typed results, etc.).

  [Explore tools](tools/README.md)

</div>

## Next Steps

- Run your first task: `uv run inspect eval examples/inspect/prompt_task.py -T prompt="Write a concise overview of Inspect‑AI"`
- Try the Python runner: `uv run python examples/inspect/run.py "Write a short overview of Inspect‑AI"`
- Configure environment flags as needed: [Environment variables](reference/environment.md)
- Full map of the documentation: [Docs index](DOCS_INDEX.md)

## Community

- Project repo and issues: https://github.com/cnm13ryan/inspect_agents
- Contributing guide and examples: https://github.com/cnm13ryan/inspect_agents#readme
