# Speclord Implementation Plan

## Vision

Speclord is a standalone Python CLI — the **spec layer for AI-assisted development**. Specs are the source of truth: human-readable markdown files describing what every piece of code should do. Speclord provides context to AI tools (Claude Code, Cursor, Copilot), enforces compliance, and catches drift. It does NOT generate code.

**Install:** `pip install speclord`
**One command, instant value:** `speclord emit claude` → CLAUDE.md from your spec hierarchy.

## Spec Format

Three tiers, hierarchical:

1. **Org spec** (`org.spec.yaml` at repo root) — organization-wide constraints
2. **Service spec** (`.spec.yaml` in package dirs) — package-level conventions
3. **File spec** (`.spec.md` next to code files) — per-file contract (YAML frontmatter + markdown body)

Resolution: org → service → file. Each level inherits from and constrains the level below.

## Tech Stack

| Need | Tool |
|------|------|
| CLI framework | click |
| YAML parsing | pyyaml |
| Frontmatter extraction | python-frontmatter |
| Terminal output | rich |
| File matching | pathlib + fnmatch (stdlib) |
| Hashing | hashlib (stdlib) |
| AI backend | Claude Code SDK (`@anthropic-ai/claude-code-sdk`) |
| Testing | pytest + pytest-cov |
| Type checking | mypy (strict) |
| Linting | ruff |
| Project management | uv |

## AI Architecture

All AI commands use the **Claude Code SDK** (agentic mode). The agent gets filesystem tools (Read, Glob, Grep) and can explore the codebase for context. This produces higher-quality results than single-turn prompt stuffing because the AI can discover relevant files, read dependencies, and understand the broader codebase.

- **Analysis commands** (drift, review): Agent reads specs + code + related files, returns structured JSON. `maxTurns=10`, `maxBudget=$0.50`.
- **Generation commands** (draft, migrate draft): Agent reads templates + code + context, writes spec files. `maxTurns=25`, `maxBudget=$1.00`.
- **Testing**: All AI tests use `MockAdapter` — no real API calls, no cost.

---

## Phase 1: Foundation ✅

Steps 1–6. Complete. 106 tests, 92% coverage, 399 lines of source.

- [x] **Step 1: Project scaffolding** — `pyproject.toml`, `__init__.py`, `cli.py`, `errors.py`, test structure
- [x] **Step 2: Types** — `types.py` with dataclasses (FileSpec, OrgSpec, ServiceSpec, LintFinding, etc.)
- [x] **Step 3: Parser** — `parser.py` with parse/discover functions
- [x] **Step 4: Validator + lint** — `validator.py`, `speclord lint` command
- [x] **Step 5: Init + new** — `speclord init`, `speclord new <type> <path>`, bundled templates
- [x] **Step 6: Resolver + compile** — `resolver.py`, `registry.py`, `hasher.py`, `speclord compile`

**Commands:** `init`, `new`, `lint`, `compile`
**Modules:** cli, types, parser, validator, resolver, registry, hasher, errors

---

## Phase 2: Context & Emit (Steps 7–15)

The bridge between specs and AI tools. After this phase, `speclord emit claude` makes Claude Code spec-aware, and your team has a config file for customization.

- [x] **Step 7: Switch to uv**
  - Replace hatch with uv as project manager
  - Update `pyproject.toml` for uv compatibility
  - Create `uv.lock`
  - Update .gitignore
  - **Verify:** `uv run speclord --version` works, `uv run pytest` passes

- [x] **Step 8: Config file support**
  - **Creates:** `src/speclord/config.py`
  - Load config from `[tool.speclord]` in `pyproject.toml` or `.speclordrc.yaml`
  - Config fields: `root`, `coverage.extensions`, `coverage.ignore`, `defaults.owner`, `defaults.status`, `emit.targets`
  - Merge with CLI flags (CLI flags override config)
  - **Tests:** config loading, merging, defaults

- [x] **Step 9: Context builder**
  - **Creates:** `src/speclord/context.py`, adds `context` to CLI
  - `build_context(spec_path, root) -> str` — resolves chain, assembles org constraints + service conventions + file spec as AI-ready text
  - CLI: `speclord context <file>` — prints to stdout (pipeable)
    - `--batch <glob>` for multiple specs
  - **Tests:** output includes all chain layers, batch combines correctly

