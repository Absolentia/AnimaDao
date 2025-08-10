# tests/test_src_parametrize.py
from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest
from animadao import import_scanner
from animadao.cli import cli
from animadao.version_checker import VersionChecker
from click.testing import CliRunner
from packaging.version import Version


@pytest.fixture(autouse=True)
def clear_scanner_cache():
    # На случай LRU-кэша у сканера — чистим между тестами
    if hasattr(import_scanner.find_top_level_imports, "cache_clear"):
        import_scanner.find_top_level_imports.cache_clear()


@pytest.fixture
def mk_project(tmp_path: Path):
    def _make(
        *,
        deps: list[str],
        pkg_imports: list[str],
        test_imports: list[str],
    ) -> dict[str, Path]:
        (tmp_path / "pyproject.toml").write_text(
            dedent(
                f"""
                [project]
                name = "demo"
                version = "0.0.0"
                dependencies = {deps!r}
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        # Используем НЕЙТРАЛЬНОЕ имя пакета, чтобы не пересекаться с самим anima_dao
        pkg = tmp_path / "pkg"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "mod.py").write_text("".join(f"import {m}\n" for m in pkg_imports), encoding="utf-8")

        tests = tmp_path / "tests"
        tests.mkdir(parents=True, exist_ok=True)
        (tests / "test_mod.py").write_text(
            "".join(f"import {m}\n" for m in test_imports) or "def test_ok():\n    assert True\n",
            encoding="utf-8",
        )

        return {"root": tmp_path, "pkg": pkg, "tests": tests}

    return _make


@pytest.fixture(autouse=True)
def freeze_latest(monkeypatch):
    # Без сети и без "outdated"
    def _get_latest(_self, name: str) -> Version:
        return Version("9999.0.0")

    monkeypatch.setattr(VersionChecker, "get_latest_version", _get_latest, raising=True)


@pytest.mark.parametrize(
    "src_args, expect_rich_unused, expect_requests_unused",
    [
        # 1) Сканируем только пакет -> rich «как бы» не используется (лежит в tests), requests — используется
        (lambda p: ["--src", str(p["pkg"])], True, False),
        # 2) Пакет + tests -> оба используются
        (lambda p: ["--src", str(p["pkg"]), "--src", str(p["tests"])], False, False),
        # 3) Корень проекта (.) -> захватит и pkg, и tests
        (lambda p: ["--src", str(p["root"])], False, False),
    ],
)
def test_unused_parametrized_multiple_srcs(mk_project, src_args, expect_rich_unused, expect_requests_unused):
    paths = mk_project(
        deps=["requests==2.31.0", "rich==13.7.0"],
        pkg_imports=["requests"],  # в пакете
        test_imports=["rich", "pytest"],  # в tests
    )

    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["unused", "--project", str(paths["root"])] + src_args(paths),
    )
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    unused = set(map(str.lower, data["unused"]))

    assert ("rich" in unused) is expect_rich_unused
    assert ("requests" in unused) is expect_requests_unused
