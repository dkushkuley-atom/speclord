"""Tests for config loading and merging."""

from __future__ import annotations

from pathlib import Path

import pytest

from speclord.config import SpeclordConfig, load_config
from speclord.errors import ConfigError


class TestSpeclordConfigDefaults:
    def test_default_root(self) -> None:
        cfg = SpeclordConfig()
        assert cfg.root == "."

    def test_default_coverage_extensions(self) -> None:
        cfg = SpeclordConfig()
        assert cfg.coverage_extensions == [".py"]

    def test_default_coverage_ignore(self) -> None:
        cfg = SpeclordConfig()
        assert cfg.coverage_ignore == []

    def test_default_owner_is_none(self) -> None:
        cfg = SpeclordConfig()
        assert cfg.defaults_owner is None

    def test_default_status(self) -> None:
        cfg = SpeclordConfig()
        assert cfg.defaults_status == "draft"

    def test_default_emit_targets(self) -> None:
        cfg = SpeclordConfig()
        assert cfg.emit_targets == ["claude"]

    def test_mutable_defaults_are_independent(self) -> None:
        a = SpeclordConfig()
        b = SpeclordConfig()
        a.coverage_extensions.append(".ts")
        assert b.coverage_extensions == [".py"]


class TestLoadConfigNoFile:
    def test_no_config_returns_defaults(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path)
        assert cfg == SpeclordConfig()

    def test_no_config_is_not_an_error(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path)
        assert cfg is not None


class TestLoadConfigFromYaml:
    def test_loads_root(self, tmp_path: Path) -> None:
        (tmp_path / ".speclordrc.yaml").write_text("root: src\n")
        cfg = load_config(tmp_path)
        assert cfg.root == "src"

    def test_loads_coverage_extensions(self, tmp_path: Path) -> None:
        (tmp_path / ".speclordrc.yaml").write_text(
            "coverage:\n  extensions: [.py, .ts]\n"
        )
        cfg = load_config(tmp_path)
        assert cfg.coverage_extensions == [".py", ".ts"]

    def test_loads_coverage_ignore(self, tmp_path: Path) -> None:
        (tmp_path / ".speclordrc.yaml").write_text(
            "coverage:\n  ignore:\n    - tests/**\n    - docs/**\n"
        )
        cfg = load_config(tmp_path)
        assert cfg.coverage_ignore == ["tests/**", "docs/**"]

    def test_loads_defaults_owner(self, tmp_path: Path) -> None:
        (tmp_path / ".speclordrc.yaml").write_text("defaults:\n  owner: '@platform'\n")
        cfg = load_config(tmp_path)
        assert cfg.defaults_owner == "@platform"

    def test_loads_defaults_status(self, tmp_path: Path) -> None:
        (tmp_path / ".speclordrc.yaml").write_text("defaults:\n  status: active\n")
        cfg = load_config(tmp_path)
        assert cfg.defaults_status == "active"

    def test_loads_emit_targets(self, tmp_path: Path) -> None:
        (tmp_path / ".speclordrc.yaml").write_text(
            "emit:\n  targets: [claude, cursor]\n"
        )
        cfg = load_config(tmp_path)
        assert cfg.emit_targets == ["claude", "cursor"]

    def test_empty_yaml_returns_defaults(self, tmp_path: Path) -> None:
        (tmp_path / ".speclordrc.yaml").write_text("")
        cfg = load_config(tmp_path)
        assert cfg == SpeclordConfig()

    def test_partial_config_fills_remaining_defaults(self, tmp_path: Path) -> None:
        (tmp_path / ".speclordrc.yaml").write_text("root: myproject\n")
        cfg = load_config(tmp_path)
        assert cfg.root == "myproject"
        assert cfg.coverage_extensions == [".py"]
        assert cfg.defaults_owner is None

    def test_invalid_yaml_raises_config_error(self, tmp_path: Path) -> None:
        (tmp_path / ".speclordrc.yaml").write_text("{{not: valid: yaml")
        with pytest.raises(ConfigError, match="Invalid YAML"):
            load_config(tmp_path)

    def test_non_mapping_yaml_raises_config_error(self, tmp_path: Path) -> None:
        (tmp_path / ".speclordrc.yaml").write_text("- just\n- a\n- list\n")
        with pytest.raises(ConfigError, match="must be a YAML mapping"):
            load_config(tmp_path)

    def test_wrong_type_for_root_raises(self, tmp_path: Path) -> None:
        (tmp_path / ".speclordrc.yaml").write_text("root: 42\n")
        with pytest.raises(ConfigError, match="'root' must be a string"):
            load_config(tmp_path)

    def test_wrong_type_for_extensions_raises(self, tmp_path: Path) -> None:
        (tmp_path / ".speclordrc.yaml").write_text(
            "coverage:\n  extensions: not-a-list\n"
        )
        with pytest.raises(ConfigError, match="'coverage.extensions' must be a list"):
            load_config(tmp_path)

    def test_wrong_type_for_coverage_raises(self, tmp_path: Path) -> None:
        (tmp_path / ".speclordrc.yaml").write_text("coverage: not-a-mapping\n")
        with pytest.raises(ConfigError, match="'coverage' must be a mapping"):
            load_config(tmp_path)

    def test_wrong_type_for_defaults_raises(self, tmp_path: Path) -> None:
        (tmp_path / ".speclordrc.yaml").write_text("defaults: not-a-mapping\n")
        with pytest.raises(ConfigError, match="'defaults' must be a mapping"):
            load_config(tmp_path)

    def test_wrong_type_for_emit_raises(self, tmp_path: Path) -> None:
        (tmp_path / ".speclordrc.yaml").write_text("emit: not-a-mapping\n")
        with pytest.raises(ConfigError, match="'emit' must be a mapping"):
            load_config(tmp_path)

    def test_unknown_keys_are_ignored(self, tmp_path: Path) -> None:
        (tmp_path / ".speclordrc.yaml").write_text(
            "root: .\nfuture_option: something\n"
        )
        cfg = load_config(tmp_path)
        assert cfg.root == "."


