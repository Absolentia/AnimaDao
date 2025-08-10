from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from animadao.dependency_checker import guess_unused, load_declared_deps_any
from animadao.import_scanner import find_top_level_imports


def test_poetry_dependencies(tmp_path: Path) -> None:
    # Minimal Poetry-style pyproject
    (tmp_path / "pyproject.toml").write_text(
        dedent("""
        [tool.poetry]
        name = "demo"
        version = "0.0.1"
        description = "demo"

        [tool.poetry.dependencies]
        python = "^3.10"
        requests = "2.31.0"
        numpy = "^1.26"

        [tool.poetry.group.dev.dependencies]
        pytest = "^8.0"
    """).strip(),
        encoding="utf-8",
    )

    src = tmp_path / "pkg"
    src.mkdir()
    (src / "a.py").write_text("import requests\n", encoding="utf-8")

    declared = load_declared_deps_any(tmp_path).requirements
    names = {r.name for r in declared}
    # dev deps (pytest) не должны попасть
    assert {"requests", "numpy"} <= names and "pytest" not in names

    imports = find_top_level_imports(src)
    unused = guess_unused(declared, imports)
    assert "numpy" in unused and "requests" not in unused
