# Speclord Complete Guide

> The spec layer for AI-assisted development.

Speclord is a Python CLI tool that manages **spec files** — human-readable markdown documents describing what every piece of code should do. It provides context to AI tools (Claude Code, Cursor, Copilot), enforces compliance via lint and structural checks, and catches drift between specs and code using AI analysis.

**Speclord does NOT generate code.** It generates *specs* and *AI instructions*. The specs are the source of truth; AI tools and humans implement them.

---

## Table of Contents

1. [Mental Model](#1-mental-model)
2. [Installation](#2-installation)
3. [Project Structure](#3-project-structure)
4. [The Spec Format](#4-the-spec-format)
   - [Org Spec](#41-org-spec-orgspecyaml)
   - [Service Spec](#42-service-spec-specyaml)
   - [File Spec](#43-file-spec-specmd)
   - [Inheritance & Resolution](#44-inheritance--resolution)
5. [Configuration](#5-configuration)
6. [Commands Reference](#6-commands-reference)
   - [init](#init)
   - [new](#new)
   - [lint](#lint)
   - [compile](#compile)
   - [check](#check)
   - [coverage](#coverage)
   - [resolve](#resolve)
   - [context](#context)
   - [emit](#emit)
   - [deps](#deps)
   - [search](#search)
   - [status](#status)
   - [drift](#drift) (AI)
   - [review](#review) (AI)
   - [draft](#draft) (AI)
   - [migrate scan](#migrate-scan)
   - [migrate plan](#migrate-plan)
   - [migrate progress](#migrate-progress)
   - [migrate draft](#migrate-draft) (AI)
7. [AI Architecture](#7-ai-architecture)
8. [Templates](#8-templates)
9. [Validation Rules Reference](#9-validation-rules-reference)
10. [Structural Check Rules Reference](#10-structural-check-rules-reference)
11. [Data Types Reference](#11-data-types-reference)
12. [Error Types](#12-error-types)
13. [Ignored Directories](#13-ignored-directories)
14. [Recipes & Workflows](#14-recipes--workflows)
15. [Internal Architecture](#15-internal-architecture)

---

## 1. Mental Model

Speclord introduces a **three-tier spec hierarchy** to your codebase:

```
org.spec.yaml          ← Organization-wide constraints (1 per repo)
  └─ .spec.yaml        ← Service/package conventions (1 per directory)
       └─ foo.spec.md  ← File-level contract (1 per code file)
```

Each level **inherits from** the one above via the `inherits` field. Resolution walks the chain: org → service → file.

The pipeline is:

```
write specs → lint → compile → emit → (AI: drift / review / draft)
```

- **lint** validates spec syntax (required fields, valid types/statuses)
- **compile** hashes everything into `registry.lock.json`
- **check** validates spec semantics (do referenced files exist?)
- **emit** generates AI instruction files (CLAUDE.md, .cursorrules, etc.)
- **coverage** finds code files without specs
- **drift** uses AI to compare specs against actual code
- **review** uses AI to score spec quality
- **draft** uses AI to write new specs

---

## 2. Installation

### From PyPI

```bash
pip install speclord
```

### From source (development)

```bash
git clone https://github.com/dkushkuley/speclord
cd speclord
uv sync --dev
uv run speclord --version
```

### Requirements

- **Python 3.10+** (uses `from __future__ import annotations`, `X | Y` union syntax)
- **Dependencies:** click, pyyaml, python-frontmatter, rich, tomli (Python <3.11 only)
- **For AI commands:** [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated (`claude` must be on your PATH)

### Verify installation

```bash
speclord --version    # → speclord, version 0.1.0
speclord --help       # → shows all 16 commands
```

---

## 3. Project Structure

After `speclord init`, your project looks like this:

```
my-project/
├── org.spec.yaml              ← org-level spec (created by init)
├── .spec/
│   └── templates/             ← spec templates (copied from bundled)
│       ├── utility.spec.md
│       ├── api-endpoint.spec.md
│       ├── data-model.spec.md
│       └── service.spec.yaml
├── src/
│   ├── .spec.yaml             ← service spec for src/ (created by `new service`)
│   ├── auth/
│   │   ├── login.py
│   │   ├── login.spec.md      ← file spec for login.py
│   │   ├── routes.py
│   │   └── routes.spec.md     ← file spec for routes.py
│   └── utils.py
├── registry.lock.json         ← compiled spec registry (created by `compile`)
├── CLAUDE.md                  ← AI instructions (created by `emit claude`)
└── .speclordrc.yaml           ← optional config file
```

**Key naming conventions:**
- File specs: `<name>.spec.md` lives next to `<name>.py` (or `.ts`, `.js`, etc.)
- Service specs: `.spec.yaml` (hidden file in each package directory)
- Org spec: `org.spec.yaml` (at repo root, exactly one)

---

## 4. The Spec Format

### 4.1. Org Spec (`org.spec.yaml`)

The organization spec lives at the repository root. It defines org-wide constraints that cascade down to every spec. Created automatically by `speclord init`.

**Required fields:** `specVersion`, `organization`

```yaml
specVersion: "0.1.0"
organization: "acme"

stack:
  runtime: "python"
  language: "python"

patterns:
  naming: "snake_case"
  testing: "pytest"

security:
  - "Validate all input"
  - "No secrets in source code"
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `specVersion` | string | yes | Format version, currently `"0.1.0"` |
| `organization` | string | yes | Organization or team name |
| `stack` | dict | no | Technology stack (`runtime`, `language`, etc.) |
| `patterns` | dict | no | Architectural patterns (`naming`, `testing`, etc.) |
| `security` | list[str] | no | Org-wide security rules |

### 4.2. Service Spec (`.spec.yaml`)

Service specs live in package directories as hidden files named `.spec.yaml`. They define conventions for all code in that directory tree.

**Required fields:** `specVersion`, `inherits`, `service`, `owner`

```yaml
specVersion: "0.1.0"
inherits: "../org.spec.yaml"

service: "auth"
owner: "@auth-team"

conventions:
  naming: "snake_case"

testing:
  framework: "pytest"
  coverage_target: 85

security:
  - "Hash all passwords with bcrypt"
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `specVersion` | string | yes | Format version |
| `inherits` | string | yes | Relative path to parent spec (org or another service) |
| `service` | string | yes | Service/package name |
| `owner` | string | yes | Team or person responsible |
| `conventions` | dict | no | Coding conventions (naming, style, etc.) |
| `testing` | dict | no | Testing configuration (framework, coverage target) |
| `security` | list[str] | no | Service-specific security rules |
| `dependencies` | dict | no | External service dependencies |
| `infrastructure` | dict | no | Infrastructure requirements |

### 4.3. File Spec (`.spec.md`)

File specs live next to the code file they describe. They use **YAML frontmatter** (between `---` delimiters) for structured metadata and **markdown body** for the human-readable contract.

**Required frontmatter fields:** `specVersion`, `inherits`, `type`, `owner`, `status`

```markdown
---
specVersion: "0.1.0"
inherits: ".spec.yaml"
type: "utility"
status: "active"
owner: "@auth-team"
priority: "high"
dependencies: ["../types", "../config"]
generates: "src/auth/login.py"
---

## Purpose

Handles user authentication via username and password.

## Exported Interface

- `login(username: str, password: str) -> AuthToken`
- `logout(token: AuthToken) -> None`

## Behavior

1. Validate credentials against the user store
2. Return a signed JWT on success
3. Raise `AuthError` on invalid credentials

## Edge Cases

- Empty username/password → raise `ValueError`
- Expired token on logout → silently succeed
- User not found → same error as wrong password (prevent enumeration)

## Testing Requirements

- Unit tests for valid and invalid credentials
- Integration test with mock user store
- Test for timing-safe comparison
```

#### Frontmatter Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `specVersion` | string | yes | — | Format version, currently `"0.1.0"` |
| `inherits` | string | yes | — | Relative path to parent service or org spec |
| `type` | string | yes | — | What kind of code this spec describes (see types below) |
| `status` | string | yes | — | Lifecycle status (see statuses below) |
| `owner` | string | yes | — | Team or person responsible (e.g., `"@auth-team"`) |
| `priority` | string | no | `"normal"` | `"low"`, `"normal"`, `"high"`, or `"critical"` |
| `dependencies` | list[str] | no | `[]` | Paths to other specs this one depends on |
| `generates` | string | no | `null` | Path to the code file this spec describes |

#### Spec Types (15 valid values)

| Type | Use For |
|------|---------|
| `utility` | General utility modules, helpers, shared functions |
| `api-endpoint` | HTTP endpoints, REST routes, GraphQL resolvers |
| `data-model` | Database models, schemas, DTOs |
| `middleware` | Request/response middleware, interceptors |
| `config` | Configuration loading, environment handling |
| `integration` | External service integrations, API clients |
| `event-handler` | Event listeners, message consumers, webhooks |
| `job` | Background jobs, scheduled tasks, workers |
| `migration` | Database migrations, data transformations |
| `cli-command` | CLI commands, argument parsing |
| `service` | Service-level orchestration, business logic |
| `hook` | Lifecycle hooks, plugins, extensions |
| `decorator` | Function/class decorators, wrappers |
| `model` | Domain models, value objects, entities |
| `schema` | Validation schemas, serialization formats |

#### Spec Statuses (4 valid values)

| Status | Meaning |
|--------|---------|
| `draft` | Spec is being written, not yet authoritative |
| `active` | Spec is the source of truth for this code |
| `deprecated` | Spec is being phased out, code should be migrated |
| `archived` | Spec is no longer active, kept for historical reference |

#### Dependencies Format

Dependencies are relative paths to other spec files. They support three formats:

```yaml
dependencies:
  - "types"              # bare name → sibling types.spec.md
  - "../config"          # relative path → ../config.spec.md
  - "../shared/utils.spec.md"  # full path → used as-is
```

Resolution: bare name `"types"` becomes `types.spec.md` in the same directory. A path without `.spec.md` suffix gets it appended automatically.

### 4.4. Inheritance & Resolution

The `inherits` field creates a chain from file → service → org. Speclord resolves this chain when building context or checking compliance.

```
org.spec.yaml                    (organization: "acme", stack, patterns, security)
  ↑ inherits
src/.spec.yaml                   (service: "auth", owner, conventions, testing)
  ↑ inherits
src/login.spec.md                (type: "utility", status, body)
```

**Resolution algorithm:**
1. Parse the file spec
2. Follow `inherits` to parent (relative path from spec's directory)
3. If parent is `org.spec.yaml` → parse as OrgSpec, stop
4. If parent is `*.spec.yaml` → parse as ServiceSpec
5. Follow the ServiceSpec's `inherits` to find OrgSpec (if any)
6. Return the full chain: `ResolvedChain(file_spec, service_spec, org_spec)`

Use `speclord resolve <file>` to see the chain for any spec.

---

## 5. Configuration

Speclord looks for configuration in two places (first match wins):

1. **`.speclordrc.yaml`** in the project root
2. **`[tool.speclord]`** in `pyproject.toml`

If neither exists, defaults are used. Unknown keys are silently ignored.

### `.speclordrc.yaml` format

```yaml
# Which file extensions to track for coverage
coverage:
  extensions: [".py"]
  ignore:
    - "migrations/*"
    - "tests/*"
    - "conftest.py"

# Defaults for scaffolded specs
defaults:
  owner: "@myteam"
  status: "draft"

# Which AI tools to generate instruction files for
emit:
  targets: ["claude"]
```

### `pyproject.toml` format

```toml
[tool.speclord.coverage]
extensions = [".py"]
ignore = ["migrations/*", "tests/*"]

[tool.speclord.defaults]
owner = "@myteam"
status = "draft"

[tool.speclord.emit]
targets = ["claude"]
```

### All Configuration Options

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `coverage.extensions` | list[str] | `[".py"]` | File extensions to count for spec coverage. Add `".ts"`, `".js"`, etc. for polyglot projects. |
| `coverage.ignore` | list[str] | `[]` | Glob patterns for files to exclude from coverage. Matched with `fnmatch` against relative paths. |
| `defaults.owner` | str | `null` | Default owner for `speclord new` scaffolded specs. |
| `defaults.status` | str | `"draft"` | Default status for scaffolded specs. |
| `emit.targets` | list[str] | `["claude"]` | Which AI tool targets to emit. Valid: `"claude"`, `"cursor"`, `"copilot"`. |

### Config Precedence

CLI flags always win. For `--root`:
1. If `--root` is passed on the command line, it's used directly
2. Otherwise, the `root` field from the config file is used
3. If no config file exists, `.` (current directory) is the root

---

## 6. Commands Reference

Every command supports `--help` for usage details. Most commands that produce structured output support `--format text|json`.

### Global Options

```
speclord --version     Show version and exit
speclord --help        Show all available commands
```

Running `speclord` with no subcommand prints the help text.

---

### `init`

**Initialize a `.spec/` structure in the project.**

```bash
speclord init [--root DIR] [--org NAME]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--root` | `.` | Project root directory (created if needed) |
| `--org` | `my-org` | Organization name for org.spec.yaml |

**What it creates:**
- `.spec/templates/` directory with 4 bundled templates:
  - `utility.spec.md`
  - `api-endpoint.spec.md`
  - `data-model.spec.md`
  - `service.spec.yaml`
- `org.spec.yaml` at the project root (only if it doesn't exist)

**Behavior:**
- **Idempotent:** If `.spec/` already exists, prints "already exists" and returns (exit 0, no error).
- The org spec is pre-filled with Python defaults (runtime, language, snake_case, pytest).

**Exit codes:** Always 0.

---

### `new`

**Scaffold a new spec file from a template.**

```bash
speclord new <TYPE> <PATH> [--root DIR]
```

| Argument | Description |
|----------|-------------|
| `TYPE` | One of: `utility`, `api-endpoint`, `data-model`, `service` |
| `PATH` | Target location relative to root (e.g., `src/auth/login`) |

| Option | Default | Description |
|--------|---------|-------------|
| `--root` | `.` | Project root directory |

**How PATH maps to output:**
- **File specs** (`utility`, `api-endpoint`, `data-model`): `PATH` → `<PATH>.spec.md`
  - Example: `speclord new utility src/auth/login` → creates `src/auth/login.spec.md`
- **Service specs**: `PATH` → `<PATH>/.spec.yaml`
  - Example: `speclord new service src/auth` → creates `src/auth/.spec.yaml`

**Template lookup order:**
1. `.spec/templates/<type>.spec.md` (project-level overrides)
2. Bundled templates in the speclord package

**Placeholder substitution:**
- `INHERITS_PATH` → relative path to nearest parent `.spec.yaml` or `org.spec.yaml`
- `GENERATES_PATH` → the PATH argument (posix format)
- `OWNER` → `@team` (or config `defaults.owner` if set)
- `SERVICE_NAME` → last component of PATH

**Behavior:**
- **Idempotent:** If the spec already exists, prints "already exists" and returns (exit 0).
- Creates parent directories as needed.
- Walks up from the output location to find the nearest `.spec.yaml` or `org.spec.yaml` for the `inherits` field.

**Exit codes:** 0 on success, 1 if template not found.

---

### `lint`

**Validate all spec files in the project.**

```bash
speclord lint [--root DIR] [--format text|json]
```

Discovers all spec files under root and validates each one. Validates **syntax** — required fields, valid types, valid statuses. Does NOT validate semantics (use `check` for that).

**Text output:** Rich table with columns: Severity, File, Rule, Message. Green "All specs are valid." if clean.

**JSON output:**
```json
[
  {
    "file": "src/auth/login.spec.md",
    "rule": "invalid-type",
    "message": "Unknown spec type: foo",
    "severity": "error"
  }
]
```

**Exit codes:** 0 if no errors, 1 if any error-severity findings exist (warnings don't cause failure).

See [Section 9: Validation Rules Reference](#9-validation-rules-reference) for all rules.

---

### `compile`

**Compile all specs into `registry.lock.json`.**

```bash
speclord compile [--root DIR]
```

Parses all file specs, hashes their content, and writes a JSON registry file. This registry serves as a baseline for `migrate progress` and as a quick-lookup index.

**Output file:** `registry.lock.json` at the project root.

```json
{
  "specs": {
    "src/auth/login.spec.md": {
      "path": "src/auth/login.spec.md",
      "hash": "a1b2c3...",
      "type": "utility",
      "status": "active",
      "dependencies": ["src/types.spec.md"],
      "generates": "src/auth/login.py"
    }
  },
  "errors": []
}
```

**Behavior:**
- Overwrites any existing `registry.lock.json`.
- Specs that fail to parse are recorded in the `errors` array (compilation continues).
- The hash is a SHA-256 of the spec file content.

**Exit codes:** Always 0.

---

### `check`

**Run structural integrity checks on spec files.**

```bash
speclord check [FILE] [--root DIR] [--format text|json]
```

| Argument | Description |
|----------|-------------|
| `FILE` | Optional. Check a single spec file instead of all. |

Validates **semantics** — do the things referenced in specs actually exist on disk? This is a layer above `lint`.

**Text output:** Rich table with columns: Severity, File, Rule, Message. Green "All specs pass structural checks." if clean.

**JSON output:** Same format as `lint` JSON.

**Exit codes:** 0 if no errors, 1 if any error-severity findings exist.

See [Section 10: Structural Check Rules Reference](#10-structural-check-rules-reference) for all rules.

---

### `coverage`

**Check spec coverage — find code files without specs.**

```bash
speclord coverage [--root DIR] [--min PERCENT] [--format text|json]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--min` | none | Fail if coverage is below this percentage |
| `--format` | `text` | Output format |

**How coverage works:**
- Scans for files with extensions matching `config.coverage_extensions` (default: `.py`)
- A file `foo.py` is "specced" if `foo.spec.md` exists as a sibling in the same directory
- `__init__.py` files are always excluded
- Files matching `config.coverage_ignore` patterns are excluded
- Directories in the [ignored list](#13-ignored-directories) are skipped

**Text output:**
```
Spec coverage: 75.0% (3/4 files)

Unspecced files:
  src/utils.py
```

Color: green (>=80%), yellow (>=50%), red (<50%).

**JSON output:**
```json
{
  "total_files": 4,
  "specced_files": 3,
  "coverage_pct": 75.0,
  "unspecced": ["src/utils.py"]
}
```

**Exit codes:** 0 normally, 1 if `--min` threshold not met.

---

### `resolve`

**Show the resolved inheritance chain for a spec file.**

```bash
speclord resolve <FILE> [--root DIR] [--format text|json]
```

Follows the `inherits` chain from file → service → org and displays what constraints come from each level.

**Text output:** Rich tree visualization:

```
Resolve: src/auth/login.spec.md
Chain: org.spec.yaml → src/.spec.yaml → src/auth/login.spec.md

Spec Chain
├── Organization: acme (org.spec.yaml)
│   ├── Stack: runtime=python, language=python
│   ├── Patterns: naming=snake_case, testing=pytest
│   └── Security: Validate all input
├── Service: auth (src/.spec.yaml)
│   ├── Owner: @auth-team
│   └── Testing: framework=pytest, coverage_target=85
└── File: utility, active (src/auth/login.spec.md)
    ├── Owner: @auth-team
    ├── Generates: src/auth/login.py
    └── Dependencies: ../types
```

**JSON output:**
```json
{
  "org": {
    "file": "org.spec.yaml",
    "organization": "acme",
    "stack": {"runtime": "python"},
    "patterns": {"naming": "snake_case"},
    "security": ["Validate all input"]
  },
  "service": {
    "file": "src/.spec.yaml",
    "service": "auth",
    "owner": "@auth-team",
    "conventions": {},
    "testing": {"framework": "pytest"},
    "security": []
  },
  "file": {
    "file": "src/auth/login.spec.md",
    "type": "utility",
    "status": "active",
    "owner": "@auth-team",
    "priority": "normal",
    "generates": "src/auth/login.py",
    "dependencies": ["../types"]
  }
}
```

**Exit codes:** 0 on success, 1 if file not found or resolution fails.

---

### `context`

**Build AI-ready context from the spec chain.**

```bash
speclord context <FILE> [--root DIR]
speclord context --batch "src/*.spec.md" [--root DIR]
```

Resolves the full inheritance chain and outputs structured markdown optimized for feeding to AI tools. This is what powers the `emit` command internally.

| Option | Description |
|--------|-------------|
| `FILE` | Single spec file to build context for |
| `--batch GLOB` | Glob pattern for multiple specs (e.g., `"src/**/*.spec.md"`) |

**Output format:** Markdown to stdout. Sections include:
- `# Context: <label>` header
- `## Organization Constraints` (if org spec exists)
- `## Service Conventions` (if service spec exists)
- `## File Spec` with metadata and full body

When using `--batch`, multiple contexts are joined with `---` separators.

**Exit codes:** 0 on success, 1 if file not found or no FILE/--batch given.

---

### `emit`

**Generate AI tool instruction files from the spec hierarchy.**

```bash
speclord emit <TARGET> [--root DIR] [--dry-run]
```

| Argument | Description |
|----------|-------------|
| `TARGET` | One of: `claude`, `cursor`, `copilot`, `all` |

| Option | Description |
|--------|-------------|
| `--dry-run` | Print content to stdout instead of writing files |

**Target output files:**

| Target | Output File |
|--------|-------------|
| `claude` | `CLAUDE.md` |
| `cursor` | `.cursorrules` |
| `copilot` | `.github/copilot-instructions.md` |
| `all` | All three files |

**What the emitted file contains:**
1. Auto-generation warning header with re-generation command
2. Organization section (from org.spec.yaml): stack, patterns, security
3. Service sections (from each .spec.yaml): owner, conventions, testing, security
4. Specs table: File, Type, Status, Owner, Generates for every file spec

**Behavior:**
- Skips specs inside `templates/` and `fixtures/` directories
- Creates parent directories as needed (for `.github/copilot-instructions.md`)
- The emitted file is pure markdown — no code, no YAML

**Exit codes:** Always 0.

---

### `deps`

**Show the dependency graph for specs.**

```bash
speclord deps [FILE] [--root DIR] [--format text|json]
```

| Argument | Description |
|----------|-------------|
| `FILE` | Optional. Show dependency tree for a single spec instead of full graph. |

**Without FILE (full graph):**

**Text output:** Rich table showing each spec and its dependencies, plus topological order:
```
┌───────────────────────┬──────────────────┐
│ Spec                  │ Dependencies     │
├───────────────────────┼──────────────────┤
│ src/auth/login.spec.md│ src/types.spec.md│
│ src/types.spec.md     │ none             │
└───────────────────────┴──────────────────┘

Topological order:
  1. src/types.spec.md
  2. src/auth/login.spec.md
```

**JSON output:**
```json
{
  "nodes": ["src/auth/login.spec.md", "src/types.spec.md"],
  "edges": {
    "src/auth/login.spec.md": ["src/types.spec.md"],
    "src/types.spec.md": []
  },
  "order": ["src/types.spec.md", "src/auth/login.spec.md"]
}
```

**With FILE (single spec tree):**

Shows the recursive dependency tree for one spec. Circular references are marked.

**JSON output:**
```json
{
  "src/auth/login.spec.md": {
    "src/types.spec.md": {}
  }
}
```

**Cycle detection:** If a dependency cycle exists, exits with code 1 and reports the cycle path (e.g., `A → B → C → A`).

**Exit codes:** 0 on success, 1 if cycle detected or file not found.

---

### `search`

**Search specs by text query and/or field filters.**

```bash
speclord search <QUERY> [--root DIR] [--format text|json]
speclord search --type utility [--root DIR] [--format text|json]
speclord search <QUERY> --owner "@team" --status active [--format json]
```

| Argument / Option | Description |
|-------------------|-------------|
| `QUERY` | Case-insensitive text search across all fields |
| `--type TEXT` | Exact match on spec type |
| `--owner TEXT` | Exact match on owner |
| `--status TEXT` | Exact match on status |

**Search behavior:**
- At least one of QUERY or a filter flag is required
- Filters are applied first (cheap exact match), then text search
- Text search checks: body, type, owner, status, generates, dependencies, file_path
- Unparseable specs are silently skipped

**Text output:** Rich table with columns: File, Type, Status, Owner.

**JSON output:**
```json
[
  {
    "file": "src/auth/login.spec.md",
    "type": "utility",
    "status": "active",
    "owner": "@auth-team",
    "generates": "src/auth/login.py"
  }
]
```

**Exit codes:** 0 always (empty results are not an error), 1 if no query or filter provided.

---

### `status`

**Show a one-screen project status dashboard.**

```bash
speclord status [--root DIR]
```

Runs lint, check, and coverage in one command and displays a compact summary.

**Output sections:**
1. **Specs:** Total file spec count, breakdown by type and status
2. **Coverage:** Percentage with color (green/yellow/red)
3. **Last compile:** Timestamp of `registry.lock.json` modification, or "never"
4. **Lint:** Error/warning counts, or "All specs valid"
5. **Check:** Error/warning counts, or "All specs pass"

**Example output:**
```
Speclord Status

Specs: 12 file spec(s)
  By type: utility (7), api-endpoint (3), data-model (2)
  By status: active (10), draft (2)

Coverage: 85.7% (12/14 files)

Last compile: 2025-01-15 14:30

Lint: All specs valid
Check: 1 warning(s)
```

**Exit codes:** Always 0 (dashboard is informational).

---

### `drift`

**Analyze drift between specs and source code using AI.**

```bash
speclord drift <FILE> [--root DIR] [--format text|json] [--fail-on LEVEL]
speclord drift [--root DIR] [--format text|json] [--fail-on LEVEL]
```

| Argument / Option | Description |
|-------------------|-------------|
| `FILE` | Optional. Analyze a single spec. Without it, analyzes all specs. |
| `--fail-on` | `error`, `warning`, or `info`. Exit 1 if any finding at this level or higher. |

**Requires:** Claude Code CLI (`claude`) installed and authenticated.

**How it works:**
1. Parses the file spec and resolves the inheritance chain
2. Finds the corresponding code file (via `generates` field, or inferred from spec name)
3. Reads the code content
4. Sends spec + code + chain context to Claude for comparison
5. Claude returns structured findings with severity

**Code file location strategy:**
1. If `generates` is set: resolve relative to root, then relative to spec's parent
2. If not set: infer from spec name (`foo.spec.md` → try `foo.py`, `foo.ts`, `foo.js`, etc.)
3. Extensions tried: `.py`, `.ts`, `.js`, `.tsx`, `.jsx`, `.go`, `.rs`, `.rb`

**Finding severities:**
- `error` — code behavior contradicts the spec
- `warning` — code diverges from spec intent but may not be a bug
- `info` — minor discrepancy or style mismatch

**Text output (no findings):**
```
No drift detected — all specs match their code.
  src/auth/login.spec.md: Code matches spec.
```

**Text output (with findings):** Rich table with Severity, Spec, Section, Description.

**JSON output:**
```json
[
  {
    "spec": "src/auth/login.spec.md",
    "summary": "Minor drift in error handling.",
    "findings": [
      {
        "spec_section": "Edge Cases",
        "code_location": "line 42",
        "description": "Spec requires ValueError for empty input, but code raises TypeError",
        "severity": "error"
      }
    ]
  }
]
```

**`--fail-on` severity ladder:**
- `--fail-on error`: exit 1 only if error findings exist
- `--fail-on warning`: exit 1 if warning OR error findings exist
- `--fail-on info`: exit 1 if ANY finding exists

**Exit codes:** 0 on success, 1 if file not found, AI error, or `--fail-on` threshold met.

---

### `review`

**Review a spec file for quality using AI.**

```bash
speclord review <FILE> [--root DIR] [--format text|json]
```

**Requires:** Claude Code CLI.

**How it works:**
1. Parses the file spec (frontmatter + body)
2. Sends spec metadata and body to Claude for quality evaluation
3. Claude scores the spec 0–100 on clarity, completeness, and actionability
4. Returns specific improvement suggestions with priority

**Score ranges:**
- 80–100: green (good spec)
- 50–79: yellow (needs improvement)
- 0–49: red (incomplete or unclear)

**Score clamping:** Values from AI below 0 are clamped to 0, above 100 to 100.

**Text output:**
```
Review: src/auth/login.spec.md
Score: 85/100

Well-structured spec with clear interface definitions.

Suggestions (2):
  [high] Completeness: Add error handling section
  [medium] Clarity: Define AuthToken type
```

**JSON output:**
```json
{
  "spec": "src/auth/login.spec.md",
  "score": 85,
  "summary": "Well-structured spec with clear interface definitions.",
  "suggestions": [
    {
      "category": "Completeness",
      "suggestion": "Add error handling section",
      "priority": "high"
    }
  ]
}
```

**Suggestion priorities:** `high`, `medium`, `low`. Missing priority defaults to `medium`.

**Exit codes:** 0 on success, 1 if file not found or AI error.

---

### `draft`

**Draft a new spec file using AI.**

```bash
speclord draft <DESCRIPTION> <PATH> [--root DIR] [--from-code] [--type TYPE]
```

| Argument | Description |
|----------|-------------|
| `DESCRIPTION` | What the code file does or should do (free text) |
| `PATH` | Target location relative to root (e.g., `src/auth/login`) |

| Option | Description |
|--------|-------------|
| `--from-code` | Read the existing source file at PATH for context |
| `--type TYPE` | Override the spec type (e.g., `api-endpoint`) |

**Requires:** Claude Code CLI.

**How it works:**
1. If `--from-code`: finds and reads the source file at PATH (tries PATH directly, then with common extensions)
2. Finds a template matching the spec type for format guidance
3. Sends description + template + code context to Claude
4. Claude generates a complete spec with YAML frontmatter and markdown body
5. Writes the result to `<PATH>.spec.md`

**Template lookup order:**
1. `.spec/templates/<type>.spec.md` (project overrides)
2. Bundled templates in the speclord package
3. Falls back to `utility` type if no type specified

**Source file discovery (for `--from-code`):**
- Tries the exact path, then appends extensions: `.py`, `.ts`, `.js`, `.tsx`, `.jsx`, `.go`, `.rs`, `.java`, `.rb`

**Behavior:**
- If `<PATH>.spec.md` already exists, prints "already exists" and returns (won't overwrite)
- Creates parent directories as needed
- Uses `max_turns=25` (more than analysis commands) because generation needs more exploration

**Exit codes:** 0 on success, 1 if AI error.

---

### `migrate scan`

**Scan the codebase for spec coverage by directory.**

```bash
speclord migrate scan [--root DIR] [--format text|json]
```

Groups coverage by directory so you can see which areas of the codebase need specs.

**Text output:**
```
Migration Scan: 60.0% overall (3/5 files specced)

┌─────────────┬───────┬────────┬──────────┐
│ Directory   │ Files │ Specced│ Coverage │
├─────────────┼───────┼────────┼──────────┤
│ src/auth    │   3   │    2   │   66.7%  │
│ src/utils   │   2   │    1   │   50.0%  │
└─────────────┴───────┴────────┴──────────┘

2 file(s) need specs.
```

**JSON output:**
```json
{
  "total_files": 5,
  "specced_files": 3,
  "unspecced_files": 2,
  "by_directory": [
    {
      "directory": "src/auth",
      "total_files": 3,
      "specced_files": 2,
      "unspecced": ["src/auth/routes.py"]
    }
  ]
}
```

**Exit codes:** Always 0.

---

### `migrate plan`

**Generate a phased migration plan for unspecced files.**

```bash
speclord migrate plan [--root DIR] [--format text|json]
```

Analyzes the dependency graph to suggest which files should get specs first.

**Three phases:**
1. **Core** — modules that other specs depend on (foundational, should be specced first)
2. **Dependent** — modules that depend on core modules
3. **Leaf** — standalone modules with no dependency relationships

**Text output:**
```
Migration Plan: 5 file(s) across 3 phase(s)

Phase 1: Core — Foundational modules that other specs depend on
  src/types.py
  src/config.py

Phase 2: Dependent — Modules that depend on core modules
  src/auth/login.py

Phase 3: Leaf — Standalone modules
  src/utils.py
  src/helpers.py
```

If all files are specced: "All code files have specs — nothing to migrate."

**JSON output:**
```json
[
  {
    "phase": "Core",
    "description": "Foundational modules that other specs depend on",
    "files": ["src/types.py", "src/config.py"]
  }
]
```

**Exit codes:** Always 0.

---

### `migrate progress`

**Show migration progress compared to the last compile baseline.**

```bash
speclord migrate progress [--root DIR] [--format text|json]
```

Compares current spec coverage against `registry.lock.json` (created by `compile`) to show what has changed.

**Text output:**
```
Migration Progress: 75.0% (9/12 files)

Baseline: 7 spec(s)
Delta: +2

Remaining: 3 file(s) need specs

New specs (+2):
  + src/auth/routes.spec.md
  + src/utils/helpers.spec.md
```

If no baseline exists: suggests running `speclord compile` first.

**JSON output:**
```json
{
  "current_total": 12,
  "current_specced": 9,
  "current_pct": 75.0,
  "baseline_specced": 7,
  "has_baseline": true,
  "delta": 2,
  "remaining": 3,
  "new_specs": ["src/auth/routes.spec.md"],
  "removed_specs": []
}
```

**Exit codes:** Always 0.

---

### `migrate draft`

**Draft specs for all unspecced files using AI.**

```bash
speclord migrate draft [--root DIR] [--batch DIR] [--format text|json]
```

| Option | Description |
|--------|-------------|
| `--batch DIR` | Only draft specs for files in this directory (relative to root) |

**Requires:** Claude Code CLI.

**How it works:**
1. Scans the codebase for unspecced files (same logic as `coverage`)
2. For each unspecced file, calls `draft_spec` with `--from-code` (reads source)
3. Writes each drafted spec to `<source_name>.spec.md`
4. Reports success/failure for each file as it completes (streaming)

**Text output (streaming):**
```
  ✓ src/auth/routes.spec.md
  ✓ src/utils/helpers.spec.md
  ✗ src/config/secrets.py: AI error: ...

Done: 2 drafted, 1 failed
```

If all files already have specs: "All code files already have specs."

**JSON output:**
```json
{
  "drafted": 2,
  "failed": 1,
  "results": [
    {"source": "src/auth/routes.py", "spec": "src/auth/routes.spec.md", "success": true, "error": null},
    {"source": "src/config/secrets.py", "spec": "src/config/secrets.spec.md", "success": false, "error": "AI error: ..."}
  ]
}
```

**Behavior:**
- Skips files that already have a spec (won't overwrite)
- Continues processing even if individual files fail
- Uses `max_turns=25` for AI generation
- Creates parent directories as needed

**Exit codes:** Always 0 (individual failures are reported in output, not as exit codes).

---

## 7. AI Architecture

All AI commands use the **Claude Code CLI** in `--print` mode (non-interactive, single-shot). The architecture separates concerns:

### Adapter Interface

```python
class LLMAdapter(Protocol):
    def analyze(self, prompt: str, system: str, cwd: Path, schema: dict) -> dict:
        """Structured JSON output (drift, review)."""

    def generate(self, prompt: str, system: str, cwd: Path) -> str:
        """Free-form text output (draft)."""
```

Two implementations:
- **`ClaudeCodeAdapter`** — calls the real `claude` CLI via subprocess
- **`MockAdapter`** — records calls and returns canned responses (used in all tests)

### ClaudeCodeAdapter Details

```python
ClaudeCodeAdapter(model="sonnet", max_turns=10)
```

- **model:** Which Claude model to use. Default is `"sonnet"`.
- **max_turns:** Maximum conversation turns. Analysis commands use 10, generation commands use 25.
- **CLI command:** `claude --print --model <model> --max-turns <max_turns> --system-prompt <system>`
- **analyze():** Appends the JSON schema to the prompt, asks for JSON output, parses the response
- **generate():** Returns raw output (the spec content)

### Prompt Structure

Each AI command has a dedicated prompt builder in `ai/prompts.py`:

| Command | System Role | Output |
|---------|-------------|--------|
| `drift` | "Code Compliance Auditor" | JSON with `summary` + `findings[]` |
| `review` | "Specification Quality Reviewer" | JSON with `score` + `summary` + `suggestions[]` |
| `draft` | "Technical Specification Writer" | Raw spec file (YAML frontmatter + markdown) |

Prompts include:
- The full resolved spec chain (org → service → file)
- The source code content (for drift)
- Templates as format guides (for draft)
- JSON schema describing expected output structure (for analyze)

### Testing AI Commands

All AI tests use `MockAdapter`, which:
- Records every call (prompt, system, schema, cwd)
- Returns canned responses configured in the constructor
- Never makes real API calls or incurs costs

```python
adapter = MockAdapter(analyze_response={"score": 85, "summary": "Good.", "suggestions": []})
result = review_spec(spec_path, root, adapter)
assert adapter.analyze_calls[0]["prompt"]  # verify what was sent
```

---

## 8. Templates

Speclord ships with 4 bundled templates. After `speclord init`, they're copied to `.spec/templates/` where you can customize them.

### `utility.spec.md`

For general utility modules, helpers, shared functions.

```markdown
---
specVersion: "0.1.0"
inherits: "INHERITS_PATH"
type: "utility"
status: "draft"
owner: "OWNER"
priority: "normal"
dependencies: []
generates: "GENERATES_PATH"
---

## Purpose
## Exported Interface
## Behavior
## Edge Cases
## Testing Requirements
```

### `api-endpoint.spec.md`

For HTTP endpoints, REST routes.

```markdown
---
...same frontmatter with type: "api-endpoint"...
---

## Purpose
## Interface       ← HTTP method, path, request/response shapes
## Behavior        ← Step-by-step logic
## Edge Cases
## Testing Requirements
```

### `data-model.spec.md`

For database models, schemas, DTOs.

```markdown
---
...same frontmatter with type: "data-model"...
---

## Purpose
## Fields          ← Field name, type, required/optional, constraints
## Relationships   ← How this model relates to others
## Validation Rules
## Edge Cases
## Testing Requirements
```

### `service.spec.yaml`

For package-level conventions.

```yaml
specVersion: "0.1.0"
inherits: "INHERITS_PATH"
service: "SERVICE_NAME"
owner: "OWNER"
conventions:
  naming: "snake_case"
testing:
  framework: "pytest"
  coverage_target: 85
```

### Custom Templates

You can add custom templates to `.spec/templates/`. The `new` command looks there first. The template name must match the spec type: `<type>.spec.md` (e.g., `middleware.spec.md`).

Supported placeholders: `INHERITS_PATH`, `GENERATES_PATH`, `OWNER`, `SERVICE_NAME`.

---

## 9. Validation Rules Reference

These rules are checked by `speclord lint`. They validate spec **syntax**.

### File Spec Rules

| Rule | Severity | Condition |
|------|----------|-----------|
| `invalid-type` | error | `type` is not in the 15 valid spec types |
| `invalid-status` | error | `status` is not one of: draft, active, deprecated, archived |
| `missing-version` | error | `specVersion` is empty |
| `missing-inherits` | error | `inherits` is empty |
| `missing-owner` | error | `owner` is empty |
| `empty-body` | warning | Body has no `## Purpose` section |

### Service Spec Rules

| Rule | Severity | Condition |
|------|----------|-----------|
| `missing-version` | error | `specVersion` is empty |
| `missing-inherits` | error | `inherits` is empty |
| `missing-service` | error | `service` name is empty |
| `missing-owner` | error | `owner` is empty |

### Org Spec Rules

| Rule | Severity | Condition |
|------|----------|-----------|
| `missing-version` | error | `specVersion` is empty |
| `missing-organization` | error | `organization` is empty |
| `missing-stack` | warning | `stack` doesn't have `runtime` and `language` |
| `missing-security` | warning | `security` list is empty |

### Parse Error Handling

If a spec file cannot be parsed at all (invalid YAML, missing frontmatter delimiters, missing required fields), it's captured as a `parse-error` finding with error severity.

---

## 10. Structural Check Rules Reference

These rules are checked by `speclord check`. They validate spec **semantics** — whether references actually resolve to real files.

| Rule | Severity | Condition |
|------|----------|-----------|
| `missing-generates-target` | error | `generates` is set but the target file doesn't exist under root |
| `broken-dependency` | error | An entry in `dependencies` doesn't resolve to an existing `.spec.md` file |
| `active-empty-body` | warning | Status is `"active"` but the body is empty/whitespace-only |
| `missing-inherits-target` | error | The `inherits` path doesn't resolve to an existing file |

### Dependency Resolution Logic

For each dependency string:
1. If it ends with `.md` → use as-is (relative to spec's parent)
2. If it's a bare name (`"types"`) → resolve to `types.spec.md` in the same directory
3. Otherwise (`"../config"`) → append `.spec.md` and resolve relative to spec's parent

---

## 11. Data Types Reference

All types are defined in `src/speclord/types.py` as frozen dataclasses.

### Spec Types

| Type | Fields |
|------|--------|
| `FileSpec` | file_path, spec_version, inherits, type, owner, status, body, priority, dependencies, generates |
| `ServiceSpec` | file_path, spec_version, inherits, service, owner, conventions, dependencies, testing, security, infrastructure |
| `OrgSpec` | file_path, spec_version, organization, stack, patterns, security |

### Result Types

| Type | Fields | Used By |
|------|--------|---------|
| `LintFinding` | file_path, rule, message, severity | lint, check |
| `RegistryEntry` | path, hash, type, status, dependencies, generates | compile |
| `ResolvedChain` | file_spec, service_spec, org_spec | resolve, context |
| `CoverageReport` | total_files, specced_files, unspecced | coverage |
| `DepGraph` | adjacency: dict[str, list[str]] | deps |

### Migration Types

| Type | Fields | Used By |
|------|--------|---------|
| `DirScanEntry` | directory, total_files, specced_files, unspecced | migrate scan |
| `MigrationScan` | total_files, specced_files, unspecced_files, by_directory | migrate scan |
| `MigrationPhase` | name, description, files | migrate plan |
| `MigrationPlan` | phases: list[MigrationPhase] | migrate plan |
| `ProgressReport` | current_total, current_specced, baseline_specced, has_baseline, new_specs, removed_specs | migrate progress |

### AI Types

| Type | Fields | Used By |
|------|--------|---------|
| `DriftFinding` | spec_section, code_location, description, severity | drift |
| `DriftReport` | spec_path, summary, findings: list[DriftFinding] | drift |
| `ReviewSuggestion` | category, suggestion, priority | review |
| `SpecReview` | spec_path, score, summary, suggestions: list[ReviewSuggestion] | review |
| `DraftResult` | source_path, spec_path, success, error | migrate draft |

---

## 12. Error Types

All errors inherit from `SpeclordError`, which carries optional `filepath` and `suggestion` attributes.

| Error | Raised When |
|-------|-------------|
| `SpeclordError` | Base class for all speclord errors |
| `ParseError` | Spec file can't be parsed (bad YAML, missing fields, unreadable file) |
| `ValidationError` | Spec fails validation rules |
| `ResolutionError` | Inheritance chain can't be resolved (missing parent spec) |
| `ConfigError` | Config file is malformed or contains invalid values |
| `CycleError` | Dependency cycle detected in the spec graph. Carries `cycle: list[str]` |
| `AIError` | AI adapter call fails (Claude CLI not found, invalid response, subprocess error) |

---

## 13. Ignored Directories

Speclord skips these directories when discovering specs and scanning for coverage:

```
node_modules  .git      dist     build    coverage
.next         __pycache__  .venv   venv    .eggs
.mypy_cache   .pytest_cache  .ruff_cache  .spec
```

These are hardcoded in `parser.IGNORE_DIRS`. Additionally, the emitter skips `templates/` and `fixtures/` subdirectories.

---

## 14. Recipes & Workflows

### New Project Setup

```bash
# Initialize
speclord init --org mycompany

# Create service spec for your main package
speclord new service src/myapp

# Create file specs for existing code
speclord new utility src/myapp/models
speclord new api-endpoint src/myapp/routes
speclord new data-model src/myapp/schemas

# Fill in the spec bodies (edit the .spec.md files)

# Validate and compile
speclord lint
speclord compile

# Generate AI instructions
speclord emit claude
```

### Adopting Specs in an Existing Codebase

```bash
# 1. See the gap
speclord migrate scan

# 2. Get a plan
speclord migrate plan

# 3. Auto-draft specs for everything (requires Claude CLI)
speclord migrate draft

# 4. Review and edit the drafted specs
speclord lint
speclord check

# 5. Track progress over time
speclord compile              # establish baseline
# ... write more specs ...
speclord migrate progress     # see delta
```

### CI Pipeline Integration

```bash
# In your CI script:
speclord lint                     # fail on invalid specs
speclord check                    # fail on broken references
speclord coverage --min 80        # fail if coverage drops below 80%

# Optional AI checks (slower, costs money):
speclord drift --fail-on error    # fail if code contradicts specs
```

### Exploring a Project's Specs

```bash
# Dashboard view
speclord status

# Find all API specs
speclord search --type api-endpoint

# Find specs owned by a team
speclord search --owner "@auth-team"

# See what a spec inherits
speclord resolve src/auth/login.spec.md

# See the full context for an AI tool
speclord context src/auth/login.spec.md

# See dependency order
speclord deps
```

### Working with AI Tools

```bash
# Generate CLAUDE.md for Claude Code
speclord emit claude

# Preview what would be generated
speclord emit claude --dry-run

# Generate for all supported tools
speclord emit all

# Review a spec's quality before going active
speclord review src/auth/login.spec.md

# Check if code still matches the spec
speclord drift src/auth/login.spec.md

# Draft a spec from a description
speclord draft "Handles user authentication via JWT" src/auth/login

# Draft from existing code
speclord draft "User authentication" src/auth/login --from-code

# Draft as a specific type
speclord draft "REST API for users" src/api/users --type api-endpoint --from-code
```

### JSON Mode for Scripting

Every command with `--format` supports JSON for programmatic use:

```bash
# Parse coverage data
speclord coverage --format json | jq '.coverage_pct'

# Count lint errors
speclord lint --format json | jq '[.[] | select(.severity == "error")] | length'

# List unspecced files
speclord coverage --format json | jq '.unspecced[]'

# Get migration plan as data
speclord migrate plan --format json | jq '.[0].files'
```

---

## 15. Internal Architecture

### Module Map

```
src/speclord/
├── __init__.py           ← version (__version__ = "0.1.0")
├── cli.py                ← Click CLI entry point, all 16 commands
├── types.py              ← All dataclasses, Literal types, valid values
├── parser.py             ← YAML/frontmatter parsing, spec discovery
├── validator.py          ← Lint rules for all 3 spec tiers
├── resolver.py           ← Inheritance chain resolution
├── registry.py           ← Compile specs → registry.lock.json
├── hasher.py             ← SHA-256 content hashing
├── errors.py             ← Error hierarchy (7 types)
├── config.py             ← Config loading (.speclordrc.yaml / pyproject.toml)
├── context.py            ← Build AI-ready markdown from resolved chain
├── emitter.py            ← Generate CLAUDE.md / .cursorrules / copilot-instructions
├── coverage.py           ← Spec coverage analysis
├── checker.py            ← Structural integrity checks
├── deps.py               ← Dependency graph, topological sort, cycle detection
├── search.py             ← Text + field search across specs
├── templates/            ← Bundled spec templates (4 files)
├── ai/
│   ├── __init__.py
│   ├── adapter.py        ← LLMAdapter Protocol, MockAdapter, ClaudeCodeAdapter
│   ├── prompts.py        ← Prompt builders for drift, review, draft
│   ├── drift.py          ← Spec-to-code drift analysis
│   ├── review.py         ← Spec quality review
│   └── draft.py          ← AI-powered spec generation
└── migrate/
    ├── __init__.py
    ├── scanner.py        ← Codebase scan by directory
    ├── planner.py        ← 3-phase migration planning
    ├── progress.py       ← Baseline comparison
    └── drafter.py        ← Batch AI drafting
```

### Data Flow

```
                    ┌──────────────┐
                    │ parser.py    │ → FileSpec, ServiceSpec, OrgSpec
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
     ┌────────▼──────┐  ┌─▼──────┐  ┌──▼────────┐
     │ validator.py  │  │resolver│  │ registry   │
     │ (lint rules)  │  │.py     │  │ .py        │
     └───────────────┘  └─┬──────┘  └────────────┘
                          │
              ┌───────────┼──────────────┐
              │           │              │
     ┌────────▼──────┐  ┌▼──────────┐  ┌▼────────────┐
     │ context.py    │  │ emitter   │  │ ai/prompts   │
     │ (AI context)  │  │ .py       │  │ .py          │
     └───────────────┘  └───────────┘  └──────┬───────┘
                                              │
                                    ┌─────────▼────────┐
                                    │  ai/adapter.py   │
                                    │  (Claude Code)   │
                                    └──────────────────┘
```

### CLI Design Patterns

- **Lazy imports:** Only `click`, `rich`, `sys`, `pathlib`, and `__version__` are imported at module level. Everything else is imported inside command functions to keep `--help` fast.
- **`_resolve_root()`:** Every command calls this to resolve the effective root from CLI flag + config file.
- **`TYPE_CHECKING` guard:** Type-only imports use `if TYPE_CHECKING:` to avoid circular imports and keep startup fast.
- **Dual output:** Most commands support `--format text` (Rich tables/trees) and `--format json` (machine-readable).
- **Exit codes:** Error findings → exit 1. Warnings alone → exit 0. Informational commands → always exit 0.

### Test Structure

```
tests/
├── test_checker.py          ← 16 tests (check rules + CLI)
├── test_cli.py              ← CLI integration tests
├── test_config.py           ← Config loading tests
├── test_context.py          ← Context builder tests
├── test_coverage.py         ← Coverage analysis tests
├── test_deps.py             ← Dependency graph tests
├── test_draft.py            ← 21 tests (draft API + CLI)
├── test_drift.py            ← 29 tests (drift analysis + CLI)
├── test_e2e.py              ← 6 end-to-end integration tests
├── test_emitter.py          ← Emitter tests
├── test_errors.py           ← Error type tests
├── test_hasher.py           ← Hash function tests
├── test_init_new.py         ← Init + new command tests
├── test_migrate_drafter.py  ← 17 tests (batch draft)
├── test_migrate_planner.py  ← Migration planner tests
├── test_migrate_progress.py ← Progress tracker tests
├── test_migrate_scanner.py  ← Scanner tests
├── test_parser.py           ← Parser tests
├── test_registry.py         ← Registry compilation tests
├── test_resolve_cmd.py      ← Resolve command tests
├── test_resolver.py         ← Chain resolution tests
├── test_review.py           ← 21 tests (review API + CLI)
├── test_search.py           ← Search engine tests
├── test_status.py           ← Status dashboard tests
├── test_types.py            ← Type validation tests
└── test_validator.py        ← Lint rule tests
```

**454 tests total.** All pass. All AI tests use `MockAdapter` — zero API calls, zero cost.

---

*Generated for speclord v0.1.0*
