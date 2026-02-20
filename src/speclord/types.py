"""Core data types for speclord."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# Spec type — the kind of code file a spec describes
SpecType = Literal[
    "api-endpoint",
    "data-model",
    "utility",
    "middleware",
    "config",
    "integration",
    "event-handler",
    "job",
    "migration",
    "cli-command",
    "service",
    "hook",
    "decorator",
    "model",
    "schema",
]

VALID_SPEC_TYPES: set[str] = {
    "api-endpoint",
    "data-model",
    "utility",
    "middleware",
    "config",
    "integration",
    "event-handler",
    "job",
    "migration",
    "cli-command",
    "service",
    "hook",
    "decorator",
    "model",
    "schema",
}

# Spec lifecycle status
SpecStatus = Literal["draft", "active", "deprecated", "archived"]

VALID_STATUSES: set[str] = {"draft", "active", "deprecated", "archived"}

# Lint finding severity
Severity = Literal["error", "warning", "info"]


@dataclass
class FileSpec:
    """A parsed file-level spec (.spec.md).

    Represents a single code file's contract: what it should do,
    its interface, behavior, edge cases, and testing requirements.
    """

    file_path: str
    spec_version: str
    inherits: str
    type: str
    owner: str
    status: str
    body: str
    priority: str = "normal"
    dependencies: list[str] = field(default_factory=list)
    generates: str | None = None


@dataclass
class ServiceSpec:
    """A parsed service-level spec (.spec.yaml in package dirs).

    Defines conventions, testing config, and constraints for a
    package/service. File specs within the package inherit from this.
    """

    file_path: str
    spec_version: str
    inherits: str
    service: str
    owner: str
    conventions: dict[str, Any] = field(default_factory=dict)
    dependencies: dict[str, Any] = field(default_factory=dict)
    testing: dict[str, Any] = field(default_factory=dict)
    security: list[str] = field(default_factory=list)
    infrastructure: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrgSpec:
    """A parsed organization-level spec (org.spec.yaml at repo root).

    The top of the inheritance chain. Defines org-wide constraints
    that all service and file specs must respect.
    """

    file_path: str
    spec_version: str
    organization: str
    stack: dict[str, Any] = field(default_factory=dict)
    patterns: dict[str, Any] = field(default_factory=dict)
    security: list[str] = field(default_factory=list)


@dataclass
class LintFinding:
    """A single validation finding from linting."""

    file_path: str
    rule: str
    message: str
    severity: Severity = "error"


@dataclass
class RegistryEntry:
    """A single spec entry in the compiled registry."""

    path: str
    hash: str
    type: str
    status: str
    dependencies: list[str] = field(default_factory=list)
    generates: str | None = None


@dataclass
class ResolvedChain:
    """A fully resolved inheritance chain for a file spec.

    Walks from file spec → service spec → org spec.
    """

    file_spec: FileSpec
    service_spec: ServiceSpec | None = None
    org_spec: OrgSpec | None = None


@dataclass
class CoverageReport:
    """The result of a spec coverage check."""

    total_files: int
    specced_files: int
    unspecced: list[str] = field(default_factory=list)

    @property
    def coverage_pct(self) -> float:
        if self.total_files == 0:
            return 100.0
        return (self.specced_files / self.total_files) * 100.0


@dataclass
class DepGraph:
    """Directed dependency graph of file specs.

    Nodes are spec paths (posix, relative to root).
    Each node maps to the list of specs it depends on.
    """

    adjacency: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class DirScanEntry:
    """Spec coverage stats for a single directory."""

    directory: str
    total_files: int
    specced_files: int
    unspecced: list[str] = field(default_factory=list)


@dataclass
class MigrationScan:
    """Result of scanning the codebase for migration readiness."""

    total_files: int
    specced_files: int
    unspecced_files: int
    by_directory: list[DirScanEntry] = field(default_factory=list)


@dataclass
class MigrationPhase:
    """A single phase in a migration plan."""

    name: str
    description: str
    files: list[str] = field(default_factory=list)


@dataclass
class MigrationPlan:
    """A phased plan for adopting specs across a codebase."""

    phases: list[MigrationPhase] = field(default_factory=list)


@dataclass
class ProgressReport:
    """Progress comparing current spec coverage to a compiled baseline."""

    current_total: int
    current_specced: int
    baseline_specced: int
    has_baseline: bool
    new_specs: list[str] = field(default_factory=list)
    removed_specs: list[str] = field(default_factory=list)

    @property
    def current_pct(self) -> float:
        if self.current_total == 0:
            return 100.0
        return (self.current_specced / self.current_total) * 100.0

    @property
    def delta(self) -> int:
        return self.current_specced - self.baseline_specced

    @property
    def remaining(self) -> int:
        return self.current_total - self.current_specced


@dataclass
class DriftFinding:
    """A single drift finding between a spec and its code."""

    spec_section: str
    code_location: str
    description: str
    severity: Severity = "warning"


@dataclass
class DriftReport:
    """Result of comparing a spec's contract against its source code."""

    spec_path: str
    summary: str
    findings: list[DriftFinding] = field(default_factory=list)


@dataclass
class ReviewSuggestion:
    """A single improvement suggestion from a spec review."""

    category: str
    suggestion: str
    priority: str = "medium"


@dataclass
class SpecReview:
    """Result of an AI quality review of a spec file."""

    spec_path: str
    score: int
    summary: str
    suggestions: list[ReviewSuggestion] = field(default_factory=list)
