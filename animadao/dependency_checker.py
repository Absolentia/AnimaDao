from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import tomllib as tomli  # Python 3.11+
except Exception:
    import tomli  # type: ignore

from packaging.requirements import Requirement


@dataclass(frozen=True)
class DeclaredDeps:
    """Container for declared dependencies."""
    requirements: list[Requirement]


def _normalize_dist_name(name: str) -> str:
    return name.lower().replace("-", "_")


# ---------- PEP 621 (project) ----------

def load_declared_deps(pyproject_path: Path) -> DeclaredDeps:
    """Existing PEP 621 loader (kept for backward compatibility)."""
    data = tomli.loads(pyproject_path.read_text(encoding="utf-8"))
    project = data.get("project", {}) or {}
    deps_raw: list[str] = list(project.get("dependencies") or [])
    opt = project.get("optional-dependencies") or {}
    for _extra, items in (opt or {}).items():
        deps_raw.extend(items or [])

    requirements: list[Requirement] = []
    for s in deps_raw:
        try:
            requirements.append(Requirement(s))
        except Exception:
            continue
    return DeclaredDeps(requirements=requirements)


# ---------- Poetry ([tool.poetry.dependencies]) ----------

def _caret_to_spec(ver: str) -> str:
    """
    Convert caret constraints ^X.Y.Z to PEP 440 range '>=X.Y.Z,<next' (basic).
    """
    import re
    parts = [int(p) for p in re.split(r"[._-]", ver) if p.isdigit()]
    while len(parts) < 3:
        parts.append(0)
    major, minor, patch = parts[:3]
    if major > 0:
        upper = f"{major + 1}.0.0"
    elif minor > 0:
        upper = f"0.{minor + 1}.0"
    else:
        upper = "0.1.0"
    return f">={major}.{minor}.{patch},<{upper}"


def _poetry_value_to_req(name: str, val: object) -> str:
    """
    Turn Poetry dep value into a Requirement string.
    - "2.31.0" -> "name==2.31.0"
    - "^1.26"  -> "name>=1.26,<2.0" (or next minor for 0.x)
    - "*" or {} -> "name"
    - {version="^1.2", extras=[...]} -> include just version (extras ignored for MVP)
    """
    if isinstance(val, str):
        if val == "*" or val.strip() == "":
            return name
        if val.startswith("^"):
            return f"{name}{_prepend_spec(_caret_to_spec(val[1:]))}"
        # raw exact version
        if val[0].isdigit():
            return f"{name}=={val}"
        # already a spec like ">=1.0"
        return f"{name}{_prepend_spec(val)}"
    if isinstance(val, dict):
        ver = str(val.get("version", "")).strip()
        if not ver or ver == "*":
            return name
        if ver.startswith("^"):
            return f"{name}{_prepend_spec(_caret_to_spec(ver[1:]))}"
        if ver[0].isdigit():
            return f"{name}=={ver}"
        return f"{name}{_prepend_spec(ver)}"
    return name


def _prepend_spec(spec: str) -> str:
    spec = spec.strip()
    return f"{spec}" if spec.startswith((">", "<", "=", "!")) else f"=={spec}"


def load_poetry_deps(pyproject_path: Path) -> DeclaredDeps:
    data = tomli.loads(pyproject_path.read_text(encoding="utf-8"))
    tool = data.get("tool", {}) or {}
    poetry = tool.get("poetry", {}) or {}
    deps = poetry.get("dependencies") or {}
    requirements: list[Requirement] = []
    for name, val in deps.items():
        if name.lower() == "python":
            continue
        try:
            req_str = _poetry_value_to_req(name, val)
            requirements.append(Requirement(req_str))
        except Exception:
            continue
    return DeclaredDeps(requirements=requirements)


# ---------- requirements.txt ----------

def _parse_requirements_file(path: Path, seen: set[Path] | None = None, depth: int = 0) -> list[str]:
    if seen is None:
        seen = set()
    if depth > 3:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []
    seen.add(path.resolve())
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r ") or line.startswith("--requirement "):
            ref = line.split(maxsplit=1)[1].strip()
            sub = (path.parent / ref).resolve()
            if sub not in seen:
                out.extend(_parse_requirements_file(sub, seen, depth + 1))
            continue
        out.append(line)
    return out


def load_requirements_txt(project_root: Path) -> DeclaredDeps:
    req_file = project_root / "requirements.txt"
    specs = _parse_requirements_file(req_file)
    requirements: list[Requirement] = []
    for s in specs:
        try:
            requirements.append(Requirement(s))
        except Exception:
            continue
    return DeclaredDeps(requirements=requirements)


# ---------- Универсальный лоадер ----------

def load_declared_deps_any(project_root: Path) -> DeclaredDeps:
    """
    Priority:
      1) pyproject.toml [project] (PEP 621)
      2) pyproject.toml [tool.poetry.dependencies]
      3) requirements.txt
    """
    pyproject = project_root / "pyproject.toml"
    if pyproject.is_file():
        data = tomli.loads(pyproject.read_text(encoding="utf-8"))
        if "project" in data:
            return load_declared_deps(pyproject)
        if "tool" in data and "poetry" in (data.get("tool") or {}):
            return load_poetry_deps(pyproject)
    req = project_root / "requirements.txt"
    if req.is_file():
        return load_requirements_txt(project_root)
    raise FileNotFoundError("No dependencies source found (pyproject or requirements.txt)")


def guess_unused(requirements: Iterable[Requirement], imported: Iterable[str]) -> list[str]:
    imported_set = {name.lower() for name in imported}
    unused: list[str] = []
    for req in requirements:
        name = req.name
        norm = _normalize_dist_name(name)
        candidates = {norm}
        if name.lower() in {"beautifulsoup4", "bs4"}:
            candidates.update({"bs4", "beautifulsoup4"})
        if imported_set.isdisjoint(candidates):
            unused.append(name)
    return sorted(unused)
