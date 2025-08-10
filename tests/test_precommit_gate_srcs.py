from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from animadao.precommit_gate import main as gate
from animadao.version_checker import VersionChecker
from click.testing import CliRunner
from packaging.version import Version


def _pp(tmp: Path, body: str) -> None:
    tmp.joinpath("pyproject.toml").write_text(dedent(body).strip(), encoding="utf-8")


def test_gate_multiple_srcs_ok(tmp_path: Path, monkeypatch) -> None:
    _pp(
        tmp_path,
        """
        [project]
        name = "demo"
        version = "0.0.0"
        dependencies = ["requests==1.0.0", "rich==1.0.0"]
        """,
    )

    # два корня исходников
    (tmp_path / "pkg").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "pkg/a.py").write_text("import requests\n", encoding="utf-8")
    (tmp_path / "tests/t.py").write_text("import rich\n", encoding="utf-8")

    # 💡 без сети: latest == pinned → нет outdated
    monkeypatch.setattr(
        VersionChecker,
        "get_latest_version",
        lambda self, name: Version("1.0.0"),
        raising=True,
    )

    res = CliRunner().invoke(
        gate,
        [
            "--project",
            str(tmp_path),
            "--src",
            str(tmp_path / "pkg"),
            "--src",
            str(tmp_path / "tests"),
            "--mode",
            "declared",
        ],
    )
    assert res.exit_code == 0, res.output
