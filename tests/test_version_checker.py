from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from packaging.requirements import Requirement

from animadao.version_checker import VersionChecker


def test_check_versions_monkeypatched(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "pyproject.toml").write_text(dedent("""
        [project]
        name = "demo"
        version = "0.0.1"
        requires-python = ">=3.10"
        dependencies = [
          "requests==2.31.0",
          "numpy>=1.26",
        ]
    """).strip(), encoding="utf-8")

    reqs = [
        Requirement("requests==2.31.0"),
        Requirement("numpy>=1.26"),
    ]
    checker = VersionChecker(reqs)

    def fake_latest(name: str):
        # pretend PyPI has a newer requests and same numpy (ignored because unpinned)
        return {"requests": "2.32.0"}.get(name)

    monkeypatch.setattr(checker, "get_latest_version",
                        lambda n: None if (v := fake_latest(
                            n)) is None else checker.get_latest_version.__annotations__.get("return").__call__(v),
                        raising=False)
    # simpler: monkeypatch to return Version object directly
    from packaging.version import Version
    monkeypatch.setattr(checker, "get_latest_version",
                        lambda n: Version("2.32.0") if n == "requests" else Version("1.26.0"),
                        raising=True)

    outdated, unpinned = checker.check()
    assert any(o.name == "requests" and o.current == "2.31.0" and o.latest == "2.32.0" for o in outdated)
    assert any(u.name == "numpy" for u in unpinned)
