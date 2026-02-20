"""Tests for the structural integrity checker."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from speclord.checker import check_all, check_spec
from speclord.cli import main

# Helper to write a minimal valid spec file
SPEC_TEMPLATE = (
    "---\nspecVersion: '0.1.0'\ninherits: '{inherits}'\n"
    "type: utility\nstatus: {status}\nowner: '@dev'\n"
    "{extra}---\n{body}\n"
)


def _write_spec(
    path: Path,
    *,
    inherits: str = ".spec.yaml",
    status: str = "draft",
    generates: str | None = None,
    dependencies: list[str] | None = None,
    body: str = "Body.",
) -> None:
    extra = ""
    if generates is not None:
        extra += f"generates: '{generates}'\n"
    if dependencies:
        extra += "dependencies:\n"
        for dep in dependencies:
            extra += f"  - '{dep}'\n"
    content = SPEC_TEMPLATE.format(
        inherits=inherits,
        status=status,
        extra=extra,
        body=body,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_inherits(tmp_path: Path) -> None:
    """Write a minimal .spec.yaml so inherits resolves."""
    (tmp_path / ".spec.yaml").write_text(
        "specVersion: '0.1.0'\ninherits: 'org.spec.yaml'\n"
        "service: test\nowner: '@dev'\n"
    )


class TestCheckSpec:
    def test_generates_target_missing(self, tmp_path: Path) -> None:
        """generates points to a nonexistent file → error."""
        _write_inherits(tmp_path)
        spec = tmp_path / "foo.spec.md"
        _write_spec(spec, generates="foo.py")
        findings = check_spec(spec, tmp_path)
        assert any(f.rule == "missing-generates-target" for f in findings)

    def test_generates_target_exists(self, tmp_path: Path) -> None:
        """generates file exists → no finding."""
        _write_inherits(tmp_path)
        (tmp_path / "foo.py").write_text("pass")
        spec = tmp_path / "foo.spec.md"
        _write_spec(spec, generates="foo.py")
        findings = check_spec(spec, tmp_path)
        assert not any(f.rule == "missing-generates-target" for f in findings)

    def test_generates_not_set(self, tmp_path: Path) -> None:
        """generates is None → no finding."""
        _write_inherits(tmp_path)
        spec = tmp_path / "foo.spec.md"
        _write_spec(spec)
        findings = check_spec(spec, tmp_path)
        assert not any(f.rule == "missing-generates-target" for f in findings)

    def test_broken_dependency(self, tmp_path: Path) -> None:
        """Dependency doesn't resolve → error."""
        _write_inherits(tmp_path)
        spec = tmp_path / "foo.spec.md"
        _write_spec(spec, dependencies=["nonexistent"])
        findings = check_spec(spec, tmp_path)
        assert any(f.rule == "broken-dependency" for f in findings)

    def test_valid_dependency(self, tmp_path: Path) -> None:
        """Dependency resolves to an existing spec → no finding."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "bar.spec.md")
        spec = tmp_path / "foo.spec.md"
        _write_spec(spec, dependencies=["bar"])
        findings = check_spec(spec, tmp_path)
        assert not any(f.rule == "broken-dependency" for f in findings)

    def test_active_empty_body(self, tmp_path: Path) -> None:
        """Active status with empty body → warning."""
        _write_inherits(tmp_path)
        spec = tmp_path / "foo.spec.md"
        _write_spec(spec, status="active", body="")
        findings = check_spec(spec, tmp_path)
        matches = [f for f in findings if f.rule == "active-empty-body"]
        assert len(matches) == 1
        assert matches[0].severity == "warning"

    def test_active_with_body(self, tmp_path: Path) -> None:
        """Active status with a body → no finding."""
        _write_inherits(tmp_path)
        spec = tmp_path / "foo.spec.md"
        _write_spec(spec, status="active", body="Has content.")
        findings = check_spec(spec, tmp_path)
        assert not any(f.rule == "active-empty-body" for f in findings)

    def test_draft_empty_body(self, tmp_path: Path) -> None:
        """Draft status with empty body → no finding (draft is WIP)."""
        _write_inherits(tmp_path)
        spec = tmp_path / "foo.spec.md"
        _write_spec(spec, status="draft", body="")
        findings = check_spec(spec, tmp_path)
        assert not any(f.rule == "active-empty-body" for f in findings)

    def test_missing_inherits_target(self, tmp_path: Path) -> None:
        """Inherits path doesn't exist → error."""
        spec = tmp_path / "foo.spec.md"
        _write_spec(spec, inherits="nonexistent.spec.yaml")
        findings = check_spec(spec, tmp_path)
        assert any(f.rule == "missing-inherits-target" for f in findings)

    def test_valid_inherits_target(self, tmp_path: Path) -> None:
        """Inherits file exists → no finding."""
        _write_inherits(tmp_path)
        spec = tmp_path / "foo.spec.md"
        _write_spec(spec)
        findings = check_spec(spec, tmp_path)
        assert not any(f.rule == "missing-inherits-target" for f in findings)