- [x] **Step 10: Resolve command**
  - **Adds:** `resolve` to CLI
  - CLI: `speclord resolve <file>` — prints the full resolved chain (org → service → file) for a spec
  - Shows which constraints come from which level
  - **Tests:** correct chain display for various depths

- [x] **Step 11: Emitter**
  - **Creates:** `src/speclord/emitter.py`, adds `emit` to CLI
  - `emit_claude(root) -> str` — generates CLAUDE.md from spec hierarchy
  - `emit_cursor(root) -> str` — generates .cursorrules
  - `emit_copilot(root) -> str` — generates .github/copilot-instructions.md
  - Reads org spec, all service specs, summarizes conventions/constraints/patterns
  - CLI: `speclord emit <target>` (claude | cursor | copilot | all)
  - **Tests:** emitted content includes org constraints, service conventions, file-level patterns

- [x] **Step 12: Dogfood — bootstrap speclord's own specs**
  - Run `speclord init` inside `speclord-py/` to create `.spec/` structure
  - Write `org.spec.yaml` at repo root (organization: speclord, stack: python, etc.)
  - Write a root-level `.spec.yaml` service spec for the speclord package
  - Write file specs (`.spec.md`) for each Phase 1 module: cli, types, parser, validator, resolver, registry, hasher, errors
  - Run `speclord lint` — all specs must pass
  - Run `speclord compile` — registry.lock.json generated
  - Run `speclord emit claude` — verify generated CLAUDE.md includes org constraints, service conventions, and per-module contracts
  - **Verify:** `speclord lint` clean, `speclord emit claude` produces useful output

- [x] **Step 13: Coverage**
  - **Creates:** `src/speclord/coverage.py`, adds `coverage` to CLI
  - `check_coverage(root, config) -> CoverageReport` — finds code files without corresponding specs
  - Respects config for which extensions count and what to ignore
  - CLI: `speclord coverage`
    - `--min <percent>` — exit non-zero if below threshold
    - `--format json`
  - **Tests:** correct detection with various file types, config-driven extensions

- [x] **Step 14: Check (lightweight drift)**
  - **Creates:** `src/speclord/checker.py`, adds `check` to CLI
  - `check_spec(spec_path, root) -> list[CheckFinding]` — non-AI structural checks:
    - Does the generates target file actually exist?
    - Do declared dependencies reference real specs?
    - Is the spec status consistent (e.g., not "active" with empty body)?
    - Does the inherits path resolve to a real file?
  - CLI: `speclord check [file]` — checks one or all specs
    - `--format json`
  - **Tests:** catches missing targets, broken deps, inconsistent status

- [x] **Step 15: Status dashboard**
  - **Adds:** `status` to CLI
  - One-screen dashboard: spec count by type/status, coverage %, last compile time, lint findings summary, check findings summary
  - CLI: `speclord status`
  - **Tests:** output includes expected sections

**Phase 2 done when:** `speclord emit claude` produces valid CLAUDE.md. `speclord coverage` reports spec coverage. `speclord check` catches structural issues. Config file works.

---

## Phase 3: Migration — Non-AI (Steps 16–20)

Scan, plan, and track migration without AI. After this phase, you have full visibility into what needs specs and a dependency-ordered plan for creating them.

- [x] **Step 16: Dependency graph**
  - **Creates:** `src/speclord/deps.py`, adds `deps` to CLI
  - `build_dep_graph(root) -> DepGraph` — builds a directed graph from spec dependencies
  - `topological_sort(graph) -> list[str]` — dependency-first ordering
  - Cycle detection
  - CLI: `speclord deps [file]` — show dependency tree for a spec, or full graph
    - `--format json`
  - **Tests:** graph construction, topological sort, cycle detection

- [x] **Step 17: Search**
  - **Adds:** `search` to CLI
  - CLI: `speclord search <query>` — spec-aware search across all specs
    - `--type <type>` — filter by spec type
    - `--owner <owner>` — filter by owner
    - `--status <status>` — filter by status
    - Searches spec body text, frontmatter fields
    - `--format json`
  - **Tests:** keyword search, field filtering, no results

- [x] **Step 18: Migrate scan**
  - **Creates:** `src/speclord/migrate/scanner.py`, adds `migrate scan` to CLI
  - `scan_codebase(root, config) -> MigrationScan` — counts total code files, specced files, unspecced files, groups by directory
  - CLI: `speclord migrate scan` — rich table output showing directories, file counts, coverage
  - **Tests:** scan on fixture repo returns expected counts

