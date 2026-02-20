"""Tests for the drift analyzer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from speclord.ai.adapter import MockAdapter
from speclord.ai.drift import analyze_all_drift, analyze_drift
from speclord.cli import main
from speclord.errors import AIError
from speclord.types import DriftReport


def _write_spec(path: Path, body: str = "Spec body.", **frontmatter: Any) -> Path:
    """Write a minimal .spec.md file."""
    defaults = {
        "specVersion": "0.1.0",
        "type": "utility",
        "owner": "@team",
        "status": "active",
        "inherits": ".spec.yaml",
    }
    defaults.update(frontmatter)
    fm_lines = [f"{k}: {json.dumps(v)}" for k, v in defaults.items()]
    content = "---\n" + "\n".join(fm_lines) + "\n---\n\n" + body
    path.write_text(content, encoding="utf-8")
    return path


def _write_code(path: Path, code: str = "def hello(): pass\n") -> Path:
    """Write a Python source file."""
    path.write_text(code, encoding="utf-8")
    return path


def _mock_adapter_with_findings(findings: list[dict[str, str]] | None = None) -> MockAdapter:
    """Create a MockAdapter that returns a drift analysis response."""
    response: dict[str, Any] = {
        "summary": "Some drift detected.",
        "findings": findings or [],
    }
    return MockAdapter(analyze_response=response)


def _mock_adapter_clean() -> MockAdapter:
    """MockAdapter that reports no drift."""
    return MockAdapter(analyze_response={
        "summary": "Code matches spec.",
        "findings": [],
    })


# ── analyze_drift ────────────────────────────────────────────────────


class TestAnalyzeDrift:
    def test_returns_drift_report(self, tmp_path: Path) -> None:
        """analyze_drift returns a DriftReport."""
        _write_spec(tmp_path / "hello.spec.md")
        _write_code(tmp_path / "hello.py")
        adapter = _mock_adapter_clean()
        report = analyze_drift(tmp_path / "hello.spec.md", tmp_path, adapter)
        assert isinstance(report, DriftReport)

    def test_report_has_spec_path(self, tmp_path: Path) -> None:
        """DriftReport carries the relative spec path."""
        _write_spec(tmp_path / "hello.spec.md")
        _write_code(tmp_path / "hello.py")
        adapter = _mock_adapter_clean()
        report = analyze_drift(tmp_path / "hello.spec.md", tmp_path, adapter)
        assert report.spec_path == "hello.spec.md"

    def test_report_has_summary(self, tmp_path: Path) -> None:
        """DriftReport carries the AI summary."""
        _write_spec(tmp_path / "hello.spec.md")
        _write_code(tmp_path / "hello.py")
        adapter = _mock_adapter_clean()
        report = analyze_drift(tmp_path / "hello.spec.md", tmp_path, adapter)
        assert report.summary == "Code matches spec."

    def test_report_with_findings(self, tmp_path: Path) -> None:
        """Findings from the AI are parsed into DriftFinding objects."""
        _write_spec(tmp_path / "hello.spec.md")
        _write_code(tmp_path / "hello.py")
        adapter = _mock_adapter_with_findings([
            {
                "spec_section": "Interface",
                "code_location": "line 10",
                "description": "Missing return type",
                "severity": "warning",
            },
            {
                "spec_section": "Behavior",
                "code_location": "line 25",
                "description": "Error not raised",
                "severity": "error",
            },
        ])
        report = analyze_drift(tmp_path / "hello.spec.md", tmp_path, adapter)
        assert len(report.findings) == 2
        assert report.findings[0].spec_section == "Interface"
        assert report.findings[0].severity == "warning"
        assert report.findings[1].severity == "error"

    def test_code_file_not_found_raises(self, tmp_path: Path) -> None:
        """AIError raised when no code file can be found."""
        _write_spec(tmp_path / "orphan.spec.md")
        adapter = _mock_adapter_clean()
        with pytest.raises(AIError, match="Cannot find code file"):
            analyze_drift(tmp_path / "orphan.spec.md", tmp_path, adapter)

    def test_generates_field_used(self, tmp_path: Path) -> None:
        """When generates is set, that file is used as the code source."""
        sub = tmp_path / "src"
        sub.mkdir()
        _write_spec(
            tmp_path / "hello.spec.md",
            generates="src/hello_impl.py",
        )
        _write_code(sub / "hello_impl.py", "def impl(): pass\n")
        adapter = _mock_adapter_clean()
        report = analyze_drift(tmp_path / "hello.spec.md", tmp_path, adapter)
        assert report.spec_path == "hello.spec.md"
        # Verify the adapter received the code content in the prompt
        call = adapter.analyze_calls[0]
        assert "def impl(): pass" in call["prompt"]

    def test_inferred_code_file(self, tmp_path: Path) -> None:
        """Without generates, code file is inferred from spec name."""
        _write_spec(tmp_path / "utils.spec.md")
        _write_code(tmp_path / "utils.py", "def util(): return 42\n")
        adapter = _mock_adapter_clean()
        analyze_drift(tmp_path / "utils.spec.md", tmp_path, adapter)
        call = adapter.analyze_calls[0]
        assert "def util(): return 42" in call["prompt"]

    def test_adapter_receives_schema(self, tmp_path: Path) -> None:
        """The adapter is called with the drift JSON schema."""
        _write_spec(tmp_path / "hello.spec.md")
        _write_code(tmp_path / "hello.py")
        adapter = _mock_adapter_clean()
        analyze_drift(tmp_path / "hello.spec.md", tmp_path, adapter)
        schema = adapter.analyze_calls[0]["schema"]
        assert schema["type"] == "object"
        assert "findings" in schema["properties"]

    def test_prompt_contains_spec_body(self, tmp_path: Path) -> None:
        """The prompt sent to the adapter includes the spec body."""
        _write_spec(tmp_path / "hello.spec.md", body="Must validate input.")
        _write_code(tmp_path / "hello.py")
        adapter = _mock_adapter_clean()
        analyze_drift(tmp_path / "hello.spec.md", tmp_path, adapter)
        call = adapter.analyze_calls[0]
        assert "Must validate input." in call["prompt"]

    def test_finding_defaults_severity(self, tmp_path: Path) -> None:
        """Findings without severity default to warning."""
        _write_spec(tmp_path / "hello.spec.md")
        _write_code(tmp_path / "hello.py")
        adapter = MockAdapter(analyze_response={
            "summary": "",
            "findings": [{"spec_section": "x", "code_location": "y", "description": "z"}],
        })
        report = analyze_drift(tmp_path / "hello.spec.md", tmp_path, adapter)
        assert report.findings[0].severity == "warning"

    def test_malformed_finding_skipped(self, tmp_path: Path) -> None:
        """Non-dict entries in findings are skipped."""
        _write_spec(tmp_path / "hello.spec.md")
        _write_code(tmp_path / "hello.py")
        adapter = MockAdapter(analyze_response={
            "summary": "",
            "findings": [
                "not a dict",
                {"spec_section": "x", "code_location": "y", "description": "ok"},
            ],
        })
        report = analyze_drift(tmp_path / "hello.spec.md", tmp_path, adapter)
        assert len(report.findings) == 1


# ── analyze_all_drift ────────────────────────────────────────────────


class TestAnalyzeAllDrift:
    def test_empty_repo(self, tmp_path: Path) -> None:
        """No specs means no reports."""
        adapter = _mock_adapter_clean()
        reports = analyze_all_drift(tmp_path, adapter)
        assert reports == []

    def test_aggregates_reports(self, tmp_path: Path) -> None:
        """Multiple specs produce multiple reports."""
        _write_spec(tmp_path / "a.spec.md")
        _write_code(tmp_path / "a.py")
        _write_spec(tmp_path / "b.spec.md")
        _write_code(tmp_path / "b.py")
        adapter = _mock_adapter_clean()
        reports = analyze_all_drift(tmp_path, adapter)
        assert len(reports) == 2

    def test_skips_specs_without_code(self, tmp_path: Path) -> None:
        """Specs whose code file can't be found are silently skipped."""
        _write_spec(tmp_path / "has_code.spec.md")
        _write_code(tmp_path / "has_code.py")
        _write_spec(tmp_path / "no_code.spec.md")
        adapter = _mock_adapter_clean()
        reports = analyze_all_drift(tmp_path, adapter)
        assert len(reports) == 1
        assert reports[0].spec_path == "has_code.spec.md"

    def test_skips_non_file_specs(self, tmp_path: Path) -> None:
        """Service specs (.spec.yaml) are not analyzed for drift."""
        _write_spec(tmp_path / "hello.spec.md")
        _write_code(tmp_path / "hello.py")
        # Write a service spec
        (tmp_path / ".spec.yaml").write_text(
            'specVersion: "0.1.0"\nservice: "test"\nowner: "@team"\ninherits: ""\n',
            encoding="utf-8",
        )
        adapter = _mock_adapter_clean()
        reports = analyze_all_drift(tmp_path, adapter)
        assert len(reports) == 1


