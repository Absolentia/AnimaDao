from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

from animadao.report_generator import generate_report


def test_report(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "pyproject.toml").write_text(
        dedent("""
        [project]
        name = "demo"
        version = "0.0.1"
        requires-python = ">=3.10"
        dependencies = [
          "requests==2.31.0",
          "numpy>=1.26",
        ]
    """).strip(),
        encoding="utf-8",
    )

    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("import requests\n", encoding="utf-8")

    # Avoid real network
    from animadao.version_checker import VersionChecker
    from packaging.version import Version

    monkeypatch.setattr(
        VersionChecker,
        "get_latest_version",
        lambda self, n: Version("2.32.0") if n == "requests" else Version("1.26.0"),
        raising=True,
    )

    out = generate_report(project_root=tmp_path, src_root=src)
    data = json.loads(out.read_text(encoding="utf-8"))

    assert out.name == "report.json"
    assert data["summary"]["declared"] == 2
    assert data["summary"]["unused"] == 1
    assert any(o["name"] == "requests" for o in data["outdated"])
