# Tell me in detail how to document environment variables and environmental flags, according to best practices.


**Goal & scope (assumptions + success criteria)**
You want a practical, durable way to *document* configuration that comes in via **environment variables** and **command‑line flags** (I’ll call these “CLI flags”). I’ll assume: cross‑platform software (Linux/macOS/Windows), modern packaging/containers, and a mixed audience (operators + developers). “Good” looks like: readers can discover every knob in one place, know the exact name, type, default, precedence, examples, and security caveats—and the docs stay in sync with the code.

---

## 1) What to write for **each environment variable**

Document each variable as a small, predictable record. Use this schema (keep the field order stable):

```yaml
# one entry per variable
name: APP_DB_TIMEOUT
aliases: []                # other accepted names, if any
type: duration             # {string|int|float|bool|enum|duration|size|path|url}
required: false
default: "30s"             # literal default as the program sees it
allowed: ["5s".."5m"]      # range or enum values
description: >
  Max time to wait for DB connection establishment.
example: APP_DB_TIMEOUT=45s
source: env                # "env" / "flag" / "config-file" (for cross-ref)
since: 1.8.0               # version it first appeared
deprecated: false          # or {true, "Use APP_DB_CONNECT_TIMEOUT"}
sensitive: false           # true for secrets; add handling guidance below
scope: process             # {process|node|cluster}
hot_reload: false          # applies without restart?
restart_required: true
interactions:
  - "Ignored if APP_DB_DISABLED=true."
notes:
  - "Units: Go-style duration (ns, us, ms, s, m, h)."
```

**Naming & characters.** For portability across standard utilities, prefer UPPER\_SNAKE\_CASE, starting with a letter or underscore; avoid starting with a digit. POSIX specifies that names consist of letters, digits, and underscore, and *do not begin with a digit* (other characters may exist on some systems but aren’t portable). ([pubs.opengroup.org][1])

**What to include in the prose:**

* **What it does** (plain English, one sentence).
* **Type + units** (e.g., “duration like `30s` or `2m`”).
* **Default** (exact literal).
* **Allowed values** (range or enum).
* **Examples** (set and unset, cross‑platform if needed).
* **Security**: mark `sensitive: true` for things like tokens/passwords and add “do not log; prefer secret manager; rotate” guidance. OWASP warns that env vars are widely readable in processes and can leak via logs/dumps; recommend secrets managers or mounted files when possible. ([OWASP Cheat Sheet Series][2])

**When the value takes effect.** Call out **reload behavior**: “read once at start,” “re-read on SIGHUP,” etc. (pair this with an operational note like “requires restart”).

**Interdependencies.** Note conflicts (“ignored if `APP_MODE=offline`”) and precedence relative to flags (see §4).

**Containers & OS specifics.** If your users deploy with Kubernetes, link to the pattern they’ll use (env, ConfigMap, or Secret; and, when it’s sensitive, advise a Secret with at‑rest encryption). For systemd‑launched services, mention `Environment`/`EnvironmentFile=` and that those files are not shell scripts (no expansion). ([Kubernetes][3], [Freedesktop][4], [Unix & Linux Stack Exchange][5])

---

## 2) What to write for **each CLI flag**

Use a mirror schema so readers can line things up:

```yaml
flag: --db-timeout
short: -t                   # optional
type: duration
default: "30s"
required: false
allowed: ["5s".."5m"]
description: "Max time to wait for DB connection."
env_var: APP_DB_TIMEOUT     # cross-link for precedence
since: 1.8.0
deprecated: false           # or {true, "Use --db-connect-timeout"}
repeatable: false
conflicts_with: ["--offline"]
```

**Option syntax conventions.** Follow POSIX utility conventions for short options (`-t`, clusterable like `-abc`) and offer long options with `--db-timeout` (GNU extension; not POSIX) for readability. Document both in `--help` and man pages; keep option arguments separate (e.g., `-t 30s` or `--db-timeout=30s`). ([pubs.opengroup.org][6], [GNU][7])

