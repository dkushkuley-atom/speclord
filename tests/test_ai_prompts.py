"""Tests for the AI prompt builders."""

from __future__ import annotations

from speclord.ai.prompts import build_draft_prompt, build_drift_prompt, build_review_prompt
from speclord.types import FileSpec, OrgSpec, ResolvedChain, ServiceSpec


def _make_file_spec(**overrides: object) -> FileSpec:
    """Create a FileSpec with sensible defaults, overridable per-field."""
    defaults = {
        "file_path": "src/auth/login.spec.md",
        "spec_version": "1.0",
        "inherits": "../.spec.yaml",
        "type": "api-endpoint",
        "owner": "auth-team",
        "status": "active",
        "body": "Handles user login via POST /login.\n\nReturns JWT on success.",
        "priority": "high",
        "dependencies": ["types", "db"],
        "generates": "login.py",
    }
    defaults.update(overrides)
    return FileSpec(**defaults)  # type: ignore[arg-type]


def _make_service_spec(**overrides: object) -> ServiceSpec:
    defaults = {
        "file_path": "src/auth/.spec.yaml",
        "spec_version": "1.0",
        "inherits": "../org.spec.yaml",
        "service": "auth-service",
        "owner": "auth-team",
        "conventions": {"naming": "snake_case"},
        "testing": {"min_coverage": 90},
        "security": ["no-plaintext-passwords"],
    }
    defaults.update(overrides)
    return ServiceSpec(**defaults)  # type: ignore[arg-type]


def _make_org_spec(**overrides: object) -> OrgSpec:
    defaults = {
        "file_path": "org.spec.yaml",
        "spec_version": "1.0",
        "organization": "acme-corp",
        "stack": {"language": "python", "framework": "fastapi"},
        "patterns": {"architecture": "hexagonal"},
        "security": ["owasp-top-10", "encrypt-at-rest"],
    }
    defaults.update(overrides)
    return OrgSpec(**defaults)  # type: ignore[arg-type]


# ── build_drift_prompt ───────────────────────────────────────────────


