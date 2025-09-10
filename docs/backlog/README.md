# Backlog Index

Last updated: 2025-09-10

Curated index of all items under `docs/backlog/`, grouped for quick navigation. This index is non‑destructive: it does not move or rename files to avoid breaking links. Use it to find the right TODO quickly.

## How To Use
- New item: add a `todo_feature_<short-name>.md` with sections: Context & Motivation, Implementation Guidance, Scope Definition, Success Criteria.
- Cross‑link related items and note overlaps (see “Overlaps” below) instead of duplicating content.
- Keep titles starting with `# TODO:` for consistency and scanability.

## Categories

Note on status:
- DONE items are retained below for traceability with pointers to code/tests.

### Iteration & Limits — feature set
- [Iterative Agent — Productive-Time Accounting (subtract provider retry/backoff)](./todo_feature_iterative_productive_time_accounting.md) — DONE.
- [Per‑Message Token Truncation (Token‑Aware Overflow Control)](./todo_feature_pruning_token_aware.md) — DONE.
- [Iterative Agent — Unified Global Tool‑Output Cap (explicit param + early config)](./todo_feature_iterative_tool_output_cap.md) — DONE.
- [Iterative Agent — In‑Loop Sample Limits Enforcement (message/token soft stop)](./todo_feature_iterative_limits_enforcement.md) — DONE.

### Docs Alignment — Iterative Agent & CLI
- [Iterative Reference — Add Supervisor Runner Subsection](./todo_docs_iterative_supervisor_subsection.md) — DONE.
- [Getting Started — Add Iterative Quick‑Start Card](./todo_docs_getting_started_iterative_card.md) — DONE.
- [Iterative Examples — Standardize at 300s/20 Steps](./todo_docs_iterative_budgets_300_20_standard.md) — DONE.
- [Iterative Reference — Add CLI Quick‑Reference Table](./todo_docs_iterative_quick_reference_table.md) — DONE.
- [Iterative Reference — Add “See Also” Backlinks](./todo_docs_iterative_see_also_links.md) — DONE.
- [Iterative Reference — Add `INSPECT_MAX_TOOL_OUTPUT` Example Invocation](./todo_docs_iterative_output_cap_example.md) — DONE.

### Approvals & Handoffs (ADR‑0005) — sorted by name
- [Apply Exclusivity in CI for the Research Runner](./todo_ci_exclusivity_research_runner.md) — DONE.
- [Approvals Presets — Add Handoff Exclusivity by Default (dev/prod)](./todo_feature_approvals_handoff_exclusivity_default.md) — DONE.
- [Research Runner — Apply Handoff Exclusivity in CI](./todo_feature_runner_ci_exclusive.md) — DONE.
- [Transcripts — Standardized “Skipped Due to Handoff” ToolEvent](./todo_feature_transcript_skipped_tool_event.md) — DONE.
- [Side‑Effect Helper — Approval‑Aware Fallback Policy](./todo_policy_migration_approvals_fallback.md)

### Config & YAML — sorted by name
- [Model Roles Map — Implementation Checklists](./TODO-model-roles-map.md)
- [YAML Config — Add Role Mapping for Sub‑Agents](./todo_feature_yaml_subagent_role_mapping.md) — DONE.
- [YAML Limits — Parse and Return Inspect Limits](./todo_feature_yaml_limits_parser.md) — DONE.

### Filesystem Sandbox (ADR‑0004) — sorted by name
- [Filesystem Sandbox — Enforce Read‑Only Mode Flag](./todo_feature_fs_readonly_flag.md) — DONE.
- [Docs Adjustments — Supervisor Tool Exposure & ADR 0004 Baseline](./todo_feature_readme_docs_updates.md)
- [Docs — Add FS Design Note Backlink](./todo_docs_fs_design_note_backlink.md) — DONE.
- [Sandbox — Best Practices Feature Set (Epic: profiles, provider hardening, FS ops, audits)](./todo_features_sandbox_best_practices.md)

### Iterative Agent & Pruning — sorted by name
- [Iterative Agent — `code_only` Flag](./todo_feature_iterative_code_only.md)
- [Iterative Agent — Env Fallbacks for Time/Steps](./todo_feature_iterative_env_fallbacks.md) — DONE.
- [Iterative Agent — Add `max_messages`](./todo_feature_iterative_max_messages.md) — DONE.
- [Conversation Pruning — Env Toggles + Optional Debug Log](./todo_feature_pruning_env_toggles.md)
- [Per‑Message Token Truncation (Token‑Aware Overflow Control)](./todo_feature_pruning_token_aware.md) — DONE.
- [Iterative Task (Inspect) — `enable_web_search` Flag](./todo_feature_iterative_task_web_search_flag.md)

### Eval Logs Tooling (`scripts/read_log_eval.py`) — sorted by name
- [Summary Stats and `summary.json`](./todo_feature_read_log_eval_summary.md)
- [`--out-dir` and Sidecar Mode](./todo_feature_read_log_eval_out_dir.md)
- [JSONL/Parquet Export Options](./todo_feature_read_log_eval_formats.md)
- [Log Selection Filters](./todo_feature_read_log_eval_filters.md)

