"""Speclord project configuration loading."""

from __future__ import annotations

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from speclord.errors import ConfigError


@dataclass
class SpeclordConfig:
    """Resolved configuration for a speclord invocation."""

    root: str = "."
    coverage_extensions: list[str] = field(default_factory=lambda: [".py"])
    coverage_ignore: list[str] = field(default_factory=list)
    defaults_owner: str | None = None
    defaults_status: str = "draft"
    emit_targets: list[str] = field(default_factory=lambda: ["claude"])


def load_config(root: Path) -> SpeclordConfig:
    """Load speclord config from .speclordrc.yaml or pyproject.toml.

    Returns SpeclordConfig with defaults if no config file is found.
    Raises ConfigError if a config file exists but cannot be parsed.
    """
    rc_path = root / ".speclordrc.yaml"
    if rc_path.exists():
        return _load_from_yaml_rc(rc_path)

    pyproject_path = root / "pyproject.toml"
    if pyproject_path.exists():
        return _load_from_pyproject(pyproject_path)

    return SpeclordConfig()


def _load_from_yaml_rc(path: Path) -> SpeclordConfig:
    """Load config from a .speclordrc.yaml file."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ConfigError(
            f"Cannot read config file: {e}",
            filepath=str(path),
        ) from e

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ConfigError(
            f"Invalid YAML in config file: {e}",
            filepath=str(path),
            suggestion="Fix the YAML syntax in .speclordrc.yaml",
        ) from e

    if data is None:
        return SpeclordConfig()

    if not isinstance(data, dict):
        raise ConfigError(
            "Config file must be a YAML mapping",
            filepath=str(path),
            suggestion="The top level of .speclordrc.yaml must be key-value pairs",
        )

    return _parse_config_dict(data, filepath=str(path))


def _load_from_pyproject(path: Path) -> SpeclordConfig:
    """Load config from the [tool.speclord] section of pyproject.toml."""
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except OSError as e:
        raise ConfigError(
            f"Cannot read pyproject.toml: {e}",
            filepath=str(path),
        ) from e
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(
            f"Invalid TOML in pyproject.toml: {e}",
            filepath=str(path),
            suggestion="Fix the TOML syntax in pyproject.toml",
        ) from e

    speclord_section = data.get("tool", {}).get("speclord", {})
    if not speclord_section:
        return SpeclordConfig()

    return _parse_config_dict(speclord_section, filepath=str(path))


def _parse_config_dict(data: dict[str, Any], *, filepath: str) -> SpeclordConfig:
    """Parse a raw config dict into SpeclordConfig.

    Raises ConfigError for type violations. Unknown keys are silently ignored.
    """
    cfg = SpeclordConfig()

    if "root" in data:
        if not isinstance(data["root"], str):
            raise ConfigError("'root' must be a string", filepath=filepath)
        cfg.root = data["root"]

    coverage = data.get("coverage", {})
    if not isinstance(coverage, dict):
        raise ConfigError("'coverage' must be a mapping", filepath=filepath)

    if "extensions" in coverage:
        val = coverage["extensions"]
        if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
            raise ConfigError(
                "'coverage.extensions' must be a list of strings", filepath=filepath
            )
        cfg.coverage_extensions = val

    if "ignore" in coverage:
        val = coverage["ignore"]
        if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
            raise ConfigError(
                "'coverage.ignore' must be a list of strings", filepath=filepath
            )
        cfg.coverage_ignore = val

    defaults = data.get("defaults", {})
    if not isinstance(defaults, dict):
        raise ConfigError("'defaults' must be a mapping", filepath=filepath)

    if "owner" in defaults:
        if not isinstance(defaults["owner"], str):
            raise ConfigError("'defaults.owner' must be a string", filepath=filepath)
        cfg.defaults_owner = defaults["owner"]

    if "status" in defaults:
        if not isinstance(defaults["status"], str):
            raise ConfigError("'defaults.status' must be a string", filepath=filepath)
        cfg.defaults_status = defaults["status"]

    emit = data.get("emit", {})
    if not isinstance(emit, dict):
        raise ConfigError("'emit' must be a mapping", filepath=filepath)

    if "targets" in emit:
        val = emit["targets"]
        if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
            raise ConfigError(
                "'emit.targets' must be a list of strings", filepath=filepath
            )
        cfg.emit_targets = val

    return cfg