class TestBuildDriftPrompt:
    def test_returns_tuple(self) -> None:
        """Returns (prompt, system) tuple."""
        chain = ResolvedChain(file_spec=_make_file_spec())
        prompt, system = build_drift_prompt(chain, "def login(): pass")
        assert isinstance(prompt, str)
        assert isinstance(system, str)

    def test_prompt_contains_drift_analysis_header(self) -> None:
        """Prompt starts with a drift analysis request header."""
        chain = ResolvedChain(file_spec=_make_file_spec())
        prompt, _ = build_drift_prompt(chain, "code")
        assert "# Drift Analysis Request" in prompt

    def test_prompt_contains_source_code(self) -> None:
        """Prompt includes the source code in a code block."""
        chain = ResolvedChain(file_spec=_make_file_spec())
        code = "def login(username, password):\n    return jwt.encode({})"
        prompt, _ = build_drift_prompt(chain, code)
        assert "## Source Code" in prompt
        assert "def login(username, password)" in prompt

    def test_prompt_contains_file_spec_metadata(self) -> None:
        """Prompt includes file spec type, status, and owner."""
        fs = _make_file_spec(type="api-endpoint", status="active", owner="auth-team")
        chain = ResolvedChain(file_spec=fs)
        prompt, _ = build_drift_prompt(chain, "code")
        assert "api-endpoint" in prompt
        assert "active" in prompt
        assert "auth-team" in prompt

    def test_prompt_contains_spec_body(self) -> None:
        """Prompt includes the spec body content."""
        fs = _make_file_spec(body="Handles user login via POST /login.")
        chain = ResolvedChain(file_spec=fs)
        prompt, _ = build_drift_prompt(chain, "code")
        assert "Handles user login via POST /login." in prompt

    def test_prompt_contains_dependencies(self) -> None:
        """Prompt lists spec dependencies."""
        fs = _make_file_spec(dependencies=["types", "db"])
        chain = ResolvedChain(file_spec=fs)
        prompt, _ = build_drift_prompt(chain, "code")
        assert "types" in prompt
        assert "db" in prompt

    def test_prompt_contains_org_constraints(self) -> None:
        """When org spec is present, prompt includes org constraints."""
        chain = ResolvedChain(
            file_spec=_make_file_spec(),
            org_spec=_make_org_spec(),
        )
        prompt, _ = build_drift_prompt(chain, "code")
        assert "Organization Constraints" in prompt
        assert "acme-corp" in prompt
        assert "owasp-top-10" in prompt

    def test_prompt_contains_service_conventions(self) -> None:
        """When service spec is present, prompt includes conventions."""
        chain = ResolvedChain(
            file_spec=_make_file_spec(),
            service_spec=_make_service_spec(),
        )
        prompt, _ = build_drift_prompt(chain, "code")
        assert "Service Conventions" in prompt
        assert "auth-service" in prompt
        assert "snake_case" in prompt

    def test_prompt_contains_full_chain(self) -> None:
        """Full chain: org + service + file all appear in the prompt."""
        chain = ResolvedChain(
            file_spec=_make_file_spec(),
            service_spec=_make_service_spec(),
            org_spec=_make_org_spec(),
        )
        prompt, _ = build_drift_prompt(chain, "code")
        assert "Organization Constraints" in prompt
        assert "Service Conventions" in prompt
        assert "File Spec" in prompt

    def test_prompt_contains_task_section(self) -> None:
        """Prompt ends with a task section giving instructions."""
        chain = ResolvedChain(file_spec=_make_file_spec())
        prompt, _ = build_drift_prompt(chain, "code")
        assert "## Task" in prompt
        assert "drift" in prompt.lower()

    def test_system_prompt_mentions_compliance(self) -> None:
        """System prompt describes the auditor role."""
        chain = ResolvedChain(file_spec=_make_file_spec())
        _, system = build_drift_prompt(chain, "code")
        assert "compliance" in system.lower()
        assert "drift" in system.lower()

    def test_file_only_chain(self) -> None:
        """Works with file spec only (no service or org)."""
        chain = ResolvedChain(file_spec=_make_file_spec())
        prompt, system = build_drift_prompt(chain, "code")
        assert "File Spec" in prompt
        assert "Organization Constraints" not in prompt
        assert "Service Conventions" not in prompt
        assert len(system) > 0


# ── build_review_prompt ──────────────────────────────────────────────


class TestBuildReviewPrompt:
    def test_returns_tuple(self) -> None:
        """Returns (prompt, system) tuple."""
        prompt, system = build_review_prompt(_make_file_spec())
        assert isinstance(prompt, str)
        assert isinstance(system, str)

    def test_prompt_contains_review_header(self) -> None:
        """Prompt starts with a review request header."""
        prompt, _ = build_review_prompt(_make_file_spec())
        assert "# Spec Review Request" in prompt

    def test_prompt_contains_metadata(self) -> None:
        """Prompt includes spec metadata section."""
        fs = _make_file_spec(
            file_path="src/auth/login.spec.md",
            type="api-endpoint",
            owner="auth-team",
        )
        prompt, _ = build_review_prompt(fs)
        assert "## Spec Metadata" in prompt
        assert "src/auth/login.spec.md" in prompt
        assert "api-endpoint" in prompt
        assert "auth-team" in prompt

    def test_prompt_contains_body(self) -> None:
        """Prompt includes the spec body."""
        fs = _make_file_spec(body="Handles user login via POST /login.")
        prompt, _ = build_review_prompt(fs)
        assert "## Spec Body" in prompt
        assert "Handles user login via POST /login." in prompt

    def test_empty_body_noted(self) -> None:
        """When body is empty, prompt indicates that explicitly."""
        fs = _make_file_spec(body="")
        prompt, _ = build_review_prompt(fs)
        assert "empty" in prompt.lower()

    def test_prompt_contains_dependencies(self) -> None:
        """Prompt lists dependencies when present."""
        fs = _make_file_spec(dependencies=["types", "db"])
        prompt, _ = build_review_prompt(fs)
        assert "types" in prompt
        assert "db" in prompt

    def test_prompt_contains_generates(self) -> None:
        """Prompt lists generates target when present."""
        fs = _make_file_spec(generates="login.py")
        prompt, _ = build_review_prompt(fs)
        assert "login.py" in prompt

    def test_prompt_contains_task_section(self) -> None:
        """Prompt ends with a task section."""
        prompt, _ = build_review_prompt(_make_file_spec())
        assert "## Task" in prompt
        assert "score" in prompt.lower()

    def test_system_prompt_mentions_quality(self) -> None:
        """System prompt describes the reviewer role."""
        _, system = build_review_prompt(_make_file_spec())
        assert "quality" in system.lower()
        assert "score" in system.lower()

    def test_no_dependencies_omitted(self) -> None:
        """When no dependencies, Dependencies line is not in prompt."""
        fs = _make_file_spec(dependencies=[])
        prompt, _ = build_review_prompt(fs)
        assert "Dependencies" not in prompt

    def test_no_generates_omitted(self) -> None:
        """When generates is None, Generates line is not in prompt."""
        fs = _make_file_spec(generates=None)
        prompt, _ = build_review_prompt(fs)
        assert "Generates" not in prompt


