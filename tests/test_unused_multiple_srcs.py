from __future__ import annotations

import json
from pathlib import Path

from animadao.cli import cli
from click.testing import CliRunner


def test_unused_multiple_srcs_union(tmp_path: Path) -> None:
    # pyproject с двумя пинами
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="demo"\nversion="0.0.0"\n' 'dependencies=["requests==2.31.0","rich==13.7.0"]\n',
        encoding="utf-8",
    )

    # пакет animadao использует requests
    pkg = tmp_path / "animadao"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "mod.py").write_text("import requests\n", encoding="utf-8")

    # tests используют rich
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_demo.py").write_text("import rich\n", encoding="utf-8")

    r = CliRunner()

    # 1) Сканируем только пакет -> rich считается неиспользуемым, requests — используется
    res1 = r.invoke(
        cli,
        ["unused", "--project", str(tmp_path), "--src", str(pkg)],  # один src
    )
    assert res1.exit_code == 0, res1.output
    data1 = json.loads(res1.output)
    assert "rich" in data1["unused"]
    assert "requests" not in data1["unused"]

    # 2) Пакет + tests -> оба используются, список пуст
    res2 = r.invoke(
        cli,
        [
            "unused",
            "--project",
            str(tmp_path),
            "--src",
            str(pkg),
            "--src",
            str(tests),
        ],
    )
    assert res2.exit_code == 0, res2.output
    data2 = json.loads(res2.output)
    assert "rich" not in data2["unused"]
    assert "requests" not in data2["unused"]
