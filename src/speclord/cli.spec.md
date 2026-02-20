---
specVersion: "0.1.0"
inherits: ".spec.yaml"
type: "cli-command"
status: "active"
owner: "@speclord-team"
priority: "high"
generates: "src/speclord/cli.py"
dependencies:
  - "src/speclord/validator.spec.md"
  - "src/speclord/registry.spec.md"
  - "src/speclord/context.spec.md"
  - "src/speclord/emitter.spec.md"
  - "src/speclord/resolver.spec.md"
  - "src/speclord/config.spec.md"
---

## Purpose

Main CLI entry point using Click. Registers all subcommands and wires them to library functions.

## Commands

- `lint` — validate all spec files
- `compile` — build registry.lock.json
- `init` — scaffold .spec/ structure
- `new <type> <path>` — create spec from template
- `context <file>` — build AI-ready context from spec chain
- `resolve <file>` — show resolved inheritance chain
- `emit <target>` — generate AI tool instruction files

## Behavior

- Lazy-imports library modules inside each command function
- Uses `_resolve_root()` helper for consistent root/config resolution
- Rich console for styled output; `click.echo()` for pipeable stdout
