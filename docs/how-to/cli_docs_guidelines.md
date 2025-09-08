---
title: Documenting Large CLIs — Grouping, Constraints, and Clear Help
description: Practical patterns to structure, name, and document many commands/flags without enumerating every permutation.
---

This guide shows how to organize and document a large command‑line surface area (many subcommands and flags) so users can discover capabilities without wading through a combinatorial explosion of permutations.

Who this is for
- Engineers adding or evolving commands in this repo.
- Doc writers maintaining CLI pages and examples.

Outcomes
- A predictable command tree, consistent flag taxonomy, and readable help.
- Documentation that explains usage patterns and constraints instead of listing every possible combination.

## Organize the Command Tree

- Prefer a shallow hierarchy: root → resource → action. Group by user intent/domain, not internal modules.
- Promote only truly global options to the root; keep everything else at the subcommand where it applies (see Cobra’s guidance on persistent vs local flags and large CLI trees). [Cobra enterprise guide](https://cobra.dev/docs/explanations/enterprise-guide/), [Cobra flags](https://cobra.dev/docs/how-to-guides/working-with-flags/).
- For complex "modes" (mutually exclusive behaviors), expose them as subcommands or document multiple synopsis lines rather than one giant line. citeturn0search3

## Flag Taxonomy and Behavior

Classify flags and keep behavior consistent:
- Global (persistent across the tree): e.g., provider/model selection.
- Command‑local: relevant only to a specific subcommand.
- Mode switches: mutually exclusive; document and enforce exclusivity.

Implementation tips (argparse)
- Use `mutually_exclusive_group()` for exclusive flags; validate "required‑together" sets manually.
- Keep boolean flags positive (e.g., `--verbose`) and, when supported, also accept `--no-verbose`. Example: Google Cloud’s `gcloud` documents `--no-` variants. <https://cloud.google.com/sdk/gcloud/reference/alpha/topic/command-conventions>
- Follow standard CLI conventions: short `-v`, long `--verbose`, `--` ends options, options precede operands (POSIX utility conventions). <https://pubs.opengroup.org/onlinepubs/9699919799.2018edition/xrat/V4_xbd_chap12.html>

Naming
- Reuse industry‑standard names (`--help`, `--version`, `--output`, `--verbose`); avoid near‑synonyms for common actions (GNU standards). <https://www.gnu.org/prep/standards/html_node/Command_002dLine-Interfaces.html>
- Decide and document how repeated flags resolve (e.g., "rightmost wins" as in gcloud). <https://cloud.google.com/sdk/gcloud/reference/alpha/topic/command-conventions>

Security
- Don’t pass secrets as flags; prefer env vars or files/stdin. <https://clig.dev/>

## Environment and Config Precedence

Document a clear, single precedence chain and keep help in sync:

CLI flag > environment variable > config file > default.

Reflect env names in help (UPPER_SNAKE_CASE), and avoid surprising overrides. This mirrors mature CLIs and keeps scripting predictable. <https://clig.dev/>

## Output, Stability, and Scripting

- Provide stable machine‑readable modes (`--output=json|yaml`) and avoid mixing human/UI text with JSON. <https://kubernetes.io/docs/reference/kubectl/conventions/>
- Define exit codes and avoid using stdout for errors (send to stderr). <https://www.gnu.org/prep/standards/html_node/Command_002dLine-Interfaces.html>
- Deprecate rather than remove: mark flags as deprecated in help, provide replacements, and publish timelines; hide after the window closes. <https://cobra.dev/docs/how-to-guides/working-with-flags/>

## Help Page Structure (Man‑page Style)

Use predictable sections so users can scan quickly:

1) NAME — one‑line summary
2) SYNOPSIS — show patterns, not permutations
3) DESCRIPTION — what and when to use
4) OPTIONS — grouped by domain (see below)
5) EXIT STATUS — codes and meanings
6) ENVIRONMENT — relevant variables and precedence
7) FILES — config/outputs
8) EXAMPLES — 3–5 realistic invocations
9) SEE ALSO — related commands

This mirrors man‑page and large‑CLI conventions. <https://man7.org/linux/man-pages/man7/man-pages.7.html>