**Help/man conventions.** In man pages and `--help`, use the standard SYNOPSIS notation: brackets for optional `[]`, vertical bar for choice `|`, and ellipsis for repetition `...`. Put semantics under **OPTIONS** with one flag per line. ([man7.org][8])

**Booleans.** Prefer positive flags plus an inverted form (e.g., `--feature` and `--no-feature`) or a tri‑state with clear defaults in docs. (Long options with `--no-…` are common in modern CLIs; keep the default explicit in the description.) GNU and contemporary CLI guidelines favor readable long options; short forms are for speed. ([GNU][7])

---

## 3) **Where** to put the documentation (and how to structure it)

* **Single “Configuration Reference” page** that lists *every* env var and flag, grouped by domain (e.g., “Database,” “HTTP,” “Auth”), sorted alphabetically within a group.
* **CLI Reference** (generated) that shows `--help` for each command/subcommand, matching man‑page conventions. ([man7.org][8])
* **Quick start** shows a minimal, copy‑paste `.env` (non‑secret defaults) and one full command using flags.
* **Operations guide** covers reload/restart semantics, precedence, and secret‑handling.

For containers, include a short “How to set this in Docker Compose/Kubernetes/systemd” appendix with tiny examples, and link to the upstream docs so the behavior (e.g., precedence of `env`, `env_file`, `--env`) isn’t ambiguous. ([Docker Documentation][9])

---

## 4) **Precedence & layering** (make this unmissable)

State one clear order and stick to it everywhere (docs, code, examples). A widely adopted pattern is:

```
CLI flags  >  environment variables  >  config file(s)  >  defaults
```

Call this out in the reference page and per‑setting when needed. As a concrete example, Go’s `viper` documents essentially this precedence (with library specifics above/below), which many teams emulate; it’s familiar to operators and predictable in CI. ([GitHub][10], [Cobra][11])

Also document **where conflicts are resolved** (“last source wins”), and show one example resolving an intentional conflict (e.g., env sets `APP_PORT=8080` but `--port 9090` wins).

---

## 5) **Security & secrets** (what to say, every time)

* **Mark sensitive items** and show the safe pattern for each platform (e.g., “Kubernetes: use a Secret mounted as a file; app reads from path X”). Kubernetes explicitly supports referencing secrets either as env vars or mounted files; prefer the latter when you want narrower exposure and easier rotation. ([Kubernetes][3])
* **Warn about leakage paths**: env dumps in crash reports, debug logs, and process inspection. OWASP’s Secrets Management Cheat Sheet recommends avoiding environment variables for secrets when better options exist (secret stores, short‑lived injectors, etc.). ([OWASP Cheat Sheet Series][2])
* **Never show real secrets** in examples; use obvious placeholders and add “not logged” notes near logging options.

---

## 6) **Conventions & style guide**

* **Env var names**: `APP_*`, all caps, underscore separators; don’t start with a digit; keep ≤ 30 chars if possible. The POSIX portability rule is your safety net. ([pubs.opengroup.org][1])
* **Flag names**: `--kebab-case` long options, optional single‑letter short alias where it genuinely helps. Follow POSIX clustering (`-abc`) and show `--long=value` *and* `--long value` examples. ([pubs.opengroup.org][6])
* **Types & units**: standardize (durations, sizes, log levels). Define the grammar once and point to it from each entry.
* **Deprecations**: add “Deprecated since X.Y; removed in Z. Use …” and keep a removal calendar.
* **Internationalization**: config keys/flags are ASCII; descriptions localized if you localize docs.

---

## 7) **Examples to include**

