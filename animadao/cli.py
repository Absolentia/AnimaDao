from __future__ import annotations

from pathlib import Path
import json
import sys

import click
from packaging.requirements import Requirement

from .dependency_checker import load_declared_deps, guess_unused
from .import_scanner import find_top_level_imports
from .report_generator import generate_report
from .version_checker import VersionChecker


@click.group(help="AnimaDao — dependency health checker for pyproject + uv.")
def cli() -> None:
    ...


@cli.command("scan")
@click.option("--project", type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."),
              help="Project root (contains pyproject.toml).")
@click.option("--src", type=click.Path(path_type=Path, exists=True), default=None,
              help="Source root to scan imports. Defaults to project root.")
def scan_cmd(project: Path, src: Path | None) -> None:
    pyproject = project / "pyproject.toml"
    deps: list[Requirement] = load_declared_deps(pyproject).requirements
    imports = find_top_level_imports(src or project)

    click.echo(json.dumps({
        "declared": [r.name + (str(r.specifier) if str(r.specifier) else "") for r in deps],
        "imports": sorted(imports),
    }, indent=2))


@cli.command("check")
@click.option("--project", type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."),
              help="Project root (contains pyproject.toml).")
def check_cmd(project: Path) -> None:
    pyproject = project / "pyproject.toml"
    declared = load_declared_deps(pyproject).requirements
    checker = VersionChecker(declared)
    outdated, unpinned = checker.check()
    click.echo(json.dumps({
        "outdated": [o.__dict__ for o in outdated],
        "unpinned": [u.__dict__ for u in unpinned],
    }, indent=2))


@cli.command("unused")
@click.option("--project", type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."),
              help="Project root (contains pyproject.toml).")
@click.option("--src", type=click.Path(path_type=Path, exists=True), default=None,
              help="Source root to scan imports. Defaults to project root.")
def unused_cmd(project: Path, src: Path | None) -> None:
    pyproject = project / "pyproject.toml"
    declared = load_declared_deps(pyproject).requirements
    imports = find_top_level_imports(src or project)
    unused = guess_unused(declared, imports)
    click.echo(json.dumps({"unused": unused}, indent=2))


@cli.command("report")
@click.option("--project", type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."),
              help="Project root (contains pyproject.toml).")
@click.option("--src", type=click.Path(path_type=Path, exists=True), default=None,
              help="Source root to scan imports. Defaults to project root.")
@click.option("--out", type=click.Path(path_type=Path), default=None, help="Path to write JSON report.")
def report_cmd(project: Path, src: Path | None, out: Path | None) -> None:
    try:
        path = generate_report(project_root=project, src_root=src, out_path=out)
        click.echo(str(path))
    except Exception as exc:  # make CLI friendly
        click.echo(f"ERROR: {exc}", err=True)
        sys.exit(1)