### Writing the SYNOPSIS (avoid the combinatorial trap)

Prefer several short synopsis lines to convey exclusivity and optionality:

```
mycmd resource action [--global-options] --mode=A [opts] [--] [ARGS...]
mycmd resource action [--global-options] --mode=B [opts] [--] [ARGS...]
```

Use `( --foo | --bar )` for mutually exclusive sets and `[ --opt ]` for optional flags. Do not enumerate all value combinations. <https://pubs.opengroup.org/onlinepubs/9699919799.2018edition/xrat/V4_xbd_chap12.html> • <https://docopt.org/>

### Group Options by Domain

Split OPTIONS into logical groups for scanning:
- Model selection: `--provider`, `--model`.
- Tools and capabilities: `--enable-*` toggles.
- Execution limits: `--time-limit`, `--max-steps`.
- Logging and paths: `--log-dir`, outputs.

Large CLIs (e.g., Azure CLI) use grouped options and topic pages to keep pages short and task‑oriented. <https://github.com/Azure/azure-cli/blob/dev/doc/reference_doc_guidelines.md>

## Patterns to Compress Complexity

- Publish "profiles" instead of axes. Example: the T/H/N profiles in this repo bundle multiple flags into named presets; document the mapping once and refer to it from recipes. (Analogy: kubectl uses conventions and consistent patterns rather than listing all combinations.) <https://kubernetes.io/docs/reference/kubectl/conventions/>
- Provide small matrices only when they add value (e.g., which flags apply to which subcommands), not full Cartesian products.
- Curate 5–8 common tasks with canonical commands; link advanced users to the full OPTIONS.

## Authoring Checklist (per command)

- [ ] Clear description and when to use it.
- [ ] Multiple SYNOPSIS lines showing modes/exclusivity.
- [ ] OPTIONS grouped by domain; defaults and env aliases documented.
- [ ] Constraints box: mutually exclusive sets; required‑together sets.
- [ ] 3–5 realistic EXAMPLES (copy‑paste‑ready, no permutations).
- [ ] Exit codes defined; machine‑readable output documented (if any).
- [ ] Deprecations and aliases (if any) listed with timelines.

## Template Snippets

Synopsis patterns

```
examples <subcommand> [GLOBAL] [OPTS] <ARGS>
examples iterative [--provider P] [--model M] [--time-limit S] [--max-steps N] [--enable-*] -- [PROMPT]
examples research [--approval (dev|ci|prod)] [--config FILE] [COMMON]
```

Constraints block

```
Constraints
- Exactly one of: --mode=supervisor | --mode=iterative
- Required together: --config FILE and --approval=prod (example)
- Precedence: CLI > ENV > config > default
```

Examples section

```
# Iterative with a 2‑minute budget
python -m examples iterative --time-limit 120 --max-steps 20 "List files and summarize"

# Research with approvals and YAML config
python -m examples research --approval dev --config examples/configs/research/exploration.yaml \
  "Compare Inspect‑AI and LangGraph"
```

## References

- POSIX Utility Conventions and Argument Syntax: <https://pubs.opengroup.org/onlinepubs/9699919799.2018edition/xrat/V4_xbd_chap12.html>
- GNU Coding Standards — Command‑Line Interfaces: <https://www.gnu.org/prep/standards/html_node/Command_002dLine-Interfaces.html>
- Command Line Interface Guidelines (clig.dev): <https://clig.dev/>
- Google Cloud CLI — Command Conventions: <https://cloud.google.com/sdk/gcloud/reference/alpha/topic/command-conventions>
- Kubernetes — kubectl Usage Conventions: <https://kubernetes.io/docs/reference/kubectl/conventions/>
- Cobra (Go) — Enterprise Guide and Flags: <https://cobra.dev/docs/explanations/enterprise-guide/>, <https://cobra.dev/docs/how-to-guides/working-with-flags/>
- man‑pages(7) — Manual Page Structure: <https://man7.org/linux/man-pages/man7/man-pages.7.html>
- docopt — usage patterns and synopsis style: <https://docopt.org/>
