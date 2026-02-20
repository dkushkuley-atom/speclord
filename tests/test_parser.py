"""Tests for spec file parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from speclord.errors import ParseError
from speclord.parser import discover_specs, parse_file_spec, parse_org_spec, parse_service_spec


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def valid_repo(fixtures_dir: Path) -> Path:
    return fixtures_dir / "valid-repo"


class TestParseFileSpec:
    def test_parses_valid_spec(self, valid_repo: Path) -> None:
        path = valid_repo / "packages/auth/src/handler.spec.md"
        spec = parse_file_spec(path)
        assert spec.spec_version == "0.1.0"
        assert spec.inherits == "../.spec.yaml"
        assert spec.type == "api-endpoint"
        assert spec.owner == "@auth-team"
        assert spec.status == "active"
        assert spec.priority == "high"
        assert spec.generates == "packages/auth/src/handler.py"
        assert "## Purpose" in spec.body
        assert "authentication" in spec.body.lower()

    def test_dependencies_list(self, valid_repo: Path) -> None:
        path = valid_repo / "packages/auth/src/handler.spec.md"
        spec = parse_file_spec(path)
        assert spec.dependencies == []

    def test_missing_file_raises(self) -> None:
        with pytest.raises(ParseError, match="Cannot read file"):
            parse_file_spec(Path("/nonexistent/file.spec.md"))

    def test_missing_required_field(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "bad.spec.md"
        spec_file.write_text("---\nspecVersion: '0.1.0'\n---\nBody\n")
        with pytest.raises(ParseError, match="Missing required field: inherits"):
            parse_file_spec(spec_file)

    def test_no_frontmatter(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "no-fm.spec.md"
        spec_file.write_text("Just plain markdown\n")
        with pytest.raises(ParseError, match="Missing required field"):
            parse_file_spec(spec_file)

    def test_empty_body(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "empty.spec.md"
        spec_file.write_text(
            '---\nspecVersion: "0.1.0"\ninherits: ".spec.yaml"\n'
            'type: "utility"\nowner: "@team"\nstatus: "draft"\n---\n'
        )
        spec = parse_file_spec(spec_file)
        assert spec.body == ""

    def test_default_priority(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "defaults.spec.md"
        spec_file.write_text(
            '---\nspecVersion: "0.1.0"\ninherits: ".spec.yaml"\n'
            'type: "utility"\nowner: "@team"\nstatus: "draft"\n---\nBody\n'
        )
        spec = parse_file_spec(spec_file)
        assert spec.priority == "normal"
        assert spec.generates is None


class TestParseServiceSpec:
    def test_parses_valid_service(self, valid_repo: Path) -> None:
        path = valid_repo / "packages/auth/.spec.yaml"
        spec = parse_service_spec(path)
        assert spec.spec_version == "0.1.0"
        assert spec.inherits == "../../org.spec.yaml"
        assert spec.service == "auth"
        assert spec.owner == "@auth-team"
        assert spec.conventions["naming"] == "snake_case"
        assert spec.testing["coverage_target"] == 90

    def test_missing_file_raises(self) -> None:
        with pytest.raises(ParseError, match="Cannot read file"):
            parse_service_spec(Path("/nonexistent/.spec.yaml"))

    def test_missing_required_field(self, tmp_path: Path) -> None:
        spec_file = tmp_path / ".spec.yaml"
        spec_file.write_text('specVersion: "0.1.0"\n')
        with pytest.raises(ParseError, match="Missing required field: inherits"):
            parse_service_spec(spec_file)

    def test_empty_conventions(self, tmp_path: Path) -> None:
        spec_file = tmp_path / ".spec.yaml"
        spec_file.write_text(
            'specVersion: "0.1.0"\ninherits: "org.spec.yaml"\n'
            'service: "core"\nowner: "@team"\n'
        )
        spec = parse_service_spec(spec_file)
        assert spec.conventions == {}
        assert spec.testing == {}
        assert spec.security == []


class TestParseOrgSpec:
    def test_parses_valid_org(self, valid_repo: Path) -> None:
        path = valid_repo / "org.spec.yaml"
        spec = parse_org_spec(path)
        assert spec.spec_version == "0.1.0"
        assert spec.organization == "test-org"
        assert spec.stack["runtime"] == "python"
        assert spec.patterns["naming"] == "snake_case"
        assert len(spec.security) == 2

    def test_missing_file_raises(self) -> None:
        with pytest.raises(ParseError, match="Cannot read file"):
            parse_org_spec(Path("/nonexistent/org.spec.yaml"))

    def test_missing_required_field(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "org.spec.yaml"
        spec_file.write_text('specVersion: "0.1.0"\n')
        with pytest.raises(ParseError, match="Missing required field: organization"):
            parse_org_spec(spec_file)

    def test_minimal_org(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "org.spec.yaml"
        spec_file.write_text('specVersion: "0.1.0"\norganization: "acme"\n')
        spec = parse_org_spec(spec_file)
        assert spec.organization == "acme"
        assert spec.stack == {}
        assert spec.security == []

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "org.spec.yaml"
        spec_file.write_text("{{not: valid: yaml")
        with pytest.raises(ParseError, match="Invalid YAML"):
            parse_org_spec(spec_file)

    def test_non_mapping_yaml(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "org.spec.yaml"
        spec_file.write_text("- just\n- a\n- list\n")
        with pytest.raises(ParseError, match="Expected a YAML mapping"):
            parse_org_spec(spec_file)


class TestDiscoverSpecs:
    def test_finds_all_specs(self, valid_repo: Path) -> None:
        specs = discover_specs(valid_repo)
        names = [p.name for p in specs]
        assert "org.spec.yaml" in names
        assert ".spec.yaml" in names
        assert "handler.spec.md" in names

    def test_returns_paths(self, valid_repo: Path) -> None:
        specs = discover_specs(valid_repo)
        assert all(isinstance(p, Path) for p in specs)
        assert len(specs) >= 3

    def test_empty_dir(self, tmp_path: Path) -> None:
        specs = discover_specs(tmp_path)
        assert specs == []

    def test_ignores_node_modules(self, tmp_path: Path) -> None:
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "something.spec.md").write_text("---\n---\n")
        specs = discover_specs(tmp_path)
        assert specs == []

    def test_ignores_venv(self, tmp_path: Path) -> None:
        venv = tmp_path / ".venv" / "lib"
        venv.mkdir(parents=True)
        (venv / "something.spec.md").write_text("---\n---\n")
        specs = discover_specs(tmp_path)
        assert specs == []
