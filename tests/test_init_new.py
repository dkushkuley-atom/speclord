"""Tests for init and new commands."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from speclord.cli import main


class TestInit:
    def test_creates_spec_dir(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / ".spec").is_dir()
        assert (tmp_path / ".spec" / "templates").is_dir()

    def test_creates_org_spec(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--root", str(tmp_path), "--org", "acme"])
        assert result.exit_code == 0
        org = tmp_path / "org.spec.yaml"
        assert org.exists()
        content = org.read_text()
        assert "acme" in content
        assert "specVersion" in content

    def test_copies_templates(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(main, ["init", "--root", str(tmp_path)])
        templates = list((tmp_path / ".spec" / "templates").iterdir())
        assert len(templates) >= 3
        names = [t.name for t in templates]
        assert "api-endpoint.spec.md" in names
        assert "utility.spec.md" in names
        assert "service.spec.yaml" in names

    def test_idempotent(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(main, ["init", "--root", str(tmp_path)])
        result = runner.invoke(main, ["init", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "already exists" in result.output.lower()

    def test_does_not_overwrite_existing_org_spec(self, tmp_path: Path) -> None:
        org = tmp_path / "org.spec.yaml"
        org.write_text("custom: true\n")
        runner = CliRunner()
        runner.invoke(main, ["init", "--root", str(tmp_path)])
        assert org.read_text() == "custom: true\n"


class TestNew:
    def test_creates_file_spec(self, tmp_path: Path) -> None:
        runner = CliRunner()
        # Init first to have templates
        runner.invoke(main, ["init", "--root", str(tmp_path)])
        result = runner.invoke(
            main, ["new", "utility", "src/helpers/format", "--root", str(tmp_path)]
        )
        assert result.exit_code == 0
        spec = tmp_path / "src" / "helpers" / "format.spec.md"
        assert spec.exists()
        content = spec.read_text()
        assert 'type: "utility"' in content
        assert 'status: "draft"' in content

    def test_creates_service_spec(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(main, ["init", "--root", str(tmp_path)])
        result = runner.invoke(main, ["new", "service", "packages/auth", "--root", str(tmp_path)])
        assert result.exit_code == 0
        spec = tmp_path / "packages" / "auth" / ".spec.yaml"
        assert spec.exists()
        content = spec.read_text()
        assert "service:" in content
        assert "auth" in content

    def test_fills_generates_path(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(main, ["init", "--root", str(tmp_path)])
        runner.invoke(main, ["new", "api-endpoint", "src/auth/login", "--root", str(tmp_path)])
        spec = tmp_path / "src" / "auth" / "login.spec.md"
        content = spec.read_text()
        assert "src/auth/login" in content

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(main, ["init", "--root", str(tmp_path)])
        runner.invoke(main, ["new", "utility", "deep/nested/path/module", "--root", str(tmp_path)])
        spec = tmp_path / "deep" / "nested" / "path" / "module.spec.md"
        assert spec.exists()

    def test_does_not_overwrite_existing(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(main, ["init", "--root", str(tmp_path)])
        runner.invoke(main, ["new", "utility", "src/helper", "--root", str(tmp_path)])
        result = runner.invoke(main, ["new", "utility", "src/helper", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "already exists" in result.output.lower()

    def test_works_without_init(self, tmp_path: Path) -> None:
        """new should work even without init, using bundled templates."""
        runner = CliRunner()
        result = runner.invoke(main, ["new", "utility", "src/helper", "--root", str(tmp_path)])
        assert result.exit_code == 0
        spec = tmp_path / "src" / "helper.spec.md"
        assert spec.exists()

    def test_inherits_finds_service_spec(self, tmp_path: Path) -> None:
        """If a .spec.yaml exists in a parent dir, inherit from it."""
        runner = CliRunner()
        runner.invoke(main, ["init", "--root", str(tmp_path)])
        # Create a service spec
        pkg = tmp_path / "packages" / "auth"
        pkg.mkdir(parents=True)
        (pkg / ".spec.yaml").write_text(
            'specVersion: "0.1.0"\ninherits: "../../org.spec.yaml"\n'
            'service: "auth"\nowner: "@team"\n'
        )
        # Now create a file spec under that package
        runner.invoke(main, [
            "new", "api-endpoint", "packages/auth/src/handler", "--root", str(tmp_path),
        ])
        spec = tmp_path / "packages" / "auth" / "src" / "handler.spec.md"
        content = spec.read_text()
        assert "../.spec.yaml" in content
