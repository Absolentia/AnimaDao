from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path

import click
from packaging.requirements import Requirement

from animadao.config import load_config
from animadao.dependency_checker import guess_unused, load_declared_deps_any
from animadao.native import scan_imports
from animadao.report_generator import generate_report
from animadao.version_checker import VersionChecker


def _merge_ignore(base: set[str] | None, extra: Iterable[str] | None) -> set[str]:
    out = set(s.lower() for s in (base or set()))
    out |= {s.lower() for s in (extra or [])}
    return out


@click.group(help="AnimaDao — dependency health checker.")
def cli() -> None: ...


@cli.command("scan")
@click.option(
    "--project",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    default=Path("."),
    help="Project root.",
)
@click.option(
    "--src",
    type=click.Path(path_type=Path, exists=True),
    default=None,
    help="Source root to scan imports.",
)
def scan_cmd(project: Path, src: Path | None) -> None:
    deps: list[Requirement] = load_declared_deps_any(project).requirements
    imports = set(scan_imports([str(src or project)]))
    click.echo(
        json.dumps(
            {
                "declared": [r.name + (str(r.specifier) if str(r.specifier) else "") for r in deps],
                "imports": sorted(imports),
            },
            indent=2,
        )
    )


@cli.command("check")
@click.option(
    "--project",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    default=Path("."),
    help="Project root.",
)
@click.option(
    "--mode",
    type=click.Choice(["declared", "installed"]),
    default=None,
    help="What to compare against PyPI.",
)
@click.option("--ignore", multiple=True, help="Ignore packages (can repeat).")
@click.option("--pypi-ttl", type=int, default=None, help="PyPI cache TTL seconds (default 86400).")
@click.option("--pypi-concurrency", type=int, default=None, help="Parallel HTTP requests to PyPI (default 8).")
def check_cmd(
    project: Path,
    mode: str | None,
    ignore: tuple[str, ...],
    pypi_ttl: int | None,
    pypi_concurrency: int | None,
) -> None:
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
@click.option(
    "--project",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    default=Path("."),
    help="Project root.",
)
@click.option(
    "--src",
    "srcs",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    multiple=True,
    default=None,
    help="Source roots to scan imports (can repeat). If omitted, the project root is scanned.",
)
@click.option("--ignore", multiple=True, help="Ignore packages (can repeat).")
def unused_cmd(project: Path, srcs: tuple[Path, ...], ignore: tuple[str, ...]) -> None:
    """Report declared-but-not-imported distributions.

    - Accepts multiple ``--src`` occurrences; imports are unioned across roots.
    - Falls back to the project root when ``--src`` is not provided.
    - Ignores packages listed via ``--ignore`` (case-insensitive).
    """
    declared = load_declared_deps_any(project).requirements

    # Determine roots to scan
    roots: list[Path] = list(srcs) if srcs else [project]

    # Collect imports from all roots
    imports = set(scan_imports([str(p) for p in roots]))

    # Apply ignore list and keep stable ordering
    ig = {s.lower() for s in ignore}
    unused = [u for u in guess_unused(declared, imports) if u.lower() not in ig]
    unused = sorted(unused)

    click.echo(json.dumps({"unused": unused}, indent=2))


@cli.command("report")
@click.option(
    "--project",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    default=Path("."),
    help="Project root.",
)
@click.option(
    "--src",
    "srcs",
    type=click.Path(path_type=Path, exists=True),
    multiple=True,
    default=None,
    help="Source roots to scan imports (can repeat).",
)
@click.option("--out", type=click.Path(path_type=Path), default=None, help="Path to write report.")
@click.option("--mode", type=click.Choice(["declared", "installed"]), default=None, help="Report mode.")
@click.option("--ignore", multiple=True, help="Ignore packages (can repeat).")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "md", "html"]),
    default="json",
    help="Output format.",
)
@click.option("--pypi-ttl", type=int, default=None, help="PyPI cache TTL seconds (default 86400).")
@click.option("--pypi-concurrency", type=int, default=None, help="Parallel HTTP requests to PyPI (default 8).")
def report_cmd(
    project: Path,
    srcs: tuple[Path, ...],
    out: Path | None,
    mode: str | None,
    ignore: tuple[str, ...],
    fmt: str,
    pypi_ttl: int | None,
    pypi_concurrency: int | None,
) -> None:
    cfg = load_config(project).with_overrides(
        mode=mode,
        src=[str(p) for p in srcs] if srcs else None,
        ignore=ignore,
        ttl=pypi_ttl,
        conc=pypi_concurrency,
    )
    try:
        path = generate_report(
            project_root=project,
            src_roots=list(srcs) if srcs else None,
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
