from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

from animadao.cli import cli
from animadao.report_generator import generate_report
from animadao.version_checker import VersionChecker
from click.testing import CliRunner
from packaging.version import Version


def _pyproject_pins(tmp: Path) -> None:
    tmp.joinpath("pyproject.toml").write_text(
        dedent(
            """
            [project]
            name = "demo"
            version = "0.0.1"
            dependencies = [
              "requests==2.31.0",
              "rich==13.7.0"
            ]
            """
        ).strip(),
        encoding="utf-8",
    )


def _mkfile(root: Path, rel: str, content: str) -> Path:
    p = root.joinpath(rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def test_generate_report_multiple_srcs_unites_imports(tmp_path: Path, monkeypatch) -> None:
    # Arrange: project with two source roots: package + tests
    _pyproject_pins(tmp_path)
    pkg = tmp_path / "anima_dao"
    tests = tmp_path / "tests"
    _mkfile(pkg, "main.py", "import requests\n")
    _mkfile(tests, "test_demo.py", "import rich\nimport pytest\n")

    # Avoid network, keep all pins up-to-date
    monkeypatch.setattr(
        VersionChecker,
        "get_latest_version",
        lambda self, n: Version("2.31.0") if n == "requests" else Version("13.7.0"),
        raising=True,
    )

    out = tmp_path / "report.json"
    path = generate_report(
        project_root=tmp_path,
        src_roots=[pkg, tests],  # <-- multiple roots
        out_path=out,
        mode="declared",
        ignore=set(),
        ttl_seconds=1,
        concurrency=1,
        output_format="json",
    )
    data = json.loads(path.read_text(encoding="utf-8"))

    # Assert: both imports discovered; no unused because requests/rich used across roots
    assert "requests" in data["imports"]
    assert "rich" in data["imports"]
    # pytest is not declared, but imported in tests — OK
    assert "pytest" in data["imports"]
    assert data["unused"] == []


def test_cli_report_accepts_multiple_src_options(tmp_path: Path, monkeypatch) -> None:
    _pyproject_pins(tmp_path)
    pkg = tmp_path / "anima_dao"
    tests = tmp_path / "tests"
    _mkfile(pkg, "pkg.py", "import requests\n")
    _mkfile(tests, "test_pkg.py", "import rich\n")

    monkeypatch.setattr(
        VersionChecker,
        "get_latest_version",
        lambda self, n: Version("2.31.0") if n == "requests" else Version("13.7.0"),
        raising=True,
    )

    out = tmp_path / "rep.json"
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "report",
            "--project",
            str(tmp_path),
            "--src",
            str(pkg),
            "--src",
            str(tests),
            "--format",
            "json",
            "--out",
            str(out),
        ],
    )
    assert res.exit_code == 0, res.output
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "requests" in data["imports"] and "rich" in data["imports"]
    assert data["unused"] == []


def test_cli_unused_multiple_srcs_eliminates_false_unused(tmp_path: Path, monkeypatch) -> None:
    _pyproject_pins(tmp_path)
    pkg = tmp_path / "anima_dao"
    demos = tmp_path / "demos"
    _mkfile(pkg, "core.py", "import requests\n")
    _mkfile(demos, "example.py", "import rich\n")

    # Network-less
    monkeypatch.setattr(VersionChecker, "get_latest_version", lambda self, n: Version("99.0.0"), raising=True)

    runner = CliRunner()

    # 1) Только один src -> rich «как бы» не используется
    res1 = runner.invoke(cli, ["unused", "--project", str(tmp_path), "--src", str(pkg)])
    assert res1.exit_code == 0, res1.output
    data1 = json.loads(res1.output)
    assert "rich" in data1["unused"]

    # 2) Два src -> rich используется во втором корне
    res2 = runner.invoke(
        cli,
        ["unused", "--project", str(tmp_path), "--src", str(pkg), "--src", str(demos)],
    )
    assert res2.exit_code == 0, res2.output
    data2 = json.loads(res2.output)
    assert "rich" not in data2["unused"]


def test_config_core_src_list_used_when_cli_missing(tmp_path: Path, monkeypatch) -> None:
    # Config defines two roots
    (tmp_path / ".animadao.toml").write_text(
        dedent(
            """
            [core]
            src = ["anima_dao", "tests"]
            """
        ).strip(),
        encoding="utf-8",
    )
    _pyproject_pins(tmp_path)
    _mkfile(tmp_path / "anima_dao", "mod.py", "import requests\n")
    _mkfile(tmp_path / "tests", "test_mod.py", "import rich\n")

    monkeypatch.setattr(
        VersionChecker,
        "get_latest_version",
        lambda self, n: Version("2.31.0") if n == "requests" else Version("13.7.0"),
        raising=True,
    )

    runner = CliRunner()
    res = runner.invoke(cli, ["report", "--project", str(tmp_path), "--format", "json"])
    assert res.exit_code == 0, res.output
    # CLI prints path to the generated report; read it back
    report_path = Path(res.output.strip())
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert "requests" in data["imports"] and "rich" in data["imports"]
    assert data["unused"] == []