* A **minimal `.env`** (non‑secret) and a **full `.env.example`** with every key commented.
* A **one‑liner** for each common platform:

  * Kubernetes: small Pod/Deployment snippet showing `env` and an example Secret volume mount. ([Kubernetes][12])
  * Docker Compose: `env_file:` vs `environment:` and a note on precedence. ([Docker Documentation][9])
  * systemd: `Environment=` and `EnvironmentFile=` with a link to the `systemd.exec` docs; note that environment files are *not shell scripts*. ([Freedesktop][4], [Unix & Linux Stack Exchange][5])

---

## 8) **Automation: keep docs in sync**

**Source of truth.** Put the schema above in code (annotations/struct tags) or a single YAML/JSON in the repo. Generate:

* the **reference page** (Markdown/HTML),
* the **`.env.example`**,
* and **man/`--help`** stubs (if your CLI library can emit them).

**Minimal pseudocode** for a generator:

```
load config_spec.yaml
for each entry:
  validate fields (name matches ^[A-Z_][A-Z0-9_]*$, allowed vs type, default ∈ allowed)
  render Markdown row + examples
  if sensitive: add “Secret handling” callout
emit "configuration.md", ".env.example", "flags.md"
```

**Tests**: run a CI check that parses the binary’s `--help` and fails if any known flag is missing from `flags.md`; run a static scan of the codebase for `os.Getenv("...")`/equivalents and fail if any name isn’t present in the spec.

---

## 9) **Acceptance checklist** (use this to review the docs)

| Test                       | Pass criteria                                                                                                                                                       |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Every variable/flag listed | A machine‑readable index exists; generator shows zero “undocumented” items.                                                                                         |
| Precedence is unambiguous  | One table or paragraph that states “flags > env > file > defaults,” with one conflict example. ([GitHub][10])                                                       |
| Types & units consistent   | A single “Types & Units” section is referenced by all entries.                                                                                                      |
| Security marked            | All sensitive items have `sensitive: true` and platform‑specific handling guidance. ([OWASP Cheat Sheet Series][2], [Kubernetes][3])                                |
| Help/man parity            | `--help` output matches the reference; SYNOPSIS/OPTIONS follow man‑page conventions. ([man7.org][8])                                                                |
| Platform examples          | Each platform snippet runs as‑is (K8s, Compose, systemd) and links upstream docs for edge behavior. ([Kubernetes][12], [Docker Documentation][9], [Freedesktop][4]) |

---

## 10) **Common pitfalls to call out (so readers don’t trip)**

* **Silent type coercion.** Say exactly what happens on bad input (e.g., “non‑parsable duration falls back to default and logs a warning”).
* **Hidden defaults.** If a default differs by environment (dev/prod), say so explicitly.
* **Secrets in env.** If your project *must* use env vars for secrets, document the blast radius (access by child processes, core dumps, diagnostics) and link to mitigations. ([OWASP Cheat Sheet Series][2])
* **Long options ≠ POSIX.** Don’t call `--long` “POSIX”; it’s a GNU extension (still fine to use, just label it correctly). ([GNU][7])

---

## 11) **Tiny reference examples**

**Man‑style SYNOPSIS (for an “ingest” subcommand):**

```
ingest [--db-timeout DURATION] [--log-level LEVEL] [--dry-run] SOURCE...
```

(Brackets = optional; `...` = repeatable; expanded in OPTIONS.) ([man7.org][8])

**Kubernetes Secret mounted as a file (safer for secrets than env):**

```yaml
volumes:
- name: api-key
  secret: { secretName: my-api-key }
containers:
- name: app
  volumeMounts:
  - name: api-key
    mountPath: /run/secret
    readOnly: true
  env:
  - name: APP_API_KEY_FILE
    value: /run/secret/key
```

Docs should state “app reads `APP_API_KEY_FILE` if set; prefer this over `APP_API_KEY` when possible.” ([Kubernetes][3])

**Docker Compose precedence note** (example in docs): “Values from `--env` override `environment:` and `env_file:`; host env can override `.env` interpolations.” Link to Compose’s precedence page. ([Docker Documentation][13])

---

### Evidence pointers (why these norms?)

