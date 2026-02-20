# speclord

The spec layer for AI-assisted development.

Specs are the source of truth: human-readable markdown files describing what every piece of code should do. Speclord provides context to AI tools (Claude Code, Cursor, Copilot), enforces compliance, and catches drift between specs and code.

```
pip install speclord
speclord emit claude   # instant CLAUDE.md from your spec hierarchy
```

## Quick Start

### 1. Initialize your project

```bash
speclord init --org mycompany
```

This creates a `.spec/` directory with templates and an `org.spec.yaml` at the repo root.

### 2. Create specs for your code

```bash
# Service-level spec for a package
speclord new service src/auth

# File-level specs for individual modules
speclord new utility src/auth/login
speclord new api-endpoint src/auth/routes
```

### 3. Validate and compile

```bash
speclord lint                  # validate all specs
speclord compile               # build registry.lock.json
speclord check                 # structural integrity checks
```

### 4. Generate AI instructions

```bash
speclord emit claude           # writes CLAUDE.md
speclord emit claude --dry-run # preview without writing
```

### 5. Check coverage

```bash
speclord coverage              # see which files lack specs
speclord coverage --min 80     # fail CI if below 80%
```

## Spec Format

Speclord uses a three-tier hierarchical spec system. Each level inherits from and constrains the level below.

### Org Spec (`org.spec.yaml`)

Lives at the repo root. Organization-wide constraints that apply to every spec.

```yaml
specVersion: "0.1.0"
org: "mycompany"
standards:
  naming: "snake_case"
  testing: "pytest"
```

### Service Spec (`.spec.yaml`)

Lives in package directories. Package-level conventions.

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
```

### File Spec (`.spec.md`)

Lives next to code files. YAML frontmatter + markdown body describing the contract for a single file.

```markdown
---
specVersion: "0.1.0"
inherits: ".spec.yaml"
type: "utility"
status: "active"
owner: "@auth-team"
priority: "normal"
dependencies: ["../types"]
generates: "src/auth/login.py"
---

## Purpose

Handles user authentication via username/password.

## Exported Interface

- `login(username: str, password: str) -> AuthToken`
- `logout(token: AuthToken) -> None`

## Behavior

1. Validate credentials against the user store
2. Return a signed JWT on success
3. Raise `AuthError` on invalid credentials

## Edge Cases

- Empty username/password: raise `ValueError`
- Expired token on logout: silently succeed

## Testing Requirements

