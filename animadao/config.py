from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import tomllib as tomli  # 3.11+
except Exception:  # 3.10
    import tomli  # type: ignore


@dataclass(frozen=True)
class Config:
    mode: str = "declared"  # declared | installed
    src: list[str] = None  # список путей; если None -> [project_root]
    ignore_distributions: set[str] = None  # lower-case имена дистрибутивов
    ignore_imports: set[str] = None  # lower-case имена импортов
    pypi_ttl_seconds: int = 86400  # кеш PyPI (по умолчанию сутки)
    pypi_concurrency: int = 8  # параллелизм запросов к PyPI

    def with_overrides(
            self,
            mode: str | None = None,
            src: Iterable[str] | None = None,
            ignore: Iterable[str] | None = None,
            ttl: int | None = None,
            conc: int | None = None,
    ) -> "Config":
        return Config(
            mode=mode or self.mode,
            src=list(src) if src is not None else (self.src or []),
            ignore_distributions=set((self.ignore_distributions or set())) | (
                {s.lower() for s in ignore} if ignore else set()),
            ignore_imports=self.ignore_imports or set(),
            pypi_ttl_seconds=ttl if ttl is not None else self.pypi_ttl_seconds,
            pypi_concurrency=conc if conc is not None else self.pypi_concurrency,
        )


def _load_one(path: Path) -> dict:
    try:
        return tomli.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_config(project_root: Path) -> Config:
    """
    Загружает конфиг в порядке приоритета:
    1) <project>/.animadao.toml
    2) $HOME/.config/animadao/config.toml
    Отсутствующие поля -> значения по умолчанию.
    """
    conf = Config()
    candidates = [
        project_root / ".animadao.toml",
        Path.home() / ".config" / "animadao" / "config.toml",
    ]
    data: dict = {}
    for p in candidates:
        if p.is_file():
            data = _load_one(p)
            break

    core = data.get("core", {}) or {}
    ignore = data.get("ignore", {}) or {}

    mode = str(core.get("mode", conf.mode))
    src = core.get("src")
    if isinstance(src, str):
        src = [src]
    src_list = [str(s) for s in (src or [])]

    ttl = int(core.get("pypi_ttl_seconds", conf.pypi_ttl_seconds))
    conc = int(core.get("pypi_concurrency", conf.pypi_concurrency))

    ig_dist = {s.lower() for s in (ignore.get("distributions") or [])}
    ig_imp = {s.lower() for s in (ignore.get("imports") or [])}

    return Config(
        mode=mode if mode in {"declared", "installed"} else "declared",
        src=src_list or None,
        ignore_distributions=ig_dist or None,
        ignore_imports=ig_imp or None,
        pypi_ttl_seconds=ttl,
        pypi_concurrency=conc,
    )