* **Store config in the environment** is the classic Twelve‑Factor recommendation (still useful context, even if you blend with files/flags). ([12factor.net][14])
* **Secrets**: OWASP cautions against env vars for secrets due to process/log exposure; recommend secret stores or mounted files. ([OWASP Cheat Sheet Series][2])
* **Portability of names**: POSIX rules on environment variable names and SYNOPSIS/OPTIONS conventions for man pages. ([pubs.opengroup.org][1], [man7.org][8])
* **CLI syntax**: POSIX utility conventions for short options; GNU notes that long `--option` is a GNU extension (document it as such). ([pubs.opengroup.org][6], [GNU][7])
* **Precedence**: Many ecosystems document a clear order; `viper`’s commonly used order is a good anchor to cite. ([GitHub][10])

---

## Brief plan → step → progress (so this is actionable)

**Plan.**

1. Adopt the schemas above in code or `config_spec.yaml`.
2. Generate reference docs + `.env.example` + `--help` parity tests.
3. Add platform appendices (K8s, Compose, systemd) with links.
4. Gate releases on the acceptance checklist.

**First step you can run today.**
Create `config_spec.yaml` for just one domain (e.g., “Database”) with 3–5 entries and wire a tiny script to emit a Markdown table. That gives you the rhythm and shows drift immediately.

**Progress gauge.**

* You have a single index of settings.
* CI fails if docs and code diverge.
* Operators can answer “what wins?” in 5 seconds.

---

### Running log (decisions I made for you)

* Assumed cross‑platform + containers; chose a single schema for both env and flags to reduce cognitive load.
* Anchored naming, SYNOPSIS, and option behavior in POSIX/GNU/man‑page sources; anchored “config in env” in 12‑Factor while balancing with OWASP on secrets. ([12factor.net][14], [OWASP Cheat Sheet Series][2], [pubs.opengroup.org][1], [GNU][7], [man7.org][8])
* Picked the common precedence order and cited a well‑known library (`viper`) to keep expectations familiar. ([GitHub][10])

If you want, I can turn this into a repo‑ready starter: a `config_spec.yaml`, a tiny generator, and a doc template you can drop into your project.

[1]: https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap08.html?utm_source=chatgpt.com "Environment Variables"
[2]: https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html?utm_source=chatgpt.com "Secrets Management Cheat Sheet"
[3]: https://kubernetes.io/docs/concepts/configuration/secret/?utm_source=chatgpt.com "Secrets"
[4]: https://www.freedesktop.org/software/systemd/man/systemd.exec.html?utm_source=chatgpt.com "systemd.exec"
[5]: https://unix.stackexchange.com/questions/358998/systemd-environmentfile-re-using-variables-how?utm_source=chatgpt.com "systemd, EnvironmentFile, re-using variables"
[6]: https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap12.html?utm_source=chatgpt.com "12. Utility Conventions"
[7]: https://www.gnu.org/prep/standards/html_node/Command_002dLine-Interfaces.html?utm_source=chatgpt.com "Command-Line Interfaces (GNU Coding Standards)"
[8]: https://man7.org/linux/man-pages/man7/man-pages.7.html?utm_source=chatgpt.com "man-pages(7) - Linux manual page"
[9]: https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/?utm_source=chatgpt.com "Set environment variables"
[10]: https://github.com/spf13/viper?utm_source=chatgpt.com "spf13/viper: Go configuration with fangs"
[11]: https://cobra.dev/docs/tutorials/12-factor-app/?utm_source=chatgpt.com "Building a 12-Factor App with Viper Integration"
[12]: https://kubernetes.io/docs/tasks/inject-data-application/define-environment-variable-container/?utm_source=chatgpt.com "Define Environment Variables for a Container"
[13]: https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/?utm_source=chatgpt.com "Environment variables precedence in Docker Compose"
[14]: https://12factor.net/config?utm_source=chatgpt.com "Store config in the environment"