# ── CLI drift command ────────────────────────────────────────────────


class TestDriftCLI:
    def _setup_project(self, tmp_path: Path) -> Path:
        """Set up a minimal project with a spec and code file."""
        _write_spec(tmp_path / "hello.spec.md", body="Says hello.")
        _write_code(tmp_path / "hello.py", "def hello(): return 'hi'\n")
        return tmp_path

    def test_drift_json_single_file(self, tmp_path: Path) -> None:
        """--format json on a single file produces valid JSON."""
        self._setup_project(tmp_path)
        mock_report = DriftReport(
            spec_path="hello.spec.md",
            summary="No drift.",
            findings=[],
        )
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.ai.drift.analyze_drift", return_value=mock_report):
            result = runner.invoke(
                main,
                [
                    "drift", str(tmp_path / "hello.spec.md"),
                    "--root", str(tmp_path), "--format", "json",
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["spec"] == "hello.spec.md"

    def test_drift_text_no_findings(self, tmp_path: Path) -> None:
        """Text mode with no findings shows success message."""
        self._setup_project(tmp_path)
        mock_report = DriftReport(
            spec_path="hello.spec.md",
            summary="All good.",
            findings=[],
        )
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.ai.drift.analyze_drift", return_value=mock_report):
            result = runner.invoke(
                main,
                ["drift", str(tmp_path / "hello.spec.md"), "--root", str(tmp_path)],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert "No drift" in result.output

    def test_drift_text_with_findings(self, tmp_path: Path) -> None:
        """Text mode with findings shows a table."""
        from speclord.types import DriftFinding

        self._setup_project(tmp_path)
        mock_report = DriftReport(
            spec_path="hello.spec.md",
            summary="Drift found.",
            findings=[
                DriftFinding(
                    spec_section="Interface",
                    code_location="line 5",
                    description="Missing param",
                    severity="warning",
                ),
            ],
        )
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.ai.drift.analyze_drift", return_value=mock_report):
            result = runner.invoke(
                main,
                ["drift", str(tmp_path / "hello.spec.md"), "--root", str(tmp_path)],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert "Missing param" in result.output

    def test_drift_fail_on_error(self, tmp_path: Path) -> None:
        """--fail-on error exits 1 when error findings exist."""
        from speclord.types import DriftFinding

        self._setup_project(tmp_path)
        mock_report = DriftReport(
            spec_path="hello.spec.md",
            summary="Drift.",
            findings=[
                DriftFinding(
                    spec_section="Behavior",
                    code_location="line 10",
                    description="Wrong return",
                    severity="error",
                ),
            ],
        )
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.ai.drift.analyze_drift", return_value=mock_report):
            result = runner.invoke(
                main,
                [
                    "drift", str(tmp_path / "hello.spec.md"),
                    "--root", str(tmp_path),
                    "--fail-on", "error",
                ],
            )
        assert result.exit_code == 1

    def test_drift_fail_on_warning_ignores_info(self, tmp_path: Path) -> None:
        """--fail-on warning doesn't exit 1 for info-only findings."""
        from speclord.types import DriftFinding

        self._setup_project(tmp_path)
        mock_report = DriftReport(
            spec_path="hello.spec.md",
            summary="Minor.",
            findings=[
                DriftFinding(
                    spec_section="Style",
                    code_location="line 1",
                    description="Naming convention",
                    severity="info",
                ),
            ],
        )
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.ai.drift.analyze_drift", return_value=mock_report):
            result = runner.invoke(
                main,
                [
                    "drift", str(tmp_path / "hello.spec.md"),
                    "--root", str(tmp_path),
                    "--fail-on", "warning",
                ],
            )
        assert result.exit_code == 0

    def test_drift_help(self) -> None:
        """drift --help works."""
        runner = CliRunner()
        result = runner.invoke(main, ["drift", "--help"])
        assert result.exit_code == 0
        assert "drift" in result.output.lower()
        assert "--fail-on" in result.output
        assert "--format" in result.output

    def test_drift_command_registered(self) -> None:
        """drift command is registered in the CLI group."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "drift" in result.output

    def test_drift_file_not_found(self) -> None:
        """drift on a nonexistent file exits 1."""
        runner = CliRunner()
        result = runner.invoke(main, ["drift", "/nonexistent/file.spec.md", "--root", "."])
        assert result.exit_code != 0


# ── Severity and fail-on logic ───────────────────────────────────────


class TestFailOnLogic:
    """Test the severity threshold logic used by --fail-on."""

    def test_severity_levels(self) -> None:
        """Severity ordering: info < warning < error."""
        levels = {"info": 0, "warning": 1, "error": 2}
        assert levels["info"] < levels["warning"] < levels["error"]

    def test_error_threshold_ignores_warnings(self) -> None:
        """With --fail-on error, warnings don't trigger failure."""
        levels = {"info": 0, "warning": 1, "error": 2}
        threshold = levels["error"]
        findings = [{"severity": "warning"}, {"severity": "info"}]
        should_fail = any(levels.get(f["severity"], 0) >= threshold for f in findings)
        assert not should_fail

    def test_warning_threshold_catches_errors(self) -> None:
        """With --fail-on warning, errors also trigger failure."""
        levels = {"info": 0, "warning": 1, "error": 2}
        threshold = levels["warning"]
        findings = [{"severity": "error"}]
        should_fail = any(levels.get(f["severity"], 0) >= threshold for f in findings)
        assert should_fail

    def test_info_threshold_catches_all(self) -> None:
        """With --fail-on info, any finding triggers failure."""
        levels = {"info": 0, "warning": 1, "error": 2}
        threshold = levels["info"]
        findings = [{"severity": "info"}]
        should_fail = any(levels.get(f["severity"], 0) >= threshold for f in findings)
        assert should_fail
