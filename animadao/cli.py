from __future__ import annotations

from pathlib import Path
import json
import sys
from typing import Iterable

import click
from packaging.requirements import Requirement

from .config import load_config
from .dependency_checker import load_declared_deps_any, guess_unused
from .import_scanner import find_top_level_imports
from .report_generator import generate_report
from .version_checker import VersionChecker


def _merge_ignore(base: set[str] | None, extra: Iterable[str] | None) -> set[str]:
    out = set(s.lower() for s in (base or set()))
    out |= {s.lower() for s in (extra or [])}
    return out


@click.group(help="AnimaDao — dependency health checker.")
def cli() -> None:
    ...


@cli.command("scan")
@click.option("--project", type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."),
              help="Project root.")
@click.option("--src", type=click.Path(path_type=Path, exists=True), default=None, help="Source root to scan imports.")
def scan_cmd(project: Path, src: Path | None) -> None:
    deps: list[Requirement] = load_declared_deps_any(project).requirements
    imports = find_top_level_imports(src or project)
    click.echo(json.dumps({
        "declared": [r.name + (str(r.specifier) if str(r.specifier) else "") for r in deps],
        "imports": sorted(imports),
    }, indent=2))


@cli.command("check")
@click.option("--project", type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."),
              help="Project root.")
@click.option("--mode", type=click.Choice(["declared", "installed"]), default=None,
              help="What to compare against PyPI.")
@click.option("--ignore", multiple=True, help="Ignore packages (can repeat).")
@click.option("--pypi-ttl", type=int, default=None, help="PyPI cache TTL seconds (default 86400).")
@click.option("--pypi-concurrency", type=int, default=None, help="Parallel HTTP requests to PyPI (default 8).")
def check_cmd(project: Path, mode: str | None, ignore: tuple[str, ...], pypi_ttl: int | None,
              pypi_concurrency: int | None) -> None:
    cfg = load_config(project).with_overrides(mode=mode, ignore=ignore, ttl=pypi_ttl, conc=pypi_concurrency)

    checker = VersionChecker(ttl_seconds=cfg.pypi_ttl_seconds, concurrency=cfg.pypi_concurrency)
    if cfg.mode == "declared":
        declared = load_declared_deps_any(project).requirements
        outdated, unpinned = checker.check_declared(declared)
    else:
        from importlib import metadata as im
        installed = {d.metadata["Name"]: d.version for d in im.distributions()}
        outdated, unpinned = checker.check_installed(installed)

    ig = cfg.ignore_distributions or set()
    out = {
        "outdated": [o.__dict__ for o in outdated if o.name.lower() not in ig],
        "unpinned": [u.__dict__ for u in unpinned if u.name.lower() not in ig],
        "mode": cfg.mode,
    }
    click.echo(json.dumps(out, indent=2))


@cli.command("unused")
@click.option("--project", type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."),
              help="Project root.")
@click.option("--src", type=click.Path(path_type=Path, exists=True), default=None, help="Source root to scan imports.")
@click.option("--ignore", multiple=True, help="Ignore packages (can repeat).")
def unused_cmd(project: Path, src: Path | None, ignore: tuple[str, ...]) -> None:
    declared = load_declared_deps_any(project).requirements
    imports = find_top_level_imports(src or project)
    ig = {s.lower() for s in ignore}
    unused = [u for u in guess_unused(declared, imports) if u.lower() not in ig]
    click.echo(json.dumps({"unused": unused}, indent=2))


@cli.command("report")
@click.option("--project", type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."),
              help="Project root.")
@click.option("--src", type=click.Path(path_type=Path, exists=True), default=None, help="Source root to scan imports.")
@click.option("--out", type=click.Path(path_type=Path), default=None, help="Path to write report.")
@click.option("--mode", type=click.Choice(["declared", "installed"]), default=None, help="Report mode.")
@click.option("--ignore", multiple=True, help="Ignore packages (can repeat).")
@click.option("--format", "fmt", type=click.Choice(["json", "md", "html"]), default="json", help="Output format.")
@click.option("--pypi-ttl", type=int, default=None, help="PyPI cache TTL seconds (default 86400).")
@click.option("--pypi-concurrency", type=int, default=None, help="Parallel HTTP requests to PyPI (default 8).")
def report_cmd(
        project: Path,
        src: Path | None,
        out: Path | None,
        mode: str | None,
        ignore: tuple[str, ...],
        fmt: str,
        pypi_ttl: int | None,
        pypi_concurrency: int | None,
) -> None:
    cfg = load_config(project).with_overrides(mode=mode, src=[str(src)] if src else None, ignore=ignore, ttl=pypi_ttl,
                                              conc=pypi_concurrency)
    try:
        path = generate_report(
            project_root=project,
            src_root=src,
            out_path=out,
            mode=cfg.mode,
            ignore=cfg.ignore_distributions or set(),
            ttl_seconds=cfg.pypi_ttl_seconds,
            concurrency=cfg.pypi_concurrency,
            output_format=fmt,
        )
        click.echo(str(path))
    except Exception as exc:
        click.echo(f"ERROR: {exc}", err=True)
        sys.exit(1)