class TestCheckAll:
    def test_aggregates_findings(self, tmp_path: Path) -> None:
        """Multiple specs → findings combined from all."""
        _write_inherits(tmp_path)
        _write_spec(
            tmp_path / "a.spec.md",
            generates="missing.py",
        )
        _write_spec(
            tmp_path / "b.spec.md",
            status="active",
            body="",
        )
        findings = check_all(tmp_path)
        rules = {f.rule for f in findings}
        assert "missing-generates-target" in rules
        assert "active-empty-body" in rules

    def test_empty_repo(self, tmp_path: Path) -> None:
        """No specs → empty list."""
        findings = check_all(tmp_path)
        assert findings == []

    def test_parse_error_captured(self, tmp_path: Path) -> None:
        """Malformed spec → parse-error finding instead of exception."""
        bad = tmp_path / "bad.spec.md"
        bad.write_text("not valid frontmatter at all")
        findings = check_all(tmp_path)
        assert any(f.rule == "parse-error" for f in findings)


class TestCheckCLI:
    def test_check_text_output(self, tmp_path: Path) -> None:
        """Text mode shows findings."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "foo.spec.md", generates="missing.py")
        runner = CliRunner()
        result = runner.invoke(main, ["check", "--root", str(tmp_path)])
        # Rich may truncate column values in narrow terminals
        assert "missing-generates" in result.output

    def test_check_json_output(self, tmp_path: Path) -> None:
        """JSON mode produces valid JSON with expected keys."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "foo.spec.md", generates="missing.py")
        runner = CliRunner()
        result = runner.invoke(
            main, ["check", "--root", str(tmp_path), "--format", "json"]
        )
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["rule"] == "missing-generates-target"
        assert "severity" in data[0]

    def test_check_single_file(self, tmp_path: Path) -> None:
        """speclord check <file> checks only that spec."""
        _write_inherits(tmp_path)
        spec = tmp_path / "foo.spec.md"
        _write_spec(spec, generates="missing.py")
        runner = CliRunner()
        result = runner.invoke(
            main, ["check", str(spec), "--root", str(tmp_path)]
        )
        assert "missing-generates" in result.output

    def test_check_clean(self, tmp_path: Path) -> None:
        """No findings → success message."""
        _write_inherits(tmp_path)
        (tmp_path / "foo.py").write_text("pass")
        _write_spec(tmp_path / "foo.spec.md", generates="foo.py")
        runner = CliRunner()
        result = runner.invoke(main, ["check", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "All specs pass" in result.output

    def test_check_exit_code(self, tmp_path: Path) -> None:
        """Error findings → exit code 1."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "foo.spec.md", generates="missing.py")
        runner = CliRunner()
        result = runner.invoke(main, ["check", "--root", str(tmp_path)])
        assert result.exit_code != 0
