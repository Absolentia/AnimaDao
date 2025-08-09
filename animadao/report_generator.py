from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from animadao.dependency_checker import load_declared_deps, guess_unused
from animadao.import_scanner import find_top_level_imports
from animadao.version_checker import VersionChecker


def generate_report(project_root: Path, src_root: Optional[Path] = None, out_path: Optional[Path] = None) -> Path:
    """
    Produce a JSON report with:
      - outdated pinned deps
      - unpinned deps
      - unused deps (heuristic by import scan)

    Args:
        project_root: path containing pyproject.toml
        src_root: source root to scan imports; defaults to project_root if None
        out_path: where to write JSON; defaults to project_root/'report.json'

    Returns:
        Path to written JSON file.
    """
    pyproject = project_root / "pyproject.toml"
    if not pyproject.is_file():
        raise FileNotFoundError(f"pyproject.toml not found at: {pyproject}")

    declared = load_declared_deps(pyproject).requirements

    src = src_root or project_root
    imports = find_top_level_imports(src)

    checker = VersionChecker(declared)
    outdated, unpinned = checker.check()

    unused = guess_unused(declared, imports)

    data = {
        "summary": {
            "declared": len(declared),
            "imports_found": len(imports),
            "outdated": len(outdated),
            "unpinned": len(unpinned),
            "unused": len(unused),
        },
        "outdated": [asdict(o) for o in outdated],
        "unpinned": [asdict(u) for u in unpinned],
        "unused": unused,
        "imports": sorted(imports),
    }

    out = out_path or (project_root / "report.json")
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return out
