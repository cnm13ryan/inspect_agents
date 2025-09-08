# Improving `inspect_agents` MkDocs site (2023‑2025 best practices)

## A) Executive summary --- prioritized actions (effort vs. impact)

| Change | Effort | Impact | Rationale |
|--------|--------|--------|-----------|
| **Adopt Diátaxis information architecture**: reorganize pages into tutorials (step‑by‑step examples), how‑to guides (task recipes), reference (CLI/API docs), and explanations (conceptual/ADR/design docs). Rename or move existing sections accordingly and provide redirects. | M | H | The Diátaxis framework emphasizes clear separation between four doc types; mixing them reduces findability and user trust. Official guidance states that tutorials teach by leading users through a process, how‑to guides help achieve goals, reference is factual, and explanation covers underlying concepts[[1]](https://diataxis.fr/start-here/#:~:text=The%20four%20kinds%20of%20documentation%C2%B6). Aligning with this structure improves navigation and search. |
| **Revise navigation**: flatten nav to ≤2 levels, use concise titles, enable Material's breadcrumb (`navigation.path`) and index pages (`navigation.indexes`), split long pages, and craft unique H1 titles. | M | H | Flat navigation helps users scan and orient themselves. Material's `navigation.path` adds breadcrumbs and `navigation.indexes` creates index pages for sections[[2]](https://squidfunk.github.io/mkdocs-material/setup/setting-up-navigation/#:~:text=Navigation%20path%20Breadcrumbs%C2%B6). Google/Microsoft style guides emphasise scannable headings and sentence‑case titles[[3]](https://developers.google.com/style/headings#:~:text=Use%20sentence%20case%20for%20headings,headings%20and%20titles%20are%20unique)[[4]](https://learn.microsoft.com/en-us/style-guide/scannable-content/headings#:~:text=Headings%20provide%20both%20structure%20and,content%20and%20find%20entry%20points). |
| **Redesign the homepage**: include a hero with the mission/value proposition, a quickstart box linking to the main tutorial, role‑ or goal‑based cards (e.g., "Run your first evaluation", "Integrate the CLI"), and a "Next steps" section pointing to tutorials, reference and community links. | M | H | Exemplary dev doc home pages (e.g., GitHub docs) highlight a clear value proposition, search bar, quickstart path, and category cards[[5]](https://docs.github.com/en#:~:text=GitHub%20Docs). This guides newcomers and reduces friction. |
| **Introduce versioning and release history using** `mike`: add the `mkdocs‑mike` plugin and set up `extra.version.provider: mike` so readers can switch between versions; use a `latest` alias; maintain older versions on GitHub Pages. | M | M | The Material docs note that `mike` maintains separate directories per version and allows a version switcher[[6]](https://squidfunk.github.io/mkdocs-material/setup/setting-up-versioning/#:~:text=to%20MkDocs%2C%20i,of%20your%20documentation%20remain%20untouched). This is critical as the project evolves and APIs change. |
| **Improve CLI and API documentation**: generate CLI docs from the code using `mkdocs-click` (if CLI uses Click) or `mkdocs-typer2` for Typer. Use `mkdocstrings` for Python API reference. Provide short examples for each command and cross‑link to guides. | S | H | Auto‑generating CLI docs reduces drift; the `mkdocs-click` and `mkdocs-typer2` plugins build interactive docs from Click or Typer commands[[7]](https://pypi.org/project/mkdocs-click/0.1.1/#:~:text=Quickstart)[[8]](https://syn54x.github.io/mkdocs-typer2/#:~:text=A%20MkDocs%20plugin%20that%20automatically,for%20your%20Typer%20CLI%20applications). |
| **Enhance performance and UX**: add `mkdocs-minify-plugin` or `mkdocs-minify-html-plugin` to minify HTML/JS/CSS, enable the built‑in search tuning (boost important pages, exclude noise), configure `mkdocs-glightbox` for image lightboxes, and enable content tabs, code copy buttons and `navigation.instant` for faster page loads. | S | M | Minification reduces payload sizes; Material supports minification via the minify plugin[[9]](https://sm-26.github.io/SWM-Wiki/plugins/minify-html/#:~:text=Minify%20HTML%C2%B6). `glightbox` provides a better image viewing experience[[10]](https://pypi.org/project/mkdocs-glightbox/#:~:text=1,1). Search boosting and exclusion options help surface relevant results[[11]](https://squidfunk.github.io/mkdocs-material/setup/setting-up-site-search/#:~:text=Search%20boosting%C2%B6)[[12]](https://squidfunk.github.io/mkdocs-material/setup/setting-up-site-search/#:~:text=Search%20exclusion%C2%B6). |
| **Add Git revision dates**: use `mkdocs-git-revision-date-localized-plugin` to display "Last updated on" in page footers, with localization/timezone options[[13]](https://timvink.github.io/mkdocs-git-revision-date-localized-plugin/options/#:~:text=Options). | S | M | Communicating freshness builds trust. |
| **Improve authoring workflow**: adopt docs-as-code practices (Vale/markdownlint for style and spelling, code snippet inclusion via `mkdocs-include-markdown-plugin` and `mkdocs-gen-files`), PR previews via GitHub Pages environments, and internal link checks in CI. Move external link checks to scheduled nightly jobs to keep PR builds under 5 minutes. | M | M | Shorter PR cycles increase contributor happiness; snippet inclusion ensures code samples never drift. |
| **Accessibility & SEO**: enforce alt text on images, keyboard navigability, descriptive page titles, canonical URLs, sitemaps, and Open Graph metadata. Ensure high color contrast and use ARIA labels. | S | H | Accessibility guidelines such as WCAG 2.2 require text alternatives, keyboard access, and descriptive page titles[[14]](https://webaim.org/standards/wcag/checklist#:~:text=Web%20content%20is%20made%20available,sight%2C%20hearing%2C%20and%2For%20touch)[[15]](https://webaim.org/standards/wcag/checklist#:~:text=Guideline%202,available%20from%20a%20keyboard)[[16]](https://webaim.org/standards/wcag/checklist#:~:text=Provide%20ways%20to%20help%20users,and%20determine%20where%20they%20are). Proper metadata improves discoverability. |

## B) Proposed information architecture (Diátaxis‑aligned)

### New top‑level nav (max two levels)

```
Home: index.md
Tutorials:
  Getting started (renamed from "Getting Started"): tutorials/getting-started.md
  Example: Train an agent (from existing guides) — tutorials/train-agent.md
How‑to Guides:
  Run CLI commands (summarise CLI quick tasks): how-to/cli-tasks.md
  Evaluate an agent: how-to/evaluate-agent.md
  Integrate into pipeline: how-to/integration.md
Reference:
  CLI reference (auto‑generated via mkdocs-click/typer2): reference/cli.md
  Python API (via mkdocstrings): reference/api.md
  Configuration & formats: reference/config.md
Explanation:
  Concepts & architecture (renamed from "Design"): explanation/concepts.md
  Design decisions & ADRs: explanation/decisions.md
  Contributing & conventions: explanation/contributing.md
Docs index / search: hidden page for full index (optional): search.md
```

### Rationale

- **Tutorials** host step‑by‑step paths to achieve new skills (e.g., "Getting started", "Train an agent") for new users[[1]](https://diataxis.fr/start-here/#:~:text=The%20four%20kinds%20of%20documentation%C2%B6).
- **How‑to guides** provide short, recipe‑like answers to specific problems (e.g., evaluate an agent, integrate the CLI). Each should be self-contained and not teach underlying concepts.
- **Reference** contains the generated CLI and API docs plus configuration details---factual and exhaustive[[1]](https://diataxis.fr/start-here/#:~:text=The%20four%20kinds%20of%20documentation%C2%B6).
- **Explanation** houses conceptual overviews (system architecture) and ADRs (rationale behind design), separated from actionable tasks.

### Redirects

Create a `redirects` mapping in `mkdocs.yml` for moved pages (e.g., `Getting Started` → `tutorials/getting-started`, `Guides/Train Agent` → `tutorials/train-agent`, `CLI/<command>.md` → `reference/cli/<command>.md`, `Design/` → `explanation/concepts`, `Decisions/` → `explanation/decisions`). This ensures existing URLs continue to work.

## C) Homepage wireframe (textual)

**Hero section (above the fold)**

- **Headline**: A succinct statement of purpose, e.g., "Inspect and evaluate AI agents with ease".
- **Sub‑headline**: One‑sentence value proposition emphasising benefits (e.g., "A toolkit for understanding and benchmarking your Python agents in production").
- **Primary call to action**: Button linking to the Getting‑Started tutorial.
- **Secondary call to action**: Link to GitHub repo or "Why inspect_agents?" explanation.
- **Quick search**: Site search box or Ask (optional) enabling users to directly search docs, similar to GitHub docs[[5]](https://docs.github.com/en#:~:text=GitHub%20Docs).

**Quickstart panel**

- Short code snippet demonstrating installation (e.g., `pip install inspect-agents`) and running the CLI to inspect a simple agent.
- Link to full Getting‑Started tutorial.

**Choose your path cards** (grid of 3--4 cards)

- **Run your first evaluation** -- links to tutorial on evaluating agents.
- **Integrate the CLI** -- links to how‑to on embedding in pipelines.
- **Understand the architecture** -- links to explanation of system design.
- **Contribute or extend** -- links to explanation on contribution guidelines or plugin development.

Each card should include a title, a one‑sentence description, and an icon or illustration.

**Next steps / footer**

- **Read the concepts** -- link to Explanation section.
- **Browse the reference** -- link to CLI/API reference.
- **Join the community** -- link to issue tracker/discussion board.
- Social cards for Twitter/LinkedIn if desired.

This structure mirrors successful docs homepages like GitHub's, which emphasise a hero, quickstart, categories, and contributions[[5]](https://docs.github.com/en#:~:text=GitHub%20Docs). Avoid clutter; keep content above the fold and use high contrast.

## D) MkDocs configuration changes (minimal diff)

Below is a unified diff against the current `mkdocs.yml`. Only relevant keys are shown. Comments beginning with `#` explain reasoning; optional changes are marked.

```diff
@@
 site_name: Inspect Agents Docs
 theme:
   name: material
+  # Enable additional navigation features
+  features:
+    - navigation.path          # breadcrumbs for orientation[2]
+    - navigation.indexes       # auto‑created index pages for sections[2]
+    - navigation.top           # back‑to‑top button
+    - content.code.copy        # copy button for code blocks (already used)
+    - content.tabs             # tabs for alternative commands (optional)
+    - navigation.instant       # prefetch pages for faster loads
   palette:
@@
 plugins:
   - search
   - mermaid2
   - autorefs
   - redirects
   - mkdocstrings
   - htmlproofer
+  # Minify HTML/JS/CSS to improve performance (optional if build time allows)
+  - minify
+  # Show last updated date using git metadata
+  - git-revision-date-localized:
+      type: date
+      fallback_to_build_date: true
+  # Lightbox for images (optional but recommended)
+  - glightbox:
+      auto_caption: true    # use alt text as caption[10]
+      caption_position: bottom
+  # Generate pages programmatically (for reference/API) – optional
+  - gen-files
+  # Macros for Jinja variables and reusable content (optional)
+  - macros
+  # Versioning provider; required for mike version switcher
+  - mike
@@
 markdown_extensions:
   - admonition
   - codehilite
   - pymdownx.superfences
   - pymdownx.inlinehilite
   - tables
+  - mkdocs-click          # auto‑generate CLI docs (if using Click)
+  # or use mkdocs-typer2 for Typer CLI
@@
 extra:
+  version:
+    provider: mike  # enable version selector[6]
@@
 nav:
-  # Existing nav removed for brevity; replace with new structure
+  - Home: index.md
+  - Tutorials:
+      - Getting started: tutorials/getting-started.md
+      - Train an agent: tutorials/train-agent.md
+  - How‑to Guides:
+      - Run CLI commands: how-to/cli-tasks.md
+      - Evaluate an agent: how-to/evaluate-agent.md
+      - Integration: how-to/integration.md
+  - Reference:
+      - CLI: reference/cli.md
+      - API: reference/api.md
+      - Config & formats: reference/config.md
+  - Explanation:
+      - Concepts & architecture: explanation/concepts.md
+      - Design decisions: explanation/decisions.md
+      - Contributing: explanation/contributing.md
+  - Search (hidden): search.md
@@
 redirects:
+  # Map old URLs to new ones after restructure
+  getting-started.md: tutorials/getting-started.md
+  cli/README.md: reference/cli.md
+  guides/train-agent.md: tutorials/train-agent.md
+  design/index.md: explanation/concepts.md
+  decisions/index.md: explanation/decisions.md
```

**Notes:**

- The minify plugin can be either `minify` (Material site)[[9]](https://sm-26.github.io/SWM-Wiki/plugins/minify-html/#:~:text=Minify%20HTML%C2%B6) or `minify-html`[[17]](https://pypi.org/project/mkdocs-minify-html-plugin/#:~:text=MkDocs%20plugin%20for%20minification%20using,JS%20%2B%20CSS%20minifier); choose one depending on maintenance.
- If using Typer instead of Click, replace `mkdocs-click` with `mkdocs-typer2` and adjust accordingly[[8]](https://syn54x.github.io/mkdocs-typer2/#:~:text=A%20MkDocs%20plugin%20that%20automatically,for%20your%20Typer%20CLI%20applications).
- Add `search.boost` front matter to important pages (e.g., `tutorials/getting-started.md`) to boost them in search results[[11]](https://squidfunk.github.io/mkdocs-material/setup/setting-up-site-search/#:~:text=Search%20boosting%C2%B6), and `search.exclude` for pages like `CHANGELOG.md`[[12]](https://squidfunk.github.io/mkdocs-material/setup/setting-up-site-search/#:~:text=Search%20exclusion%C2%B6).

## E) Content patterns & templates

**1. Tutorials (step‑by‑step lessons)**

Structure:

1. **Purpose** -- one sentence describing the goal.
2. **Prerequisites** -- list any requirements (installed dependencies, accounts).
3. **Steps (numbered)** -- each step starts with a heading, uses imperative verbs, and provides code blocks or commands. Use admonitions for notes and warnings.
4. **Outcome** -- recap what the reader achieved and link to next tutorial.

Example header:

````markdown
---
title: Getting started
search:
  boost: 2  # improve search ranking[11]
---

# Getting started

In this tutorial you'll install **inspect_agents**, run a simple agent, and view the inspection report.

## Prerequisites

- Python 3.11+
- pip

## Step 1 – Install the package
```bash
pip install inspect_agents
```

...
````

**2. How‑to Guides**

Structure:

1. **Goal** – clearly state what the guide helps accomplish.
2. **Short introduction** – context and expected outcome.
3. **Procedure** – bullet or numbered instructions. Each section should be self‑contained; avoid teaching concepts; cross‑link to reference pages.
4. **See also** – links to related tutorials or explanation pages.

Example: `How to evaluate an agent` with a CLI command and sample configuration.

**3. Reference**

Use auto‑generation for CLI and API:

- For Click CLI: use `::: mkdocs-click` directive:

  ```markdown
  # CLI reference

  ::: mkdocs-click
      :module: inspect_agents.cli
      :command: main
      :depth: 2
  ```

  This directive pulls docstrings from the Click commands and generates sections with parameter tables[[7]](https://pypi.org/project/mkdocs-click/0.1.1/#:~:text=Quickstart).

- For Typer CLI: use `::: mkdocs-typer2` with `:module:` and `:name:` parameters; enable `pretty: true` in plugin config to display options in tables[[18]](https://syn54x.github.io/mkdocs-typer2/#:~:text=Basic%20Configuration).

- For Python API: continue using `mkdocstrings` and annotate functions/classes thoroughly. Group modules logically and ensure cross‑refs via `autorefs`.

**4. Explanation (conceptual)**

Structure:

1. **Problem statement** – describe why the concept matters.
2. **Overview** – diagram or architecture (use Mermaid if helpful).
3. **In‑depth discussion** – break into subtopics (design rationale, trade‑offs).
4. **Related ADRs** – link to design decisions.
5. **Further reading** – external resources or standards.

**5. Conventions & contributing**

Provide guidelines on style (sentence‑case headings[[3]](https://developers.google.com/style/headings#:~:text=Use%20sentence%20case%20for%20headings,headings%20and%20titles%20are%20unique)), admonition usage, list formatting[[19]](https://developers.google.com/style/lists#:~:text=List%20or%20table%3F), and code snippet inclusion using `include-markdown` plugin:

````markdown
```{include-markdown} ../../src/inspect_agents/example.py
:dedent: 0
:rewrite_relative_urls: true
```
````

Encourage Vale or markdownlint by providing `.vale.ini` and `.markdownlint.json` with rules aligning to Google or Microsoft style guides.

## F) Workflow & quality gates

**1. Continuous integration (CI)**

PR builds should run quickly (<5 min). Steps: (i) install dependencies, (ii) run `mkdocs build`, (iii) run `htmlproofer` with offline checks only, (iv) run lints (Vale and markdownlint). If any step fails, block merge.

Use GitHub Actions caching to speed up installations.

Nightly scheduled workflow runs `htmlproofer` with external link checks and builds the sitemap.

Set up `mkdocs-material/.github/workflows/deploy.yml` to deploy `gh-pages` branch on every merge; use GitHub Pages environments for PR previews.

**2. Authoring ergonomics**

Provide a `CONTRIBUTING.md` explaining doc structure, Diátaxis categories, naming conventions, and how to run docs locally.

Add templates in `.github/ISSUE_TEMPLATE` or `.github/PULL_REQUEST_TEMPLATE` with checklists (style, alt text, internal links).

Use Vale and markdownlint to enforce style; include rules for headings (sentence case, no consecutive headings), list formatting, active voice, inclusive language.

Use `mkdocs-gen-files` to auto‑generate indexes or API stubs from code; store generation scripts under `scripts/gen_docs.py` and call them in `pre_build` hook.

Use Git hooks or pre‑commit to run lints and `python -m pip install -e .` for local dev.

**3. Analytics and privacy**

Use a lightweight privacy‑respectful tool like Plausible or Matomo; integrate via `<script>` in `extra_javascript` and provide an opt‑in mechanism.

Track metrics relevant to documentation quality: search zero‑results count, time on page, exit rate, and most viewed guides.

Avoid GA4 unless accepted by organization's privacy policy.

## G) Accessibility and SEO checklist

Use this checklist during reviews. Items derive from WCAG 2.2 and Material best practices.

1. **Text alternatives** -- All meaningful images have descriptive `alt` text; decorative images use empty alt (`alt=""`)[[14]](https://webaim.org/standards/wcag/checklist#:~:text=Web%20content%20is%20made%20available,sight%2C%20hearing%2C%20and%2For%20touch).
2. **Headings and page titles** -- Each page has a unique H1 and a descriptive `<title>`; headings follow a logical hierarchy and use sentence‑style capitalization[[4]](https://learn.microsoft.com/en-us/style-guide/scannable-content/headings#:~:text=Headings%20provide%20both%20structure%20and,content%20and%20find%20entry%20points).
3. **Keyboard navigation** -- All interactive elements (links, buttons, tabs) are reachable and operable via keyboard; no keyboard traps[[15]](https://webaim.org/standards/wcag/checklist#:~:text=Guideline%202,available%20from%20a%20keyboard).
4. **Skip navigation** -- Provide a skip‑to‑content link at the top of each page to bypass navigation for screen readers and keyboard users[[16]](https://webaim.org/standards/wcag/checklist#:~:text=Provide%20ways%20to%20help%20users,and%20determine%20where%20they%20are).
5. **Breadcrumbs** -- Enable breadcrumbs (`navigation.path`) for orientation[[2]](https://squidfunk.github.io/mkdocs-material/setup/setting-up-navigation/#:~:text=Navigation%20path%20Breadcrumbs%C2%B6).
6. **Sufficient contrast** -- Ensure text/background color contrast meets WCAG 2.2 AA (4.5:1 for normal text).
7. **Link text** -- Links describe their destination (avoid "click here"); differentiate visually between links and plain text[[16]](https://webaim.org/standards/wcag/checklist#:~:text=Provide%20ways%20to%20help%20users,and%20determine%20where%20they%20are).
8. **Focus indicators** -- Interactive elements display visible focus styling (browser default or custom) so keyboard users can see their location[[16]](https://webaim.org/standards/wcag/checklist#:~:text=Provide%20ways%20to%20help%20users,and%20determine%20where%20they%20are).
9. **ARIA attributes** -- Use ARIA labels for icons, tabs, accordions; avoid using `role` unless necessary.
10. **Responsive design** -- Test pages on mobile and ensure that navigation collapses gracefully and content is readable.
11. **Language attributes** -- Set the `lang` attribute to `en` (or appropriate locale) in `mkdocs.yml` (Material sets this automatically).
12. **Metadata** -- Configure canonical URLs, `description`, Open Graph and Twitter card metadata for each page.
13. **Sitemap** -- Generate a sitemap (`mkdocs-sitemap` plugin) and reference in `robots.txt` for search engines.
14. **No broken links** -- Use `htmlproofer` in CI for internal links; run external link checks nightly.
15. **Code blocks** -- Provide caption or summary where necessary; enable copy buttons; ensure long lines wrap or scroll.
16. **Internationalization** -- If planning multiple languages, consider `mkdocs-static-i18n`; organise translated files using the `suffix` or `folder` structure[[21]](https://ultrabug.github.io/mkdocs-static-i18n/#:~:text=The%20%60mkdocs,to%20your%20existing%20documentation%20pages)[[22]](https://ultrabug.github.io/mkdocs-static-i18n/setup/choosing-the-structure/#:~:text=Choosing%20the%20docs%20structure).

By following this plan, `inspect_agents` can deliver a modern, user‑friendly documentation site that scales with the project, improves discoverability, and upholds accessibility and performance standards.

## References

[1]: https://diataxis.fr/start-here/#:~:text=The%20four%20kinds%20of%20documentation%C2%B6
[2]: https://squidfunk.github.io/mkdocs-material/setup/setting-up-navigation/#:~:text=Navigation%20path%20Breadcrumbs%C2%B6
[3]: https://developers.google.com/style/headings#:~:text=Use%20sentence%20case%20for%20headings,headings%20and%20titles%20are%20unique
[4]: https://learn.microsoft.com/en-us/style-guide/scannable-content/headings#:~:text=Headings%20provide%20both%20structure%20and,content%20and%20find%20entry%20points
[5]: https://docs.github.com/en#:~:text=GitHub%20Docs
[6]: https://squidfunk.github.io/mkdocs-material/setup/setting-up-versioning/#:~:text=to%20MkDocs%2C%20i,of%20your%20documentation%20remain%20untouched
[7]: https://pypi.org/project/mkdocs-click/0.1.1/#:~:text=Quickstart
[8]: https://syn54x.github.io/mkdocs-typer2/#:~:text=A%20MkDocs%20plugin%20that%20automatically,for%20your%20Typer%20CLI%20applications
[9]: https://sm-26.github.io/SWM-Wiki/plugins/minify-html/#:~:text=Minify%20HTML%C2%B6
[10]: https://pypi.org/project/mkdocs-glightbox/#:~:text=1,1
[11]: https://squidfunk.github.io/mkdocs-material/setup/setting-up-site-search/#:~:text=Search%20boosting%C2%B6
[12]: https://squidfunk.github.io/mkdocs-material/setup/setting-up-site-search/#:~:text=Search%20exclusion%C2%B6
[13]: https://timvink.github.io/mkdocs-git-revision-date-localized-plugin/options/#:~:text=Options
[14]: https://webaim.org/standards/wcag/checklist#:~:text=Web%20content%20is%20made%20available,sight%2C%20hearing%2C%20and%2For%20touch
[15]: https://webaim.org/standards/wcag/checklist#:~:text=Guideline%202,available%20from%20a%20keyboard
[16]: https://webaim.org/standards/wcag/checklist#:~:text=Provide%20ways%20to%20help%20users,and%20determine%20where%20they%20are
[17]: https://pypi.org/project/mkdocs-minify-html-plugin/#:~:text=MkDocs%20plugin%20for%20minification%20using,JS%20%2B%20CSS%20minifier
[18]: https://syn54x.github.io/mkdocs-typer2/#:~:text=Basic%20Configuration
[19]: https://developers.google.com/style/lists#:~:text=List%20or%20table%3F
[20]: https://pypi.org/project/mkdocs-include-markdown-plugin/#:~:text=Installation
[21]: https://ultrabug.github.io/mkdocs-static-i18n/#:~:text=The%20%60mkdocs,to%20your%20existing%20documentation%20pages
[22]: https://ultrabug.github.io/mkdocs-static-i18n/setup/choosing-the-structure/#:~:text=Choosing%20the%20docs%20structure
