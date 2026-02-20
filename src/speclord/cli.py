"""CLI entry point for speclord."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.table import Table

from speclord import __version__

if TYPE_CHECKING:
    from speclord.config import SpeclordConfig

console = Console()


def _resolve_root(cli_root: str | None) -> tuple[Path, SpeclordConfig]:
    """Resolve effective root from CLI flag and config file.

    If cli_root is provided, it wins. Otherwise, config root is used.
    """
    from speclord.config import load_config

    discovery_root = Path(cli_root).resolve() if cli_root else Path(".").resolve()
    cfg = load_config(discovery_root)
    effective_root = Path(cli_root).resolve() if cli_root is not None else Path(cfg.root).resolve()
    return effective_root, cfg


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="speclord")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Speclord — the spec layer for AI-assisted development.

    Specs are the source of truth. Speclord provides context to AI tools,
    enforces compliance, and catches drift.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def lint(root: str | None, fmt: str) -> None:
    """Validate all spec files in the project."""
    from speclord.validator import lint_all

    root_path, _cfg = _resolve_root(root)
    findings = lint_all(root_path)

    if fmt == "json":
        import json

        data = [
            {
                "file": f.file_path,
                "rule": f.rule,
                "message": f.message,
                "severity": f.severity,
            }
            for f in findings
        ]
        click.echo(json.dumps(data, indent=2))
    else:
        if not findings:
            console.print("[green]All specs are valid.[/green]")
            return

        table = Table(title="Lint Findings")
        table.add_column("Severity", style="bold")
        table.add_column("File")
        table.add_column("Rule")
        table.add_column("Message")

        for f in findings:
            sev_style = {"error": "red", "warning": "yellow", "info": "blue"}.get(
                f.severity, "white"
            )
            table.add_row(
                f"[{sev_style}]{f.severity}[/{sev_style}]",
                f.file_path,
                f.rule,
                f.message,
            )

        console.print(table)

    errors = [f for f in findings if f.severity == "error"]
    if errors:
        console.print(f"\n[red]{len(errors)} error(s) found.[/red]")
        sys.exit(1)


@main.command()
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory.")
def compile(root: str | None) -> None:
    """Compile all specs into registry.lock.json."""
    from speclord.registry import compile_registry

    root_path, _cfg = _resolve_root(root)
    registry = compile_registry(root_path)

    specs = registry.get("specs", {})
    errors = registry.get("errors", [])

    console.print(f"[green]Compiled {len(specs)} spec(s) into registry.lock.json[/green]")
    if errors:
        console.print(f"[yellow]{len(errors)} error(s) during compilation:[/yellow]")
        for err in errors:
            console.print(f"  {err}")


@main.command()
@click.option("--root", type=click.Path(), default=".", help="Project root directory.")
@click.option("--org", "org_name", default="my-org", help="Organization name.")
def init(root: str, org_name: str) -> None:
    """Initialize a .spec/ structure in the project."""
    import shutil

    root_path = Path(root).resolve()
    spec_dir = root_path / ".spec"
    templates_dir = spec_dir / "templates"

    if spec_dir.exists():
        console.print("[yellow].spec/ directory already exists.[/yellow]")
        return

    # Create directories
    templates_dir.mkdir(parents=True)

    # Copy bundled templates
    bundled = Path(__file__).parent / "templates"
    for template in bundled.iterdir():
        shutil.copy2(template, templates_dir / template.name)

    # Create org spec
    org_spec_path = root_path / "org.spec.yaml"
    if not org_spec_path.exists():
        org_spec_path.write_text(
            f'specVersion: "0.1.0"\n'
            f'organization: "{org_name}"\n'
            f"\n"
            f"stack:\n"
            f'  runtime: "python"\n'
            f'  language: "python"\n'
            f"\n"
            f"patterns:\n"
            f'  naming: "snake_case"\n'
            f'  testing: "pytest"\n'
            f"\n"
            f"security:\n"
            f'  - "Validate all input"\n'
        )
        console.print("[green]Created org.spec.yaml[/green]")

    console.print(f"[green]Initialized .spec/ at {spec_dir}[/green]")
    console.print(f"  Templates: {len(list(templates_dir.iterdir()))} files")


@main.command("new")
@click.argument("spec_type", type=click.Choice([
    "api-endpoint", "data-model", "utility", "service",
]))
@click.argument("path")
@click.option("--root", type=click.Path(exists=True), default=".", help="Project root directory.")
def new_spec(spec_type: str, path: str, root: str) -> None:
    """Scaffold a new spec file from a template.

    SPEC_TYPE is the kind of spec (api-endpoint, data-model, utility, service).
    PATH is the target location relative to root (e.g., src/auth/login).
    """
    root_path = Path(root).resolve()

    # Find template
    if spec_type == "service":
        template_name = "service.spec.yaml"
        output_name = ".spec.yaml"
    else:
        template_name = f"{spec_type}.spec.md"
        output_name = f"{Path(path).name}.spec.md"

    # Look for template in .spec/templates/ first, then bundled
    template_path = root_path / ".spec" / "templates" / template_name
    if not template_path.exists():
        template_path = Path(__file__).parent / "templates" / template_name
    if not template_path.exists():
        console.print(f"[red]Template not found: {template_name}[/red]")
        sys.exit(1)

    template = template_path.read_text(encoding="utf-8")

    # Compute output path
    # For file specs: "src/auth/login" -> "src/auth/login.spec.md"
    # For service specs: "packages/auth" -> "packages/auth/.spec.yaml"
    if spec_type == "service":
        target_dir = root_path / path
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / output_name
    else:
        output_path = root_path / f"{path}.spec.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        console.print(f"[yellow]Spec already exists: {output_path.relative_to(root_path)}[/yellow]")
        return

    # Fill placeholders
    content = template
    # Compute inherits path (relative path to nearest .spec.yaml or org.spec.yaml)
    content = content.replace("INHERITS_PATH", _find_inherits(output_path, root_path))
    content = content.replace("GENERATES_PATH", str(Path(path).as_posix()))
    content = content.replace("OWNER", "@team")
    content = content.replace("SERVICE_NAME", Path(path).name)

    output_path.write_text(content, encoding="utf-8")
    rel = output_path.relative_to(root_path)
    console.print(f"[green]Created {rel}[/green]")


@main.command()
@click.argument("file", required=False)
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory.")
@click.option("--batch", type=str, default=None, help="Glob pattern for multiple specs.")
def context(file: str | None, root: str | None, batch: str | None) -> None:
    """Build AI-ready context from the spec chain.

    Resolves org → service → file and prints structured markdown to stdout.
    Use --batch with a glob pattern to process multiple specs at once.
    """
    from speclord.context import build_context
    from speclord.errors import ResolutionError

    if file is None and batch is None:
        console.print("[red]Provide a FILE argument or --batch pattern.[/red]")
        sys.exit(1)

    root_path, _cfg = _resolve_root(root)

    if batch is not None:
        specs = sorted(root_path.glob(batch))
        if not specs:
            console.print(f"[yellow]No specs matched pattern: {batch}[/yellow]", stderr=True)
            return

        outputs: list[str] = []
        for spec in specs:
            try:
                outputs.append(build_context(spec, root_path))
            except ResolutionError as e:
                console.print(f"[red]Error resolving {spec}: {e}[/red]", stderr=True)

        click.echo("\n---\n\n".join(outputs), nl=False)
    else:
        spec_path = Path(file).resolve()  # type: ignore[arg-type]
        if not spec_path.exists():
            console.print(f"[red]File not found: {file}[/red]", stderr=True)
            sys.exit(1)
        try:
            output = build_context(spec_path, root_path)
        except ResolutionError as e:
            console.print(f"[red]Error: {e}[/red]", stderr=True)
            sys.exit(1)
        click.echo(output, nl=False)


@main.command()
@click.argument("file")
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def resolve(file: str, root: str | None, fmt: str) -> None:
    """Show the resolved inheritance chain for a spec file.

    Displays which constraints come from each level: org → service → file.
    """
    import json

    from rich.tree import Tree

    from speclord.errors import ResolutionError
    from speclord.resolver import resolve_chain

    root_path, _cfg = _resolve_root(root)
    spec_path = Path(file).resolve()

    if not spec_path.exists():
        console.print(f"[red]File not found: {file}[/red]", stderr=True)
        sys.exit(1)

    try:
        chain = resolve_chain(spec_path, root_path)
    except ResolutionError as e:
        console.print(f"[red]Error: {e}[/red]", stderr=True)
        sys.exit(1)

    if fmt == "json":
        data: dict[str, object] = {}
        if chain.org_spec is not None:
            org = chain.org_spec
            data["org"] = {
                "file": org.file_path,
                "organization": org.organization,
                "stack": org.stack,
                "patterns": org.patterns,
                "security": org.security,
            }
        if chain.service_spec is not None:
            svc = chain.service_spec
            data["service"] = {
                "file": svc.file_path,
                "service": svc.service,
                "owner": svc.owner,
                "conventions": svc.conventions,
                "testing": svc.testing,
                "security": svc.security,
            }
        fs = chain.file_spec
        data["file"] = {
            "file": fs.file_path,
            "type": fs.type,
            "status": fs.status,
            "owner": fs.owner,
            "priority": fs.priority,
            "generates": fs.generates,
            "dependencies": fs.dependencies,
        }
        click.echo(json.dumps(data, indent=2))
        return

    # Text mode — Rich Tree
    try:
        rel = spec_path.relative_to(root_path)
    except ValueError:
        rel = spec_path

    # Build chain path string
    chain_parts: list[str] = []
    if chain.org_spec is not None:
        chain_parts.append(chain.org_spec.file_path)
    if chain.service_spec is not None:
        chain_parts.append(chain.service_spec.file_path)
    chain_parts.append(chain.file_spec.file_path)

    console.print(f"[bold]Resolve:[/bold] {rel}")
    console.print(f"[dim]Chain: {' → '.join(chain_parts)}[/dim]\n")

    tree = Tree("[bold]Spec Chain[/bold]")

    if chain.org_spec is not None:
        org = chain.org_spec
        org_branch = tree.add(
            f"[bold cyan]Organization:[/bold cyan] {org.organization} ({org.file_path})"
        )
        if org.stack:
            org_branch.add(f"Stack: {_fmt_dict(org.stack)}")
        if org.patterns:
            org_branch.add(f"Patterns: {_fmt_dict(org.patterns)}")
        if org.security:
            org_branch.add(f"Security: {', '.join(org.security)}")

    if chain.service_spec is not None:
        svc = chain.service_spec
        svc_branch = tree.add(
            f"[bold green]Service:[/bold green] {svc.service} ({svc.file_path})"
        )
        svc_branch.add(f"Owner: {svc.owner}")
        if svc.conventions:
            svc_branch.add(f"Conventions: {_fmt_dict(svc.conventions)}")
        if svc.testing:
            svc_branch.add(f"Testing: {_fmt_dict(svc.testing)}")
        if svc.security:
            svc_branch.add(f"Security: {', '.join(svc.security)}")

    fs = chain.file_spec
    file_branch = tree.add(
        f"[bold yellow]File:[/bold yellow] {fs.type}, {fs.status} ({fs.file_path})"
    )
    file_branch.add(f"Owner: {fs.owner}")
    if fs.priority != "normal":
        file_branch.add(f"Priority: {fs.priority}")
    if fs.generates:
        file_branch.add(f"Generates: {fs.generates}")
    if fs.dependencies:
        file_branch.add(f"Dependencies: {', '.join(fs.dependencies)}")

    console.print(tree)


@main.command()
@click.argument("target", type=click.Choice(["claude", "cursor", "copilot", "all"]))
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory.")
@click.option("--dry-run", is_flag=True, help="Print to stdout instead of writing files.")
def emit(target: str, root: str | None, dry_run: bool) -> None:
    """Generate AI tool instruction files from spec hierarchy.

    TARGET is the AI tool to emit for: claude, cursor, copilot, or all.
    """
    from speclord.emitter import TARGET_PATHS, write_target
    from speclord.emitter import emit as do_emit

    root_path, cfg = _resolve_root(root)

    targets = list(TARGET_PATHS.keys()) if target == "all" else [target]

    for t in targets:
        if dry_run:
            content = do_emit(root_path, t)
            click.echo(content, nl=False)
        else:
            out = write_target(root_path, t)
            try:
                rel = out.relative_to(root_path)
            except ValueError:
                rel = out
            console.print(f"[green]Wrote {rel}[/green]")


@main.command()
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory.")
@click.option("--min", "min_pct", type=float, default=None, help="Minimum coverage %.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def coverage(root: str | None, min_pct: float | None, fmt: str) -> None:
    """Check spec coverage — find code files without specs."""
    import json

    from speclord.coverage import check_coverage

    root_path, cfg = _resolve_root(root)
    report = check_coverage(root_path, cfg)

    if fmt == "json":
        data = {
            "total_files": report.total_files,
            "specced_files": report.specced_files,
            "coverage_pct": round(report.coverage_pct, 1),
            "unspecced": report.unspecced,
        }
        click.echo(json.dumps(data, indent=2))
    else:
        pct = round(report.coverage_pct, 1)
        color = "green" if pct >= 80 else "yellow" if pct >= 50 else "red"
        console.print(
            f"Spec coverage: [{color}]{pct}%[/{color}]"
            f" ({report.specced_files}/{report.total_files} files)"
        )
        if report.unspecced:
            console.print("\n[bold]Unspecced files:[/bold]")
            for f in report.unspecced:
                console.print(f"  {f}")

    if min_pct is not None and report.coverage_pct < min_pct:
        console.print(
            f"\n[red]Coverage {round(report.coverage_pct, 1)}%"
            f" is below minimum {min_pct}%[/red]"
        )
        sys.exit(1)


@main.command()
@click.argument("file", required=False)
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def check(file: str | None, root: str | None, fmt: str) -> None:
    """Run structural integrity checks on spec files.

    Validates that generates targets exist, dependencies resolve,
    inherits paths are valid, and status is consistent.
    """
    import json

    from speclord.checker import check_all, check_spec

    root_path, _cfg = _resolve_root(root)

    if file is not None:
        spec_path = Path(file).resolve()
        if not spec_path.exists():
            console.print(f"[red]File not found: {file}[/red]", stderr=True)
            sys.exit(1)
        findings = check_spec(spec_path, root_path)
    else:
        findings = check_all(root_path)

    if fmt == "json":
        data = [
            {
                "file": f.file_path,
                "rule": f.rule,
                "message": f.message,
                "severity": f.severity,
            }
            for f in findings
        ]
        click.echo(json.dumps(data, indent=2))
    else:
        if not findings:
            console.print("[green]All specs pass structural checks.[/green]")
            return

        table = Table(title="Check Findings")
        table.add_column("Severity", style="bold")
        table.add_column("File")
        table.add_column("Rule")
        table.add_column("Message")

        for f in findings:
            sev_style = {
                "error": "red",
                "warning": "yellow",
                "info": "blue",
            }.get(f.severity, "white")
            table.add_row(
                f"[{sev_style}]{f.severity}[/{sev_style}]",
                f.file_path,
                f.rule,
                f.message,
            )

        console.print(table)

        errors = [f for f in findings if f.severity == "error"]
        if errors:
            console.print(f"\n[red]{len(errors)} error(s) found.[/red]")
            sys.exit(1)
        return

    # JSON mode: exit non-zero if errors present
    if any(f.severity == "error" for f in findings):
        sys.exit(1)


@main.command()
@click.argument("file", required=False)
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory.")
@click.option(
    "--fail-on",
    "fail_on",
    type=click.Choice(["error", "warning", "info"]),
    default=None,
    help="Exit non-zero if findings at this severity or higher.",
)
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def drift(file: str | None, root: str | None, fail_on: str | None, fmt: str) -> None:
    """Analyze drift between specs and source code using AI.

    Compares a spec's contract with the actual code and reports
    any places where the code no longer matches the spec.
    Requires the Claude CLI to be installed.
    """
    import json

    from speclord.ai.adapter import ClaudeCodeAdapter
    from speclord.ai.drift import analyze_all_drift, analyze_drift
    from speclord.errors import AIError

    root_path, _cfg = _resolve_root(root)
    adapter = ClaudeCodeAdapter()

    if file is not None:
        spec_path = Path(file).resolve()
        if not spec_path.exists():
            console.print(f"[red]File not found: {file}[/red]")
            sys.exit(1)
        try:
            reports = [analyze_drift(spec_path, root_path, adapter)]
        except AIError as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
    else:
        reports = analyze_all_drift(root_path, adapter)

    # Collect all findings across reports
    all_findings = []
    for r in reports:
        for f in r.findings:
            all_findings.append((r.spec_path, f))

    if fmt == "json":
        data = [
            {
                "spec": r.spec_path,
                "summary": r.summary,
                "findings": [
                    {
                        "spec_section": f.spec_section,
                        "code_location": f.code_location,
                        "description": f.description,
                        "severity": f.severity,
                    }
                    for f in r.findings
                ],
            }
            for r in reports
        ]
        click.echo(json.dumps(data, indent=2))
    else:
        if not reports:
            console.print("[dim]No specs with code files found.[/dim]")
            return

        if not all_findings:
            console.print("[green]No drift detected — all specs match their code.[/green]")
            for r in reports:
                if r.summary:
                    console.print(f"  [dim]{r.spec_path}: {r.summary}[/dim]")
            return

        table = Table(title="Drift Findings")
        table.add_column("Severity", style="bold")
        table.add_column("Spec")
        table.add_column("Section")
        table.add_column("Description")

        for spec_path, f in all_findings:
            sev_style = {"error": "red", "warning": "yellow", "info": "blue"}.get(
                f.severity, "white"
            )
            table.add_row(
                f"[{sev_style}]{f.severity}[/{sev_style}]",
                spec_path,
                f.spec_section,
                f.description,
            )

        console.print(table)

        for r in reports:
            if r.summary:
                console.print(f"\n[dim]{r.spec_path}: {r.summary}[/dim]")

    # --fail-on exit logic
    if fail_on is not None:
        severity_levels = {"info": 0, "warning": 1, "error": 2}
        threshold = severity_levels[fail_on]
        for _, f in all_findings:
            if severity_levels.get(f.severity, 0) >= threshold:
                sys.exit(1)


@main.command()
@click.argument("file")
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def review(file: str, root: str | None, fmt: str) -> None:
    """Review a spec file for quality using AI.

    Evaluates clarity, completeness, and actionability. Returns a
    score from 0–100 and specific improvement suggestions.
    Requires the Claude CLI to be installed.
    """
    import json

    from speclord.ai.adapter import ClaudeCodeAdapter
    from speclord.ai.review import review_spec
    from speclord.errors import AIError

    root_path, _cfg = _resolve_root(root)
    adapter = ClaudeCodeAdapter()

    spec_path = Path(file).resolve()
    if not spec_path.exists():
        console.print(f"[red]File not found: {file}[/red]")
        sys.exit(1)

    try:
        result = review_spec(spec_path, root_path, adapter)
    except AIError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

    if fmt == "json":
        data = {
            "spec": result.spec_path,
            "score": result.score,
            "summary": result.summary,
            "suggestions": [
                {
                    "category": s.category,
                    "suggestion": s.suggestion,
                    "priority": s.priority,
                }
                for s in result.suggestions
            ],
        }
        click.echo(json.dumps(data, indent=2))
        return

    # Text mode
    score = result.score
    if score >= 80:
        color = "green"
    elif score >= 50:
        color = "yellow"
    else:
        color = "red"

    console.print(f"[bold]Review:[/bold] {result.spec_path}")
    console.print(f"[bold]Score:[/bold] [{color}]{score}/100[/{color}]")

    if result.summary:
        console.print(f"\n{result.summary}")

    if result.suggestions:
        console.print(f"\n[bold]Suggestions ({len(result.suggestions)}):[/bold]")
        for s in result.suggestions:
            priority_style = {
                "high": "red",
                "medium": "yellow",
                "low": "dim",
            }.get(s.priority, "white")
            console.print(
                f"  [{priority_style}][{s.priority}][/{priority_style}]"
                f" [bold]{s.category}:[/bold] {s.suggestion}"
            )


@main.command()
@click.argument("description")
@click.argument("path")
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory.")
@click.option("--from-code", "from_code", is_flag=True, help="Read existing source for context.")
@click.option("--type", "spec_type", default=None, help="Override spec type.")
def draft(
    description: str, path: str, root: str | None, from_code: bool, spec_type: str | None,
) -> None:
    """Draft a new spec file using AI.

    DESCRIPTION is what the code file does or should do.
    PATH is the target location relative to root (e.g., src/auth/login).
    The drafted spec is written to PATH.spec.md.
    Requires the Claude CLI to be installed.
    """
    from speclord.ai.adapter import ClaudeCodeAdapter
    from speclord.ai.draft import draft_spec
    from speclord.errors import AIError

    root_path, _cfg = _resolve_root(root)
    adapter = ClaudeCodeAdapter(max_turns=25)

    target = Path(path)
    output_path = root_path / f"{target.as_posix()}.spec.md"

    if output_path.exists():
        console.print(f"[yellow]Spec already exists: {output_path.relative_to(root_path)}[/yellow]")
        return

    try:
        content = draft_spec(
            description,
            target,
            root_path,
            adapter,
            from_code=from_code,
            spec_type=spec_type,
        )
    except AIError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    try:
        rel = output_path.relative_to(root_path)
    except ValueError:
        rel = output_path
    console.print(f"[green]Drafted {rel}[/green]")


@main.command()
@click.argument("file", required=False)
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def deps(file: str | None, root: str | None, fmt: str) -> None:
    """Show the dependency graph for specs.

    Without arguments, shows the full dependency graph and topological order.
    With a FILE argument, shows the dependency tree for that spec.
    """
    import json

    from rich.tree import Tree

    from speclord.deps import build_dep_graph, get_dep_tree, topological_sort
    from speclord.errors import CycleError

    root_path, _cfg = _resolve_root(root)
    graph = build_dep_graph(root_path)

    if file is not None:
        # Single-file dependency tree
        spec_path = Path(file).resolve()
        if not spec_path.exists():
            console.print(f"[red]File not found: {file}[/red]", stderr=True)
            sys.exit(1)
        try:
            node = spec_path.relative_to(root_path).as_posix()
        except ValueError:
            console.print(f"[red]File is not under root: {file}[/red]", stderr=True)
            sys.exit(1)

        if node not in graph.adjacency:
            console.print(f"[red]Not a recognized spec: {node}[/red]", stderr=True)
            sys.exit(1)

        tree_data = get_dep_tree(graph, node)

        if fmt == "json":
            click.echo(json.dumps(tree_data, indent=2))
        else:
            rich_tree = Tree(f"[bold]{node}[/bold]")

            def _add_branches(parent: Tree, children: dict[str, object]) -> None:
                for name, subtree in children.items():
                    if name == "(circular)":
                        parent.add("[red](circular)[/red]")
                    else:
                        branch = parent.add(name)
                        if isinstance(subtree, dict):
                            _add_branches(branch, subtree)

            _add_branches(rich_tree, tree_data[node])  # type: ignore[arg-type]
            console.print(rich_tree)
        return

    # Full graph
    if fmt == "json":
        try:
            order = topological_sort(graph)
        except CycleError as e:
            data = {
                "nodes": sorted(graph.adjacency),
                "edges": graph.adjacency,
                "order": None,
                "cycle": e.cycle,
            }
            click.echo(json.dumps(data, indent=2))
            sys.exit(1)

        data = {
            "nodes": sorted(graph.adjacency),
            "edges": graph.adjacency,
            "order": order,
        }
        click.echo(json.dumps(data, indent=2))
    else:
        if not graph.adjacency:
            console.print("[dim]No file specs found.[/dim]")
            return

        # Show each spec and its dependencies
        table = Table(title="Dependency Graph")
        table.add_column("Spec", style="bold")
        table.add_column("Dependencies")

        for node in sorted(graph.adjacency):
            dep_list = graph.adjacency[node]
            table.add_row(node, ", ".join(dep_list) if dep_list else "[dim]none[/dim]")

        console.print(table)
        console.print()

        # Topological order
        try:
            order = topological_sort(graph)
            console.print("[bold]Topological order:[/bold]")
            for i, node in enumerate(order, 1):
                console.print(f"  {i}. {node}")
        except CycleError as e:
            console.print(f"[red]Cycle detected: {' → '.join(e.cycle)}[/red]")
            sys.exit(1)


@main.command()
@click.argument("query", required=False, default="")
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory.")
@click.option("--type", "type_filter", default=None, help="Filter by spec type.")
@click.option("--owner", "owner_filter", default=None, help="Filter by owner.")
@click.option("--status", "status_filter", default=None, help="Filter by status.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def search(
    query: str,
    root: str | None,
    type_filter: str | None,
    owner_filter: str | None,
    status_filter: str | None,
    fmt: str,
) -> None:
    """Search specs by text query and/or field filters.

    QUERY is matched case-insensitively against body text and frontmatter.
    Use --type, --owner, --status to narrow results by field.
    """
    import json

    from speclord.search import search_specs

    root_path, _cfg = _resolve_root(root)

    if not query and type_filter is None and owner_filter is None and status_filter is None:
        console.print("[red]Provide a search query or at least one filter.[/red]")
        sys.exit(1)

    results = search_specs(
        root_path,
        query,
        type_filter=type_filter,
        owner_filter=owner_filter,
        status_filter=status_filter,
    )

    if fmt == "json":
        data = [
            {
                "file": s.file_path,
                "type": s.type,
                "status": s.status,
                "owner": s.owner,
                "generates": s.generates,
            }
            for s in results
        ]
        click.echo(json.dumps(data, indent=2))
    else:
        if not results:
            console.print("[dim]No matching specs found.[/dim]")
            return

        table = Table(title=f"Search Results ({len(results)})")
        table.add_column("File", style="bold")
        table.add_column("Type")
        table.add_column("Status")
        table.add_column("Owner")

        for s in results:
            table.add_row(s.file_path, s.type, s.status, s.owner)

        console.print(table)


@main.group()
def migrate() -> None:
    """Migration tools for adopting specs across a codebase."""


main.add_command(migrate)


@migrate.command("scan")
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def migrate_scan(root: str | None, fmt: str) -> None:
    """Scan the codebase for spec coverage by directory.

    Shows which directories have specs, which need them,
    and the overall migration readiness.
    """
    import json

    from speclord.migrate.scanner import scan_codebase

    root_path, cfg = _resolve_root(root)
    scan = scan_codebase(root_path, cfg)

    if fmt == "json":
        data = {
            "total_files": scan.total_files,
            "specced_files": scan.specced_files,
            "unspecced_files": scan.unspecced_files,
            "by_directory": [
                {
                    "directory": e.directory,
                    "total_files": e.total_files,
                    "specced_files": e.specced_files,
                    "unspecced": e.unspecced,
                }
                for e in scan.by_directory
            ],
        }
        click.echo(json.dumps(data, indent=2))
        return

    if scan.total_files == 0:
        console.print("[dim]No code files found.[/dim]")
        return

    pct = round(scan.specced_files / scan.total_files * 100, 1) if scan.total_files else 0
    color = "green" if pct >= 80 else "yellow" if pct >= 50 else "red"
    console.print(
        f"[bold]Migration Scan:[/bold] [{color}]{pct}%[/{color}] overall"
        f" ({scan.specced_files}/{scan.total_files} files specced)"
    )
    console.print()

    table = Table(title="Coverage by Directory")
    table.add_column("Directory", style="bold")
    table.add_column("Files", justify="right")
    table.add_column("Specced", justify="right")
    table.add_column("Coverage", justify="right")

    for entry in scan.by_directory:
        entry_pct = round(entry.specced_files / entry.total_files * 100, 1)
        entry_color = "green" if entry_pct >= 80 else "yellow" if entry_pct >= 50 else "red"
        table.add_row(
            entry.directory,
            str(entry.total_files),
            str(entry.specced_files),
            f"[{entry_color}]{entry_pct}%[/{entry_color}]",
        )

    console.print(table)

    if scan.unspecced_files:
        console.print(f"\n[bold]{scan.unspecced_files} file(s) need specs.[/bold]")


@migrate.command("plan")
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def migrate_plan(root: str | None, fmt: str) -> None:
    """Generate a phased migration plan for unspecced files.

    Analyzes the dependency graph to suggest which files should
    get specs first: core modules, then dependents, then leaves.
    """
    import json

    from speclord.migrate.planner import plan_migration

    root_path, cfg = _resolve_root(root)
    plan = plan_migration(root_path, cfg)

    if fmt == "json":
        data = [
            {
                "phase": p.name,
                "description": p.description,
                "files": p.files,
            }
            for p in plan.phases
        ]
        click.echo(json.dumps(data, indent=2))
        return

    if not plan.phases:
        console.print("[green]All code files have specs — nothing to migrate.[/green]")
        return

    total = sum(len(p.files) for p in plan.phases)
    n_phases = len(plan.phases)
    console.print(f"[bold]Migration Plan:[/bold] {total} file(s) across {n_phases} phase(s)")
    console.print()

    for i, phase in enumerate(plan.phases, 1):
        console.print(f"[bold]Phase {i}: {phase.name}[/bold] — {phase.description}")
        for f in phase.files:
            console.print(f"  {f}")
        console.print()


@migrate.command("progress")
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def migrate_progress(root: str | None, fmt: str) -> None:
    """Show migration progress compared to the last compile baseline.

    Compares current spec coverage against registry.lock.json to show
    what has changed: new specs added, specs removed, and overall delta.
    """
    import json

    from speclord.migrate.progress import track_progress

    root_path, cfg = _resolve_root(root)
    report = track_progress(root_path, cfg)

    if fmt == "json":
        data = {
            "current_total": report.current_total,
            "current_specced": report.current_specced,
            "current_pct": round(report.current_pct, 1),
            "baseline_specced": report.baseline_specced,
            "has_baseline": report.has_baseline,
            "delta": report.delta,
            "remaining": report.remaining,
            "new_specs": report.new_specs,
            "removed_specs": report.removed_specs,
        }
        click.echo(json.dumps(data, indent=2))
        return

    pct = round(report.current_pct, 1)
    color = "green" if pct >= 80 else "yellow" if pct >= 50 else "red"
    console.print(
        f"[bold]Migration Progress:[/bold] [{color}]{pct}%[/{color}]"
        f" ({report.current_specced}/{report.current_total} files)"
    )

    if not report.has_baseline:
        console.print(
            "\n[dim]No baseline found. Run 'speclord compile'"
            " to establish a baseline.[/dim]"
        )
        return

    console.print(f"\n[bold]Baseline:[/bold] {report.baseline_specced} spec(s)")

    if report.delta > 0:
        console.print(f"[bold]Delta:[/bold] [green]+{report.delta}[/green]")
    elif report.delta < 0:
        console.print(f"[bold]Delta:[/bold] [red]{report.delta}[/red]")
    else:
        console.print("[bold]Delta:[/bold] 0 (no change)")

    if report.remaining > 0:
        console.print(
            f"[bold]Remaining:[/bold] {report.remaining} file(s) need specs"
        )

    if report.new_specs:
        console.print(f"\n[bold]New specs (+{len(report.new_specs)}):[/bold]")
        for s in report.new_specs:
            console.print(f"  [green]+[/green] {s}")

    if report.removed_specs:
        n = len(report.removed_specs)
        console.print(f"\n[bold]Removed specs (-{n}):[/bold]")
        for s in report.removed_specs:
            console.print(f"  [red]-[/red] {s}")


@migrate.command("draft")
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory.")
@click.option("--batch", "directory", default=None, help="Only draft specs in this directory.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def migrate_draft(root: str | None, directory: str | None, fmt: str) -> None:
    """Draft specs for all unspecced files using AI.

    Scans the codebase, finds files without specs, and uses AI to
    generate draft specs for each one. Uses --from-code to read
    existing source files for context.
    Requires the Claude CLI to be installed.
    """
    import json

    from speclord.ai.adapter import ClaudeCodeAdapter
    from speclord.migrate.drafter import batch_draft

    root_path, cfg = _resolve_root(root)
    adapter = ClaudeCodeAdapter(max_turns=25)

    results = []
    succeeded = 0
    failed = 0

    for result in batch_draft(root_path, adapter, cfg, directory=directory):
        results.append(result)
        if result.success:
            succeeded += 1
            if fmt == "text":
                console.print(f"  [green]+[/green] {result.spec_path}")
        else:
            failed += 1
            if fmt == "text":
                console.print(f"  [red]x[/red] {result.source_path}: {result.error}")

    if fmt == "json":
        data = {
            "drafted": succeeded,
            "failed": failed,
            "results": [
                {
                    "source": r.source_path,
                    "spec": r.spec_path,
                    "success": r.success,
                    "error": r.error,
                }
                for r in results
            ],
        }
        click.echo(json.dumps(data, indent=2))
    else:
        if not results:
            console.print("[green]All code files already have specs.[/green]")
        else:
            console.print(
                f"\n[bold]Done:[/bold] {succeeded} drafted, {failed} failed"
            )


@main.command()
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory.")
def status(root: str | None) -> None:
    """Show a one-screen project status dashboard.

    Summarizes specs by type/status, coverage, last compile,
    lint findings, and check findings.
    """
    from collections import Counter

    from speclord.checker import check_all
    from speclord.coverage import check_coverage
    from speclord.errors import ParseError
    from speclord.parser import discover_specs, parse_file_spec
    from speclord.validator import lint_all

    root_path, cfg = _resolve_root(root)

    console.print("[bold]Speclord Status[/bold]")
    console.print()

    # --- Spec counts ---
    spec_paths = discover_specs(root_path)
    file_specs = []
    for p in spec_paths:
        if p.name.endswith(".spec.md"):
            try:
                file_specs.append(parse_file_spec(p))
            except ParseError:
                pass

    type_counts: Counter[str] = Counter(s.type for s in file_specs)
    status_counts: Counter[str] = Counter(s.status for s in file_specs)

    console.print(f"[bold]Specs:[/bold] {len(file_specs)} file spec(s)")
    if type_counts:
        parts = ", ".join(
            f"{t} ({c})" for t, c in type_counts.most_common()
        )
        console.print(f"  By type: {parts}")
    if status_counts:
        parts = ", ".join(
            f"{s} ({c})" for s, c in status_counts.most_common()
        )
        console.print(f"  By status: {parts}")

    console.print()

    # --- Coverage ---
    report = check_coverage(root_path, cfg)
    pct = round(report.coverage_pct, 1)
    color = "green" if pct >= 80 else "yellow" if pct >= 50 else "red"
    console.print(
        f"[bold]Coverage:[/bold] [{color}]{pct}%[/{color}]"
        f" ({report.specced_files}/{report.total_files} files)"
    )

    console.print()

    # --- Last compile ---
    lock_file = root_path / "registry.lock.json"
    if lock_file.exists():
        import datetime

        mtime = lock_file.stat().st_mtime
        dt = datetime.datetime.fromtimestamp(mtime)
        console.print(f"[bold]Last compile:[/bold] {dt:%Y-%m-%d %H:%M}")
    else:
        console.print("[bold]Last compile:[/bold] [dim]never[/dim]")

    console.print()

    # --- Lint summary ---
    lint_findings = lint_all(root_path)
    lint_errors = sum(1 for f in lint_findings if f.severity == "error")
    lint_warnings = sum(1 for f in lint_findings if f.severity == "warning")
    if not lint_findings:
        console.print("[bold]Lint:[/bold] [green]All specs valid[/green]")
    else:
        parts = []
        if lint_errors:
            parts.append(f"[red]{lint_errors} error(s)[/red]")
        if lint_warnings:
            parts.append(f"[yellow]{lint_warnings} warning(s)[/yellow]")
        console.print(f"[bold]Lint:[/bold] {', '.join(parts)}")

    # --- Check summary ---
    check_findings = check_all(root_path)
    check_errors = sum(1 for f in check_findings if f.severity == "error")
    check_warnings = sum(
        1 for f in check_findings if f.severity == "warning"
    )
    if not check_findings:
        console.print("[bold]Check:[/bold] [green]All specs pass[/green]")
    else:
        parts = []
        if check_errors:
            parts.append(f"[red]{check_errors} error(s)[/red]")
        if check_warnings:
            parts.append(f"[yellow]{check_warnings} warning(s)[/yellow]")
        console.print(f"[bold]Check:[/bold] {', '.join(parts)}")


def _fmt_dict(d: dict[str, object]) -> str:
    """Render a dict as comma-separated key=value for CLI display."""
    return ", ".join(f"{k}={v}" for k, v in d.items())


def _find_inherits(spec_path: Path, root: Path) -> str:
    """Find the nearest parent spec to inherit from."""
    import os

    current = spec_path.parent
    while current >= root:
        svc_spec = current / ".spec.yaml"
        if svc_spec.exists() and svc_spec != spec_path:
            return Path(os.path.relpath(svc_spec, spec_path.parent)).as_posix()
        org_spec = current / "org.spec.yaml"
        if org_spec.exists():
            return Path(os.path.relpath(org_spec, spec_path.parent)).as_posix()
        current = current.parent
    return ".spec.yaml"


if __name__ == "__main__":
    main()
