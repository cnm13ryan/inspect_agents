# inspect_agents
> Inspect‑AI–native agents with typed state, safe tools, and rich traces.

This library extends Inspect‑AI with higher‑level agent orchestration, typed state (todos and virtual files), and a small set of Inspect‑native tools. It is safe by default: optional standard tools (think, web_search, bash/python, web_browser, text_editor) are gated behind environment flags, and sandboxed filesystem operations are constrained.

![Quick Demo](docs/assets/demo.gif)

[![Build](https://img.shields.io/github/actions/workflow/status/cnm13ryan/inspect_agents/ci.yml?branch=main)](https://github.com/cnm13ryan/inspect_agents/actions)
[![Tests](https://img.shields.io/github/actions/workflow/status/cnm13ryan/inspect_agents/tests.yml?label=tests&branch=main)](https://github.com/cnm13ryan/inspect_agents/actions)
[![Coverage](https://img.shields.io/codecov/c/github/cnm13ryan/inspect_agents?branch=main)](https://app.codecov.io/gh/cnm13ryan/inspect_agents)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PyPI Version](https://img.shields.io/pypi/v/inspect-agents)](https://pypi.org/project/inspect-agents/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/inspect-agents)](https://pypi.org/project/inspect-agents/)
[![Last Commit](https://img.shields.io/github/last-commit/cnm13ryan/inspect_agents/main)](https://github.com/cnm13ryan/inspect_agents/commits/main)
[![Docs](https://img.shields.io/badge/docs-mkdocs%20material-0A7BBB)](https://cnm13ryan.github.io/inspect_agents)

## Quickstart (self‑contained)
Uses local sources via `PYTHONPATH` and requires no provider setup. This validates the code path without contacting external services.

```bash
export PYTHONPATH=src:external/inspect_ai
python examples/inspect/quickstart_toy.py
# Expected: Completion: DONE
```

[Next: Examples — Start Here →](examples/README.md#start-here)

[Docs Home →](https://cnm13ryan.github.io/inspect_agents)

## Why Inspect Agents?
Setting up practical LLM agents is slow: you fight glue code, logging, state, and tool orchestration. Inspect Agents removes overhead with an Inspect‑AI‑native workflow: typed state (todos/files), built‑in tools, and rich transcripts/traces by default. You can run a toy agent offline in seconds (see Quickstart above).

## Key Features
- ✅ Inspect‑native tools: Todos + virtual filesystem
  - Default: in‑memory “store” (ephemeral; isolated per run)
  - Optional: sandbox (routes through Inspect’s `text_editor`/`bash_session`; delete disabled)
  - Sandbox quickstart: see [docs/how-to/filesystem_sandbox_quickstart.md](docs/how-to/filesystem_sandbox_quickstart.md)
- ✅ Optional standard tools (gated by env flags):
  - `INSPECT_ENABLE_THINK` (default on), `INSPECT_ENABLE_WEB_SEARCH` (auto when provider keys set),
    `INSPECT_ENABLE_EXEC`, `INSPECT_ENABLE_WEB_BROWSER`, `INSPECT_ENABLE_TEXT_EDITOR_TOOL` (default off)
  - The stateful `bash_session` tool is never exposed by this repo; it’s used internally for sandbox FS.
- ✅ Typed state: Pydantic models backed by Inspect Store for `Todos` and `Files`
- ✅ Sub‑agents: “handoff” (transfer to `transfer_to_<name>`) or “tool” (single‑shot)
- ✅ Traces & transcripts: Structured tool events and store change logs by default
- ✅ Safe by default: approval presets (`dev`/`prod`), quarantine filters, sandbox confinement/symlink denial
- ✅ Self‑contained toy example to verify setup without external model providers

## Table of Contents
- Installation
- Usage (CLI and Python)
- Logs & Inspect View
- Examples
- Documentation
- Project Status
- Contributing
- Support

## Installation
- Python 3.11+ on macOS or Linux.
- For packaging/install instructions (pip or uv), see the docs site. The Quickstart above runs from source.

### Configure Environment Variables
If you use Inspect CLI or providers, see the Environment reference and the example configurator:

- Environment reference: [docs/reference/environment.md](docs/reference/environment.md)
- Example configurator: [env_templates/configure.py](env_templates/configure.py)

For the self‑contained Quickstart above, no configuration is required.

<!-- Quickstart moved to top for faster TTFX -->

## Usage
### Scaffold a new agent
Generate a minimal agent module in seconds.

```bash
# Creates src/<package>/<name>.py  (<package> is the dotted package path; <name> is normalized to snake_case)
python scripts/scaffold_agent.py my_helper --path . --package inspect_agents --no-test
```

Notes
- Safe by default: refuses to overwrite existing files unless `--force` (or confirms y/N when interactive).
- The template uses `build_iterative_agent(code_only=True)` so it runs without exec/search/browser tools.
- Creates `src/<package>/<name>.py` (under `src/<package>/`; `<name>` is normalized to snake_case, e.g., "MyAgent" → `my_agent.py`).
- By default a smoke test is also created at `tests/<package>/test_<name>.py`; in the example above we pass `--no-test` to skip it (omit `--no-test` to generate the test).

### FS tools (store mode)
Short, deterministic example that writes, lists, and reads a file using the in‑memory store (no host filesystem writes).

```python
import asyncio, os

# Ensure store mode (default), i.e., in‑memory virtual filesystem
os.environ["INSPECT_AGENTS_FS_MODE"] = "store"

from inspect_agents.tools import write_file, read_file, ls

async def main():
    w = write_file(); r = read_file(); l = ls()
    await w(file_path="demo.txt", content="Hello\nWorld")
    print(await l())                  # → ["demo.txt"]
    print(await r(file_path="demo.txt", offset=0, limit=10))
    # → numbered output:
    #     1\tHello
    #     2\tWorld

asyncio.run(main())
```

Note: In store mode these paths live in an in‑memory store tied to the current process context, not your disk. For sandbox mode, see the quickstart: [docs/how-to/filesystem_sandbox_quickstart.md](docs/how-to/filesystem_sandbox_quickstart.md) and the full guide: [docs/how-to/filesystem.md](docs/how-to/filesystem.md).

### CLI (Inspect)
When using Inspect CLI and tasks, see:
- Evaluated examples: [docs/cli/inspect_eval.md](docs/cli/inspect_eval.md)
- Provider setup: [docs/getting-started/inspect_agents_quickstart.md](docs/getting-started/inspect_agents_quickstart.md) and [docs/reference/environment.md](docs/reference/environment.md)

Policy note: Enabling `INSPECT_ENABLE_EXEC=1` exposes only single‑shot `bash()` and `python()` tools. The stateful `bash_session` tool is never surfaced by this repo’s `standard_tools()`; it is reserved for internal filesystem‑sandbox operations (e.g., `sed`, `ls`, `wc -c`).

## Viewing Logs (Inspect View)
Inspect provides a log viewer. See: [docs/cli/inspect_view.md](docs/cli/inspect_view.md)

<!-- Provider-specific CLI examples were removed to avoid stale or environment-sensitive commands here. See the docs site for up-to-date provider guidance. -->

## Advanced Usage

### Sub‑agents Configuration
Define sub‑agents in YAML and load programmatically. See: [docs/guides/subagents.md](docs/guides/subagents.md)

## Architecture

```mermaid
flowchart LR
    SP[[System Prompt / Config]] --> S[Supervisor]
    MR[Model Resolver] --> S
    S --> L[Logs / Traces]
    S -->|tool call| AP[Approvals & Policies]
    AP --> ST[Stateless Tools]
    AP --> SS[Stateful Tools]
    ST -.-> S
    SS -.-> S

    subgraph "FS Path Modes (MODE=store|sandbox)"
      direction LR
      FST[FS Tools] -->|"store (default)"|VFS["(VFS)"]
      FST -->|sandbox| SBX[["Sandboxed Editor (no delete)"]]
      SBX --> HFS[(Host FS)]
    end
    AP --> FST
    VFS -.-> S
    SBX -.-> S
    HFS -.-> S

    S -->|handoff| CG[Context Gate]
    CG <-->|iterate| SA[Sub-Agents]
    SA -.-> S
```

Fallback: `docs/diagrams/architecture_overview.png`

## Documentation
- Getting Started: [docs/getting-started/inspect_agents_quickstart.md](docs/getting-started/inspect_agents_quickstart.md)
- Tools Reference: [docs/tools/README.md](docs/tools/README.md)
- Filesystem & Sandbox: [docs/how-to/filesystem.md](docs/how-to/filesystem.md)
- Approvals: [docs/how-to/approvals.md](docs/how-to/approvals.md)
- Sub‑agent Patterns: [docs/guides/subagents.md](docs/guides/subagents.md)
- Examples: [examples/inspect/](examples/inspect/)
- Testing Guides (repo): [tests/README.md](tests/README.md)

### Docs (MkDocs)
To preview docs locally, see: [docs/README.md](docs/README.md)

## Project Status
- Version: 0.0.1 (repo) / see PyPI badge for latest
- Status: Beta
- Python: 3.11+ (tested on 3.12)
- Roadmap: [Milestones](https://github.com/cnm13ryan/inspect_agents/milestones) | [Projects](https://github.com/cnm13ryan/inspect_agents/projects)

### Coming Soon
- CI workflows (tests, lint, coverage) and release automation
- Expanded examples for web_browser and sandboxed exec
- Additional sub-agent templates (researcher, coder, editor)

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Quick Setup for Contributors
See CONTRIBUTING.md for up‑to‑date dev environment instructions.

## Support
- **Questions**: [GitHub Discussions](https://github.com/cnm13ryan/inspect_agents/discussions)
- **Bugs & Features**: Open an [Issue](https://github.com/cnm13ryan/inspect_agents/issues) with repro steps

## License & Acknowledgments
- Licensed under [MIT](LICENSE)
- Thanks to the Inspect-AI project and ecosystem
- Inspired by CLI-first DX from projects like Bun and Supabase
