from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from animadao.config import load_config


def test_config_defaults(tmp_path: Path) -> None:
    # Без файла конфигурации берутся дефолты
    cfg = load_config(tmp_path)
    assert cfg.mode == "declared"
    assert cfg.src is None
    assert cfg.ignore_distributions is None
    assert cfg.ignore_imports is None
    assert cfg.pypi_ttl_seconds == 86400
    assert cfg.pypi_concurrency == 8


def test_config_file_loading(tmp_path: Path) -> None:
    (tmp_path / ".animadao.toml").write_text(dedent("""
        [core]
        mode = "installed"
        src = ["src", "app"]
        pypi_ttl_seconds = 1234
        pypi_concurrency = 5

        [ignore]
        distributions = ["pip", "Setuptools"]
        imports = ["__future__"]
    """).strip(), encoding="utf-8")

    cfg = load_config(tmp_path)
    assert cfg.mode == "installed"
    assert cfg.src == ["src", "app"]
    assert cfg.pypi_ttl_seconds == 1234
    assert cfg.pypi_concurrency == 5
    assert cfg.ignore_distributions == {"pip", "setuptools"}  # lower-cased
    assert cfg.ignore_imports == {"__future__"}


def test_config_overrides(tmp_path: Path) -> None:
    (tmp_path / ".animadao.toml").write_text(dedent("""
        [core]
        mode = "declared"
        pypi_ttl_seconds = 3600

        [ignore]
        distributions = ["wheel"]
    """).strip(), encoding="utf-8")

    cfg = load_config(tmp_path).with_overrides(
        mode="installed",
        src=["src"],
        ignore=["pip"],
        ttl=10,
        conc=2,
    )
    assert cfg.mode == "installed"
    assert cfg.src == ["src"]
    # wheel из файла + pip из override
    assert cfg.ignore_distributions == {"wheel", "pip"}
    assert cfg.pypi_ttl_seconds == 10
    assert cfg.pypi_concurrency == 2
