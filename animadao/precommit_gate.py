from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import click

from animadao.config import load_config
from animadao.dependency_checker import guess_unused, load_declared_deps_any
from animadao.native import scan_imports
from animadao.version_checker import VersionChecker


def _lower_set(items: Iterable[str] | None) -> set[str]:
    return {s.lower() for s in (items or [])}


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--project", type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."), help="Project root."
)
@click.option(
    "--src",
    "srcs",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    multiple=True,
    help="Source roots to scan imports (can repeat).",
)
@click.option(
    "--mode",
    type=click.Choice(["declared", "installed"]),
    default=None,
    help="Check declared pins or installed packages.",
)
@click.option("--ignore", multiple=True, help="Ignore packages (case-insensitive). Can repeat.")
@click.option("--pypi-ttl", type=int, default=None, help="PyPI cache TTL seconds (default 86400).")
@click.option("--pypi-concurrency", type=int, default=None, help="Parallel PyPI requests (default 8).")
@click.option("--fail-if-outdated", is_flag=True, default=False, help="Fail if any outdated packages found.")
@click.option(
    "--fail-if-unpinned", is_flag=True, default=False, help="Fail if any unpinned requirements (declared mode)."
)
@click.option("--max-unused", type=int, default=None, help="Fail if count of unused declared deps exceeds this value.")
def main(
    project: Path,
    srcs: tuple[Path, ...],
    mode: str | None,
    ignore: tuple[str, ...],
    pypi_ttl: int | None,
    pypi_concurrency: int | None,
    fail_if_outdated: bool,
    fail_if_unpinned: bool,
    max_unused: int | None,
) -> None:
    """Pre-commit gate for AnimaDao."""
    cfg = load_config(project).with_overrides(
        mode=mode,
        ignore=ignore,
        ttl=pypi_ttl,
        conc=pypi_concurrency,
        src=[str(p) for p in srcs] if srcs else None,
    )
    ig = _lower_set(cfg.ignore_distributions)
    roots: list[Path] = [Path(p) for p in (cfg.src or [])] or [project]

    checker = VersionChecker(ttl_seconds=cfg.pypi_ttl_seconds, concurrency=cfg.pypi_concurrency)

    outdated = []
    unpinned = []
    unused: list[str] = []
    imports_found = 0
    declared_count = 0

    if cfg.mode == "declared":
        declared = load_declared_deps_any(project).requirements
        declared_count = len(declared)

        # combine imports from all roots
        imports = set(scan_imports([str(r) for r in roots]))
        imports_found = len(imports)

        outdated, unpinned = checker.check_declared(declared)
        unused = guess_unused(declared, imports)
    else:
        from importlib import metadata as im

        installed = {d.metadata["Name"]: d.version for d in im.distributions()}
        outdated, _ = checker.check_installed(installed)

    # apply ignore
    outdated = [o for o in outdated if o.name.lower() not in ig]
    unpinned = [u for u in unpinned if u.name.lower() not in ig]
    unused = [u for u in unused if u.lower() not in ig]

    summary = {
        "mode": cfg.mode,
        "declared": declared_count,
        "imports_found": imports_found,
        "outdated": len(outdated),
        "unpinned": len(unpinned),
        "unused": len(unused),
    }
    print("AnimaDao summary:", __import__("json").dumps(summary, indent=2))

    violations: list[str] = []
    if fail_if_outdated and summary["outdated"] > 0:
        violations.append(f"outdated={summary['outdated']}")
    if cfg.mode == "declared":
        if fail_if_unpinned and summary["unpinned"] > 0:
            violations.append(f"unpinned={summary['unpinned']}")
        if max_unused is not None and summary["unused"] > max_unused:
            violations.append(f"unused={summary['unused']} > {max_unused}")

    raise SystemExit(2 if violations else 0)
