---
specVersion: "0.1.0"
inherits: ".spec.yaml"
type: "utility"
status: "active"
owner: "@speclord-team"
generates: "src/speclord/validator.py"
dependencies:
  - "src/speclord/parser.spec.md"
  - "src/speclord/types.spec.md"
---

## Purpose

Validate spec files against schema rules. Powers the `speclord lint` command.

## Exported Interface

- `validate_file_spec(spec) -> list[LintFinding]`
- `validate_service_spec(spec) -> list[LintFinding]`
- `validate_org_spec(spec) -> list[LintFinding]`
- `lint_all(root) -> list[LintFinding]`

## Behavior

- Checks required fields, valid types/statuses, non-empty bodies
- Returns findings with severity (error, warning, info) — never raises
- `lint_all` discovers + parses + validates all specs under root
