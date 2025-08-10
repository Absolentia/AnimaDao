from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from .dependency_checker import load_declared_deps_any, guess_unused
from .import_scanner import find_top_level_imports
from .version_checker import VersionChecker


def generate_report(project_root: Path, src_root: Optional[Path] = None, out_path: Optional[Path] = None) -> Path:
    if not (project_root / "pyproject.toml").is_file() and not (project_root / "requirements.txt").is_file():
        raise FileNotFoundError(f"No pyproject.toml or requirements.txt in: {project_root}")

    declared = load_declared_deps_any(project_root).requirements

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
