from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:  # Python 3.11+
    import tomllib as tomli  # type: ignore
except Exception:  # Python 3.10
    import tomli  # type: ignore

from packaging.requirements import Requirement


@dataclass(frozen=True)
class DeclaredDeps:
    """Container for declared dependencies."""
    requirements: list[Requirement]


def _normalize_dist_name(name: str) -> str:
    """
    Normalize distribution name to a Python import-ish form.
    Very basic heuristic: lower, replace '-' with '_'.
    """
    return name.lower().replace("-", "_")


def load_declared_deps(pyproject_path: Path) -> DeclaredDeps:
    """
    Load declared dependencies from pyproject.toml:
    - PEP 621: [project].dependencies and [project.optional-dependencies].* (ignored for 'unused' by default)
    - Poetry legacy isn't a target here by design (keep MVP tight).

    Returns:
        DeclaredDeps: list of parsed packaging.Requirement objects.
    """
    data = tomli.loads(pyproject_path.read_text(encoding="utf-8"))
    project = data.get("project", {}) or {}

    deps_raw: list[str] = list(project.get("dependencies") or [])
    # optional-dependencies kept for completeness, but we don't treat them as required
    # You can extend logic later to include selected extras.
    opt = project.get("optional-dependencies") or {}
    # flatten optional deps but tag them by marker if needed later
    for _extra, items in opt.items():
        deps_raw.extend(items or [])

    requirements: list[Requirement] = []
    for s in deps_raw:
        try:
            requirements.append(Requirement(s))
        except Exception:
            # Ignore invalid lines gracefully; report could add a warning bucket if desired
            continue
    return DeclaredDeps(requirements=requirements)


def guess_unused(requirements: Iterable[Requirement], imported: Iterable[str]) -> list[str]:
    """
    Heuristic: a dep is 'unused' if its normalized dist name (or common alias)
    does not appear among top-level imports.

    We check:
      - normalized dist name (e.g., 'beautifulsoup4' -> 'beautifulsoup4'/'bs4')
      - also try a dash->underscore transform

    Returns:
        list[str]: distribution names deemed unused.
    """
    imported_set = {name.lower() for name in imported}
    unused: list[str] = []

    for req in requirements:
        name = req.name
        norm = _normalize_dist_name(name)
        candidates = {norm}

        # Common alias for BeautifulSoup
        if name.lower() in {"beautifulsoup4", "bs4"}:
            candidates.update({"bs4", "beautifulsoup4"})

        if imported_set.isdisjoint(candidates):
            unused.append(name)

    return sorted(unused)
