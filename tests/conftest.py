from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from packaging.version import Version


@pytest.fixture
def mk_project(tmp_path: Path):
    """
    Create a tiny project with configurable deps and imports.
    Returns: dict with paths: root, pkg, tests.
    """

    def _make(
        *,
        name: str = "demo",
        deps: list[str] = None,
        pkg_imports: list[str] = None,
        test_imports: list[str] = None,
        pkg_dir: str = "anima_dao",
    ) -> dict[str, Path]:
        d_deps = deps or []
        p_imps = pkg_imports or []
        t_imps = test_imports or []

        # pyproject.toml
        (tmp_path / "pyproject.toml").write_text(
            dedent(
                f"""
                [project]
                name = "{name}"
                version = "0.0.0"
                dependencies = {d_deps!r}
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        # package files
        pkg = tmp_path / pkg_dir
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "mod.py").write_text("".join(f"import {m}\n" for m in p_imps), encoding="utf-8")

        # tests
        tests = tmp_path / "tests"
        tests.mkdir(parents=True, exist_ok=True)
        (tests / "test_mod.py").write_text(
            "".join(f"import {m}\n" for m in t_imps) or "def test_ok():\n    assert True\n",
            encoding="utf-8",
        )

        return {"root": tmp_path, "pkg": pkg, "tests": tests}

    return _make


@pytest.fixture
def freeze_latest(monkeypatch):
    """
    Monkeypatch VersionChecker.get_latest_version to avoid network.
    Pass mapping {'requests': '2.31.0', ...}; unknown -> huge version (never outdated).
    """

    def _apply(mapping: dict[str, str]):
        from animadao.version_checker import VersionChecker

        def _get_latest(_self, name: str) -> Version:
            v = mapping.get(name, "9999.0.0")
            return Version(v)

        monkeypatch.setattr(VersionChecker, "get_latest_version", _get_latest, raising=True)

    return _apply