- Unit tests for valid/invalid credentials
- Integration test with mock user store
```

### Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `specVersion` | yes | Spec format version (currently `"0.1.0"`) |
| `inherits` | yes | Path to parent spec (service or org) |
| `type` | yes | Spec type (see below) |
| `status` | yes | Lifecycle status |
| `owner` | yes | Team or person responsible |
| `priority` | no | `"low"`, `"normal"`, `"high"`, `"critical"` |
| `dependencies` | no | List of spec paths this file depends on |
| `generates` | no | Path to the code file this spec describes |

### Spec Types

`api-endpoint`, `data-model`, `utility`, `middleware`, `config`, `integration`, `event-handler`, `job`, `migration`, `cli-command`, `service`, `hook`, `decorator`, `model`, `schema`

### Spec Statuses

`draft` - `active` - `deprecated` - `archived`

## Command Reference

### Core Commands

#### `speclord init`

Initialize a `.spec/` structure in the project.

```bash
speclord init [--root DIR] [--org NAME]
```

#### `speclord new`

Scaffold a new spec file from a template.

```bash
speclord new <type> <path> [--root DIR]
# type: utility, api-endpoint, data-model, service
```

#### `speclord lint`

Validate all spec files.

```bash
speclord lint [--root DIR] [--format text|json]
```

#### `speclord compile`

Build the spec registry (`registry.lock.json`).

```bash
speclord compile [--root DIR]
```

#### `speclord check`

Run structural integrity checks (missing targets, broken dependencies, empty active specs).

```bash
speclord check [FILE] [--root DIR] [--format text|json]
```

Exit code 1 if any error-severity findings.

#### `speclord coverage`

Find code files without specs.

```bash
speclord coverage [--root DIR] [--format text|json] [--min PERCENT]
```

#### `speclord resolve`

Show the resolved inheritance chain for a spec.

```bash
speclord resolve <FILE> [--root DIR] [--format text|json]
```

#### `speclord context`

Build AI-ready context from the spec chain.

```bash
speclord context <FILE> [--root DIR]
speclord context --batch "src/*.spec.md" [--root DIR]
```

#### `speclord emit`

Generate AI tool instruction files from the spec hierarchy.

```bash
speclord emit claude [--root DIR] [--dry-run]
```

#### `speclord deps`

Show the dependency graph.

```bash
speclord deps [FILE] [--root DIR] [--format text|json]
```

#### `speclord search`

Search specs by text and/or field filters.

```bash
speclord search <QUERY> [--root DIR] [--format text|json]
speclord search --type utility [--root DIR] [--format text|json]
```

#### `speclord status`

One-screen project dashboard: coverage, lint, and check summary.

```bash
speclord status [--root DIR]
```

### AI Commands

These commands use Claude Code under the hood.

#### `speclord drift`

Analyze drift between specs and source code.

```bash
speclord drift <FILE> [--root DIR] [--format text|json] [--fail-on error|warning|info]
```

#### `speclord review`

Review a spec file for quality.

```bash
speclord review <FILE> [--root DIR] [--format text|json]
```

#### `speclord draft`

Draft a new spec file using AI.

```bash
speclord draft <DESCRIPTION> <PATH> [--root DIR] [--from-code] [--type TYPE]
```

### Migration Commands

Tools for adopting specs across an existing codebase.

#### `speclord migrate scan`

Scan the codebase to find unspecced files.

```bash
speclord migrate scan [--root DIR] [--format text|json]
```

#### `speclord migrate plan`

Generate a phased migration plan.

```bash
speclord migrate plan [--root DIR] [--format text|json]
```

#### `speclord migrate progress`

Track migration progress.

```bash
speclord migrate progress [--root DIR]
```

#### `speclord migrate draft`

Batch-draft specs for all unspecced files using AI.

```bash
speclord migrate draft [--root DIR] [--batch DIR] [--format text|json]
```

## Configuration

Speclord looks for configuration in two places (first match wins):

1. `.speclordrc.yaml` in the project root
2. `[tool.speclord]` section in `pyproject.toml`

### `.speclordrc.yaml`

```yaml
coverage:
  extensions: [".py"]
  ignore:
    - "migrations/*"
    - "tests/*"

defaults:
  owner: "@myteam"
  status: "draft"

emit:
  targets: ["claude"]
```

### `pyproject.toml`

```toml
[tool.speclord]

[tool.speclord.coverage]
extensions = [".py"]
ignore = ["migrations/*", "tests/*"]

[tool.speclord.defaults]
owner = "@myteam"
status = "draft"

[tool.speclord.emit]
targets = ["claude"]
```

### Config Options

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `coverage.extensions` | list[str] | `[".py"]` | File extensions to track for coverage |
| `coverage.ignore` | list[str] | `[]` | Glob patterns to exclude from coverage |
| `defaults.owner` | str | `null` | Default owner for scaffolded specs |
| `defaults.status` | str | `"draft"` | Default status for scaffolded specs |
| `emit.targets` | list[str] | `["claude"]` | Targets for the `emit` command |

## Typical Workflow

```
1. speclord init              # one-time setup
2. speclord new ...           # create specs as you build
3. speclord lint              # validate specs
4. speclord compile           # build registry
5. speclord emit claude       # generate CLAUDE.md
6. speclord coverage --min 80 # enforce in CI
7. speclord drift <file>      # catch spec/code divergence
```

## Requirements

- Python 3.10+
- For AI commands (`drift`, `review`, `draft`): [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI installed and authenticated

## License

MIT
