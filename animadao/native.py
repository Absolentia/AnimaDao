from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

try:
    from anima_core import scan_imports as _scan_imports_rust
except Exception:
    _scan_imports_rust = None  # type: ignore[assignment]


def scan_imports(paths: Iterable[Path | str]) -> list[str]:
    """Collect top-level imports across multiple roots (Rust fast-path, Python fallback)."""
    norm_paths = [Path(p) for p in paths]
    if _scan_imports_rust:
        return list(_scan_imports_rust([str(p) for p in norm_paths]))
    from .import_scanner import find_top_level_imports

    acc: set[str] = set()
    for p in norm_paths:
        acc |= find_top_level_imports(p)
    return sorted(acc)
