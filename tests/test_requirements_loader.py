from __future__ import annotations

from pathlib import Path
from packaging.requirements import Requirement
from textwrap import dedent
import json

from animadao.dependency_checker import load_declared_deps_any, guess_unused
from animadao.import_scanner import find_top_level_imports
from animadao.report_generator import generate_report
from animadao.version_checker import VersionChecker
from packaging.version import Version


def test_requirements_txt_basic(tmp_path: Path, monkeypatch) -> None:
    # requirements.txt with pinned + unpinned
    (tmp_path / "requirements.txt").write_text(dedent("""
        requests==2.31.0
        numpy>=1.26
        # comment
    """).strip(), encoding="utf-8")

    # source imports only requests
    src = tmp_path / "src"
    src.mkdir()
    (src / "mod.py").write_text("import requests\n", encoding="utf-8")

    declared = load_declared_deps_any(tmp_path).requirements
    names = {r.name for r in declared}
    assert names == {"requests", "numpy"}

    imports = find_top_level_imports(src)
    unused = guess_unused(declared, imports)
    assert "numpy" in unused and "requests" not in unused

    # monkeypatch PyPI latest
    monkeypatch.setattr(VersionChecker, "get_latest_version",
                        lambda self, n: Version("2.32.0") if n == "requests" else Version("1.26.0"),
                        raising=True)
    outdated, unpinned = VersionChecker(declared).check()
    assert any(o.name == "requests" and o.current == "2.31.0" for o in outdated)
    assert any(u.name == "numpy" for u in unpinned)

    # report end-to-end
    out = generate_report(project_root=tmp_path, src_root=src)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["summary"]["declared"] == 2
    assert data["summary"]["unused"] == 1
