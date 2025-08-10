from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import animadao.precommit_gate as gate
from animadao.version_checker import VersionChecker
from click.testing import CliRunner
from packaging.version import Version


def _write_pyproject(tmp: Path, body: str) -> None:
    tmp.joinpath("pyproject.toml").write_text(dedent(body).strip(), encoding="utf-8")


def _write_src_file(tmp: Path, rel: str, content: str) -> None:
    p = tmp.joinpath(rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_gate_declared_outdated_fails(tmp_path: Path, monkeypatch) -> None:
    _write_pyproject(
        tmp_path,
        """
        [project]
        name = "demo"
        version = "0.0.1"
        dependencies = ["requests==2.31.0"]
        """,
    )
    _write_src_file(tmp_path, "src/app.py", "import requests\n")

    # requests latest is newer -> outdated=1
    monkeypatch.setattr(
        VersionChecker,
        "get_latest_version",
        lambda self, n: Version("2.32.0") if n == "requests" else Version("1.0.0"),
        raising=True,
    )

    runner = CliRunner()
    res = runner.invoke(
        gate.main,
        ["--project", str(tmp_path), "--mode", "declared", "--fail-if-outdated"],
    )
    assert res.exit_code == 2, res.output
    assert '"outdated": 1' in res.output


def test_gate_declared_unpinned_fails(tmp_path: Path, monkeypatch) -> None:
    _write_pyproject(
        tmp_path,
        """
        [project]
        name = "demo"
        version = "0.0.1"
        dependencies = ["numpy>=1.26"]
        """,
    )
    # avoid network: any value is fine; unpinned rule will trigger
    monkeypatch.setattr(VersionChecker, "get_latest_version", lambda self, n: Version("1.26.0"), raising=True)

    runner = CliRunner()
    res = runner.invoke(
        gate.main,
        ["--project", str(tmp_path), "--mode", "declared", "--fail-if-unpinned"],
    )
    assert res.exit_code == 2, res.output
    assert '"unpinned": 1' in res.output


def test_gate_declared_max_unused_fails(tmp_path: Path, monkeypatch) -> None:
    _write_pyproject(
        tmp_path,
        """
        [project]
        name = "demo"
        version = "0.0.1"
        dependencies = ["requests==2.31.0", "rich==13.7.0"]
        """,
    )
    # code uses only requests -> rich is unused
    _write_src_file(tmp_path, "pkg/main.py", "import requests\n")

    # no outdated: latest equals current for both
    monkeypatch.setattr(
        VersionChecker,
        "get_latest_version",
        lambda self, n: Version("2.31.0") if n == "requests" else Version("13.7.0"),
        raising=True,
    )

    runner = CliRunner()
    res = runner.invoke(
        gate.main,
        ["--project", str(tmp_path), "--mode", "declared", "--max-unused", "0"],
    )
    assert res.exit_code == 2, res.output
    assert '"unused": 1' in res.output


def test_gate_ignore_suppresses_failure(tmp_path: Path, monkeypatch) -> None:
    _write_pyproject(
        tmp_path,
        """
        [project]
        name = "demo"
        version = "0.0.1"
        dependencies = ["requests==2.31.0"]
        """,
    )
    _write_src_file(tmp_path, "app.py", "import requests\n")

    # make requests outdated, but ignore it via CLI
    monkeypatch.setattr(
        VersionChecker,
        "get_latest_version",
        lambda self, n: Version("2.32.0") if n == "requests" else Version("1.0.0"),
        raising=True,
    )

    runner = CliRunner()
    res = runner.invoke(
        gate.main,
        [
            "--project",
            str(tmp_path),
            "--mode",
            "declared",
            "--fail-if-outdated",
            "--ignore",
            "requests",
        ],
    )
    assert res.exit_code == 0, res.output
    # Summary still counts declared/imports, but outdated is hidden by ignore
    assert '"outdated": 0' in res.output


def test_gate_installed_mode_outdated_fails(tmp_path: Path, monkeypatch) -> None:
    # Fake importlib.metadata.distributions()
    class FakeDist:
        def __init__(self, name: str, version: str) -> None:
            self.metadata = {"Name": name}
            self.version = version

    import importlib.metadata as im

    monkeypatch.setattr(
        im,
        "distributions",
        lambda: [FakeDist("requests", "2.31.0"), FakeDist("numpy", "1.26.0")],
        raising=True,
    )
    # Only requests is outdated
    monkeypatch.setattr(
        VersionChecker,
        "get_latest_version",
        lambda self, n: Version("2.32.0") if n == "requests" else Version("1.26.0"),
        raising=True,
    )

    runner = CliRunner()
    res = runner.invoke(gate.main, ["--project", str(tmp_path), "--mode", "installed", "--fail-if-outdated"])
    assert res.exit_code == 2, res.output
    assert '"outdated": 1' in res.output
    assert '"mode": "installed"' in res.output


def test_gate_config_file_and_overrides(tmp_path: Path, monkeypatch) -> None:
    # Config ignores 'requests'
    tmp_path.joinpath(".animadao.toml").write_text(
        dedent(
            """
            [core]
            mode = "declared"

            [ignore]
            distributions = ["requests"]
            """
        ).strip(),
        encoding="utf-8",
    )
    _write_pyproject(
        tmp_path,
        """
        [project]
        name = "demo"
        version = "0.0.1"
        dependencies = ["requests==2.31.0"]
        """,
    )
    _write_src_file(tmp_path, "main.py", "import requests\n")

    # requests would be outdated, but config should ignore it
    monkeypatch.setattr(
        VersionChecker,
        "get_latest_version",
        lambda self, n: Version("2.32.0") if n == "requests" else Version("1.0.0"),
        raising=True,
    )

    runner = CliRunner()
    res = runner.invoke(gate.main, ["--project", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert '"mode": "declared"' in res.output
    assert '"outdated": 0' in res.output


def test_gate_config_mode_cli_override(tmp_path: Path, monkeypatch) -> None:
    # Config sets installed, CLI overrides to declared
    tmp_path.joinpath(".animadao.toml").write_text(
        dedent(
            """
            [core]
            mode = "installed"
            """
        ).strip(),
        encoding="utf-8",
    )
    _write_pyproject(
        tmp_path,
        """
        [project]
        name = "demo"
        version = "0.0.1"
        dependencies = ["rich==13.7.0"]
        """,
    )
    _write_src_file(tmp_path, "x.py", "print('no imports here')\n")

    # No outdated at all
    monkeypatch.setattr(
        VersionChecker,
        "get_latest_version",
        lambda self, n: Version("13.7.0"),
        raising=True,
    )

    runner = CliRunner()
    res = runner.invoke(gate.main, ["--project", str(tmp_path), "--mode", "declared", "--max-unused", "0"])
    # Should run in declared mode (per CLI), find 1 unused (rich), fail on policy
    assert res.exit_code == 2, res.output
    assert '"mode": "declared"' in res.output
    assert '"unused": 1' in res.output
