from __future__ import annotations

import ast
from pathlib import Path


def find_top_level_imports(src_root: Path) -> set[str]:
    """
    Walk Python files under `src_root` and collect top-level import names.
    We record only the top module part: e.g. `requests.adapters` -> `requests`.

    Returns:
        set[str]: unique top-level import names found.
    """
    imports: set[str] = set()
    for py in src_root.rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8")
        except Exception:
            continue
        try:
            tree = ast.parse(text, filename=str(py))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top:
                        imports.add(top)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    if top:
                        imports.add(top)
    return imports