class TestLoadConfigFromPyproject:
    def test_loads_from_tool_speclord(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[tool.speclord]\nroot = "src"\n')
        cfg = load_config(tmp_path)
        assert cfg.root == "src"

    def test_pyproject_without_tool_speclord_returns_defaults(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'
        )
        cfg = load_config(tmp_path)
        assert cfg == SpeclordConfig()

    def test_loads_coverage_section(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.speclord]\n"
            "[tool.speclord.coverage]\n"
            'extensions = [".py", ".ts"]\n'
            'ignore = ["tests/**"]\n'
        )
        cfg = load_config(tmp_path)
        assert cfg.coverage_extensions == [".py", ".ts"]
        assert cfg.coverage_ignore == ["tests/**"]

    def test_loads_defaults_section(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.speclord.defaults]\n"
            'owner = "@backend"\n'
            'status = "active"\n'
        )
        cfg = load_config(tmp_path)
        assert cfg.defaults_owner == "@backend"
        assert cfg.defaults_status == "active"

    def test_loads_emit_section(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.speclord.emit]\n"
            'targets = ["claude", "cursor", "copilot"]\n'
        )
        cfg = load_config(tmp_path)
        assert cfg.emit_targets == ["claude", "cursor", "copilot"]

    def test_invalid_toml_raises_config_error(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("not = valid = toml [[\n")
        with pytest.raises(ConfigError, match="Invalid TOML"):
            load_config(tmp_path)


class TestConfigPrecedence:
    def test_yaml_rc_wins_over_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / ".speclordrc.yaml").write_text("root: from-yaml\n")
        (tmp_path / "pyproject.toml").write_text('[tool.speclord]\nroot = "from-toml"\n')
        cfg = load_config(tmp_path)
        assert cfg.root == "from-yaml"

    def test_pyproject_used_when_no_yaml_rc(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[tool.speclord]\nroot = "from-toml"\n')
        cfg = load_config(tmp_path)
        assert cfg.root == "from-toml"
