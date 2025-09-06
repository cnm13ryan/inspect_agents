# Inspect Agents Documentation

Welcome to the unified documentation site for Inspect Agents. This site collects all project docs under `docs/` and presents them with MkDocs.

## Quick Links

- Getting Started: [Inspect Agents Quickstart](getting-started/inspect_agents_quickstart.md)
- Cheat Sheet: [Inspect Console](getting-started/inspect_console_cheatsheet.md)
- How-To Guides: [Approvals](how-to/approvals.md), [Filesystem](how-to/filesystem.md)
- Guides: [Sub‑agents](guides/subagents.md), [Retries & Cache](guides/retries_cache.md), [Supervisor Limits](guides/supervisor-limits.md)
- Tools Reference: [Index](tools/README.md)
- Reference: [Environment Variables](reference/environment.md)
- Architecture: [Overview](ARCHITECTURE.md)
- ADRs: [Index](adr/README.md)
- Open Questions: [Discussion Topics](design/open-questions.md)
- Examples: Simple Architecture Demo — `examples/demos/simple_arch_demo.py`

For a fuller section-by-section map of all docs, see the in-repo index at [docs/DOCS_INDEX.md](DOCS_INDEX.md). The Simple Architecture shown in the diagram is conceptual; see the example under `examples/demos/` for a runnable demo that composes only public APIs (agent builders, approvals, tools).

## Acknowledgments

The iterative agent approach described in examples (`examples/tasks/` and `examples/runners/`), reference guides, and the `src/inspect_agents/` implementation draws inspiration from the PaperBench project on iterative multi‑step agent evaluation. See: PaperBench — https://arxiv.org/abs/2504.01848.