### Retries & Cache — sorted by name
- [Retry Policy — Feature](./todo_feature_retry_policy.md)
- [Retry/Cache Tests — Feature](./todo_feature_retry_cache_tests.md)
- [Cache Policy — Feature](./todo_feature_cache_policy.md)

### Epics & Misc
- [Rewrite Epic](./rewrite/README.md)
- [General Todos](./todos/README.md)

### Refactors — Code Health
- [tools.py — Migrate FS Helpers to `inspect_agents.fs`](./todo_feature_tools_py_migrate_fs_helpers.md)

### Migration Helper — Side‑Effects
- [Add Debug Logs + Tests](./todo_feature_migration_helper_debug_logging.md)
- [Approval‑Aware Fallback Policy](./todo_policy_migration_approvals_fallback.md)
- [Skip Fallback on Success (Idempotency)](./todo_feature_migration_idempotency_check.md)
- [Instance Scoping for Store Models](./todo_feature_migration_instance_scoping.md)
- [Enforce Size Caps on Fallback Writes](./todo_limits_migration_fallback_size_caps.md)
- [Tests — Edge Cases Coverage](./todo_tests_side_effect_helper_extensions.md)

### Providers & Models — Resolver Diagnostics
- [Implement `resolve_model_explain(...)`](./todo_feature_model_resolver_explain_api.md) — DONE.
- [Typed Error with `.explain`](./todo_feature_model_resolver_error_type.md) — DONE.
- [Stabilize `path` Labels Contract](./todo_api_model_resolver_path_labels_contract.md)
- [Explicit Sentinel Handling for `INSPECT_EVAL_MODEL=none/none`](./todo_feature_model_resolver_env_sentinel_none_none.md)
- [Tests — Explain/Precedence Coverage](./todo_tests_model_explain_coverage.md) — DONE.
- [Docs — Debugging Model Resolution How‑To](./todo_docs_model_resolution_debugging_howto.md) — DONE (see `docs/how-to/model_resolver_explain.md`).

### Settings & Env Centralization
- [Iterative Helpers — Wrap `settings.int_env`](./todo_settings_iterative_wrappers.md)
- [Add `settings.max_tool_output_env()` Accessor](./todo_settings_max_tool_output_accessor.md)
- [Tests — Unit Coverage for settings.py](./todo_tests_settings_unit.md)
- [Docs — Add “Environment & Settings API” Section](./todo_docs_environment_settings_api_section.md)
- [Deprecations — Gate Alias Warnings Behind `INSPECT_SHOW_DEPRECATIONS`](./todo_deprecations_alias_warnings_flag.md)

### Bugs & Fixes — new
- [run_agent: mutable default for limits](./todo_bug_run_mutable_limits_default.md) — DONE.
- [delete (sandbox): unify error code/message with docs](./todo_docs_delete_sandbox_error_alignment.md) — DONE.
- [read_file numbering: make sandbox/store formatting consistent](./todo_docs_read_file_line_numbering.md) — DONE.

### Tests & Coverage — new
- [Observability: one‑time effective tool‑output limit log precedence + log‑once](./todo_obs_effective_tool_output_limit_tests.md)
- [Model resolver: precedence + sentinel env cases](./todo_tests_model_resolver_precedence.md)
- [Filters: default_input_filter cascade/inherit + scoped summary caps](./todo_tests_filters_quarantine_inherit.md)
- [Iterative: pruning/truncation behaviors (overflow hint, keep_first/last, token cap)](./todo_tests_iterative_prune_truncate.md)
- [Settings: direct unit tests for helpers](./todo_tests_settings_unit.md)
- [Migration helper: edge cases/approvals/idempotency](./todo_tests_side_effect_helper_extensions.md)

### CI — Docs Only
- [Add docs‑only workflow job (unit subset + link checker)](./todo_ci_docs_only_job.md)

### Docs Alignment — new
- [YAML limits schema and examples: align docs with current parser](./todo_feature_yaml_limits_parser.md)
- [Filesystem read‑only: expand docs and examples across how‑to + env ref](./todo_docs_fs_read_only_alignment.md)
- [Add CHANGELOG and release notes automation (Release Drafter)](./todo_docs_changelog_template_release_drafter.md)

## Overlaps / Duplicates
- CI exclusivity for the research runner is tracked in both:
  - `todo_feature_runner_ci_exclusive.md` and
  - `todo_ci_exclusivity_research_runner.md` (older, includes checklist/status).
  Prefer the `todo_feature_…` file for new work; link or consolidate later when convenient.

## Conventions
- File naming: `todo_feature_<area>_<topic>.md`; epics in subfolders.
- Title: start with `# TODO:` followed by a crisp scope.
- Sections: Context & Motivation, Implementation Guidance, Scope Definition, Success Criteria.
- Status/Owner: optional at the end of the file.
