from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from animadao.dependency_checker import load_declared_deps, guess_unused
from animadao.import_scanner import find_top_level_imports


def write_pyproject(tmp: Path) -> None:
    tmp.joinpath("pyproject.toml").write_text(dedent("""
        [project]
        name = "demo"
        version = "0.0.1"
        requires-python = ">=3.10"
        dependencies = [
          "requests==2.31.0",
          "numpy>=1.26",
        ]
    """).strip(), encoding="utf-8")


def test_scan_and_unused(tmp_path: Path) -> None:
    write_pyproject(tmp_path)
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)
    src.joinpath("app.py").write_text("import requests\n", encoding="utf-8")

    declared = load_declared_deps(tmp_path / "pyproject.toml").requirements
    imports = find_top_level_imports(src)
    unused = guess_unused(declared, imports)

    # requests is used, numpy is not imported -> unused should contain numpy only
    names = {r.name for r in declared}
    assert {"requests", "numpy"} <= names
    assert "numpy" in unused
    assert "requests" not in unused
