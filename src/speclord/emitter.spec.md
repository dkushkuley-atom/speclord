---
specVersion: "0.1.0"
inherits: ".spec.yaml"
type: "utility"
status: "active"
owner: "@speclord-team"
generates: "src/speclord/emitter.py"
dependencies:
  - "src/speclord/parser.spec.md"
  - "src/speclord/types.spec.md"
---

## Purpose

Generate AI tool instruction files (CLAUDE.md, .cursorrules, copilot-instructions.md) from the spec hierarchy.

## Exported Interface

- `emit(root, target) -> str` — build content for a target
- `write_target(root, target) -> Path` — write to disk
- `output_path(root, target) -> Path` — get output path
- `TARGET_PATHS` — target → filename mapping

## Behavior

- Discovers all specs, categorizes into org/service/file
- Builds a project-wide markdown summary with org constraints, service sections, and specs table
- All targets use identical markdown content; only output path differs
