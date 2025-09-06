# Examples Index

This repo’s examples are grouped by intent so you can quickly find the right entrypoint and avoid path confusion.

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
  - `examples/configs/research_supervisor.yaml` — YAML composition for the research supervisor.

## Quick Start

- Inspect CLI (tasks)
  - `uv run inspect eval examples/tasks/prompt_task.py -T prompt="Write a concise overview of LangGraph"`
  - `uv run inspect eval examples/tasks/iterative_task.py -T prompt="List repo files and propose a small refactor plan"`
  - YAML config: `uv run inspect eval examples/tasks/research_task.py -T config=examples/configs/research_supervisor.yaml -T prompt="Research topic..."`

- Python runners
  - `uv run python examples/runners/supervisor_runner.py "What is Inspect‑AI?"`
  - `uv run python examples/runners/research_runner.py --enable-web-search "Research LangGraph vs Inspect"`
  - `uv run python examples/runners/iterative_runner.py --time-limit 120 --max-steps 20 "List repo files and summarize"`
  - `uv run python examples/runners/profiled_runner.py --profile T1.H1.N1 "Curate arXiv papers by Quantinuum (2025)"`

- Demos
  - `uv run python examples/demos/simple_arch_demo.py --mode supervisor "Research topic..."`
  - `uv run python examples/demos/subagent_approvals_demo.py --preset dev`

## Notes

- Paths and imports: each runner/task sets `REPO_ROOT = Path(__file__).resolve().parents[2]` so local `src/` code is imported from this repo.
- Environment: runners/tasks load `.env` from the repo root and their own folder (if present). You can also pass `--env-file` to runners that support it or set `INSPECT_ENV_FILE`.
- Providers: defaults prefer local providers (e.g., Ollama/LM Studio). Override via CLI flags or env (see docs/reference/environment.md).