# ── build_draft_prompt ───────────────────────────────────────────────


class TestBuildDraftPrompt:
    def test_returns_tuple(self) -> None:
        """Returns (prompt, system) tuple."""
        prompt, system = build_draft_prompt("A user login endpoint")
        assert isinstance(prompt, str)
        assert isinstance(system, str)

    def test_prompt_contains_draft_header(self) -> None:
        """Prompt starts with a draft request header."""
        prompt, _ = build_draft_prompt("A user login endpoint")
        assert "# Spec Draft Request" in prompt

    def test_prompt_contains_description(self) -> None:
        """Prompt includes the description section."""
        prompt, _ = build_draft_prompt("A REST API endpoint for user authentication")
        assert "## Description" in prompt
        assert "REST API endpoint for user authentication" in prompt

    def test_prompt_without_template(self) -> None:
        """When no template, Template section is absent."""
        prompt, _ = build_draft_prompt("description")
        assert "Template" not in prompt

    def test_prompt_with_template(self) -> None:
        """When template provided, it appears in a markdown code block."""
        template = "---\ntype: api-endpoint\n---\n# Login"
        prompt, _ = build_draft_prompt("desc", template=template)
        assert "## Template" in prompt
        assert "api-endpoint" in prompt

    def test_prompt_without_context(self) -> None:
        """When no context, Additional Context section is absent."""
        prompt, _ = build_draft_prompt("description")
        assert "Additional Context" not in prompt

    def test_prompt_with_context(self) -> None:
        """When context provided, it appears in the prompt."""
        ctx = "Related to the auth service. Uses JWT tokens."
        prompt, _ = build_draft_prompt("desc", context=ctx)
        assert "## Additional Context" in prompt
        assert "JWT tokens" in prompt

    def test_prompt_with_template_and_context(self) -> None:
        """Both template and context appear when provided."""
        prompt, _ = build_draft_prompt(
            "desc",
            template="---\ntype: utility\n---",
            context="Helper for date formatting",
        )
        assert "## Template" in prompt
        assert "## Additional Context" in prompt

    def test_prompt_contains_task_section(self) -> None:
        """Prompt ends with a task section."""
        prompt, _ = build_draft_prompt("desc")
        assert "## Task" in prompt
        assert "frontmatter" in prompt.lower()

    def test_system_prompt_mentions_spec_writer(self) -> None:
        """System prompt describes the spec writer role."""
        _, system = build_draft_prompt("desc")
        assert "specification" in system.lower()
        assert "frontmatter" in system.lower()