- [x] **Step 19: Migrate plan**
  - **Creates:** `src/speclord/migrate/planner.py`, adds `migrate plan` to CLI
  - `plan_migration(root, config) -> MigrationPlan` — uses dependency graph + scan results to suggest migration phases
    - Phase 1: core models/shared utilities (most depended-on)
    - Phase 2: services that depend on core
    - Phase 3: leaf modules
  - CLI: `speclord migrate plan` — prints phased migration plan
  - **Tests:** plan ordering respects dependencies

- [x] **Step 20: Migrate progress**
  - **Creates:** `src/speclord/migrate/progress.py`, adds `migrate progress` to CLI
  - `track_progress(root) -> ProgressReport` — coverage over time (compares current vs registry.lock.json from previous compiles)
  - CLI: `speclord migrate progress` — shows current vs target, velocity
  - **Tests:** progress calculation

**Phase 3 done when:** `speclord migrate scan` shows what needs specs. `speclord migrate plan` suggests a phased approach. `speclord deps` visualizes the dependency graph.

---

## Phase 4: AI Engine (Steps 21–26)

Claude Code SDK integration for intelligent analysis and spec generation. All tests use MockAdapter.

- [x] **Step 21: AI adapter**
  - **Creates:** `src/speclord/ai/__init__.py`, `src/speclord/ai/adapter.py`
  - `LLMAdapter` Protocol: `analyze(prompt, system, cwd, schema) -> dict`, `generate(prompt, system, cwd) -> str`
  - `ClaudeCodeAdapter` — wraps Claude Code SDK, configurable model/turns/budget
  - `MockAdapter` — returns canned responses for testing
  - Config: reads `ANTHROPIC_API_KEY` from env, model from config file
  - **Tests:** mock adapter returns expected shapes

- [x] **Step 22: AI prompts**
  - **Creates:** `src/speclord/ai/prompts.py`
  - `build_drift_prompt(chain, code) -> (prompt, system)` — context-rich prompt for drift analysis
  - `build_review_prompt(spec) -> (prompt, system)` — prompt for spec quality review
  - `build_draft_prompt(description, template, context) -> (prompt, system)` — prompt for spec drafting
  - **Tests:** prompts include expected context sections

- [x] **Step 23: Drift analyzer**
  - **Creates:** `src/speclord/ai/drift.py`, adds `drift` to CLI
  - `analyze_drift(spec_path, root, adapter) -> DriftReport` — AI compares spec to code
  - CLI: `speclord drift [file]` — analyzes one or all specs
    - `--fail-on <severity>` — exit non-zero at threshold
    - `--format json`
  - **Tests:** mock drift findings, report structure

- [x] **Step 24: Spec reviewer**
  - **Creates:** `src/speclord/ai/review.py`, adds `review` to CLI
  - `review_spec(spec_path, root, adapter) -> SpecReview` — AI reviews spec quality
  - CLI: `speclord review <file>`
    - `--format json`
  - **Tests:** mock review, structure validation

- [x] **Step 25: Spec drafter**
  - **Creates:** `src/speclord/ai/draft.py`, adds `draft` to CLI
  - `draft_spec(description, path, root, adapter) -> str` — AI drafts a new spec
  - CLI: `speclord draft <description> <path>`
    - `--from-code` — reverse-engineer from existing code
    - `--type <type>` — override spec type
  - **Tests:** mock returns valid spec markdown

- [x] **Step 26: Migrate draft (AI batch)**
  - **Creates:** `src/speclord/migrate/drafter.py`, adds `migrate draft` to CLI
  - `batch_draft(paths, root, adapter) -> Generator` — sequential AI spec drafting with rate limiting
  - CLI: `speclord migrate draft --batch <dir>` — drafts specs for all unspecced files
    - Progress bar, writes draft specs
  - **Tests:** mock adapter, verify specs are written

**Phase 4 done when:** `speclord drift` returns structured findings. `speclord review` evaluates spec quality. `speclord draft` produces valid specs. `speclord migrate draft` batch-creates specs. All tests use MockAdapter.

---

## Phase 5: Ship It (Steps 27–29)

Polish, documentation, PyPI publish.

