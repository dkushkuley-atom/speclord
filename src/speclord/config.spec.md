---
specVersion: "0.1.0"
inherits: ".spec.yaml"
type: "utility"
status: "active"
owner: "@speclord-team"
generates: "src/speclord/config.py"
dependencies:
  - "src/speclord/errors.spec.md"
---

## Purpose

Load and merge configuration from .speclordrc.yaml or pyproject.toml [tool.speclord].

## Exported Interface

- `SpeclordConfig` — dataclass with all config fields
- `load_config(root) -> SpeclordConfig`

## Behavior

- Precedence: .speclordrc.yaml > pyproject.toml [tool.speclord] > defaults
- Validates types; raises `ConfigError` on invalid config
- Returns defaults if no config file found (not an error)