- [x] **Step 27: End-to-end test**
  - `tests/test_e2e.py` — full workflow in tmpdir: init → new → lint → compile → coverage → context → emit → check → status
  - Verifies the entire non-AI pipeline works end-to-end

- [x] **Step 28: README + documentation**
  - `README.md` — installation, quick start, command reference, spec format guide, config reference
  - Docstrings on all public functions

- [x] **Step 29: PyPI publish**
  - `pyproject.toml` finalized with classifiers, URLs, license
  - GitHub Actions CI: pytest, ruff, mypy on every push
  - PyPI publish workflow on tag
  - **Verify:** `pip install speclord && speclord --help` works from PyPI

**Phase 5 done when:** `pip install speclord && speclord --help` works. CI green. README has working examples.

---

## Phase 6: CI & Enforcement (Steps 30–33)

Post-ship. Add once specs are the norm and you need to prevent regression.

- [ ] **Step 30: CI command**
  - `speclord ci` — combined check: lint + coverage + check + optional drift
    - `--min-coverage <percent>` — fail if below threshold
    - `--changed-only` — only check files changed vs base branch (git diff)
    - `--fail-on-drift` — also run AI drift, fail on findings
  - **Tests:** exit codes for various failure scenarios

- [ ] **Step 31: Watch mode**
  - `speclord watch` — file watcher (watchdog)
    - On spec change: re-lint + re-compile + re-emit
    - On code change: re-check coverage
    - Rich live display
  - **Tests:** mock filesystem events

- [ ] **Step 32: Git hooks**
  - `speclord hooks install` — creates git hooks
    - pre-commit: `speclord lint`
    - pre-push: `speclord ci`
  - `speclord hooks uninstall` — removes hooks
  - **Tests:** hook scripts created with correct content

- [ ] **Step 33: Diff**
  - `speclord diff` — show spec changes vs base branch
    - Uses `git diff` under the hood
    - `--base <branch>` — compare against specific branch (default: main)
  - **Tests:** diff detection with mock git output

**Phase 6 done when:** `speclord ci --min-coverage 80` works in CI. Watch mode re-emits on changes. Git hooks install cleanly.

---

## Progress

| Phase | Steps | Status |
|-------|-------|--------|
| 1: Foundation | 1–6 | ✅ 6/6 |
| 2: Context & Emit | 7–15 | 🔨 2/9 |
| 3: Migration (non-AI) | 16–20 | ⬜ 0/5 |
| 4: AI Engine | 21–26 | ⬜ 0/6 |
| 5: Ship It | 27–29 | ⬜ 0/3 |
| 6: CI & Enforcement | 30–33 | ⬜ 0/4 |
| **Total** | **1–33** | **8/33** |

## Command Reference

| Command | Phase | Status |
|---------|-------|--------|
| `speclord init` | 1 | ✅ |
| `speclord new <type> <path>` | 1 | ✅ |
| `speclord lint` | 1 | ✅ |
| `speclord compile` | 1 | ✅ |
| `speclord context <file>` | 2 | ⬜ |
| `speclord resolve <file>` | 2 | ⬜ |
| `speclord emit <target>` | 2 | ⬜ |
| `speclord coverage` | 2 | ⬜ |
| `speclord check [file]` | 2 | ⬜ |
| `speclord status` | 2 | ⬜ |
| `speclord deps [file]` | 3 | ⬜ |
| `speclord search <query>` | 3 | ⬜ |
| `speclord migrate scan` | 3 | ⬜ |
| `speclord migrate plan` | 3 | ⬜ |
| `speclord migrate progress` | 3 | ⬜ |
| `speclord drift [file]` | 4 | ⬜ |
| `speclord review <file>` | 4 | ⬜ |
| `speclord draft <desc> <path>` | 4 | ⬜ |
| `speclord migrate draft` | 4 | ⬜ |
| `speclord ci` | 6 | ⬜ |
| `speclord watch` | 6 | ⬜ |
| `speclord hooks install` | 6 | ⬜ |
| `speclord diff` | 6 | ⬜ |

## Verification

- After each step: `uv run pytest` passes, `uv run ruff check` clean
- After Phase 2: `speclord emit claude` produces valid CLAUDE.md
- After Phase 3: `speclord migrate scan` works on a real codebase
- After Phase 4: `speclord drift <file>` with mock adapter returns findings
- After Phase 5: `pip install speclord && speclord --help` works from PyPI
