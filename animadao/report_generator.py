from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Iterable

from packaging.requirements import Requirement

from .dependency_checker import load_declared_deps_any, guess_unused
from .import_scanner import find_top_level_imports
from .version_checker import VersionChecker


def _apply_ignore(names: Iterable[str], ignore: set[str] | None) -> list[str]:
    if not ignore:
        return list(names)
    ig = {s.lower() for s in ignore}
    return [n for n in names if n.lower() not in ig]


def _render_md(data: dict) -> str:
    lines: list[str] = []
    s = data["summary"]
    lines.append(f"# AnimaDao report\n")
    lines.append(
        f"**declared:** {s['declared']}  \n**imports:** {s['imports_found']}  \n**outdated:** {s['outdated']}  \n**unpinned:** {s['unpinned']}  \n**unused:** {s['unused']}\n")
    if data["outdated"]:
        lines.append("## Outdated\n\n| package | current | latest |\n|---|---:|---:|")
        for o in data["outdated"]:
            lines.append(f"| {o['name']} | {o['current']} | {o['latest']} |")
        lines.append("")
    if data["unpinned"]:
        lines.append("## Unpinned\n\n| package | spec |\n|---|---|")
        for u in data["unpinned"]:
            lines.append(f"| {u['name']} | `{u['spec']}` |")
        lines.append("")
    if data["unused"]:
        lines.append("## Unused\n\n" + ", ".join(sorted(data["unused"])) + "\n")
    return "\n".join(lines)


def _render_html(data: dict) -> str:
    def table(rows: list[list[str]], head: list[str]) -> str:
        th = "".join(f"<th>{h}</th>" for h in head)
        trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
        return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"

    s = data["summary"]
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>AnimaDao report</title>"
        "<style>body{font-family:system-ui,monospace;padding:20px} table{border-collapse:collapse} td,th{border:1px solid #ddd;padding:6px 10px}</style>"
        "</head><body>",
        f"<h1>AnimaDao report</h1>",
        f"<p><b>declared:</b> {s['declared']} &nbsp; <b>imports:</b> {s['imports_found']} &nbsp; <b>outdated:</b> {s['outdated']} &nbsp; <b>unpinned:</b> {s['unpinned']} &nbsp; <b>unused:</b> {s['unused']}</p>",
    ]
    if data["outdated"]:
        rows = [[o["name"], o["current"], o["latest"]] for o in data["outdated"]]
        parts += ["<h2>Outdated</h2>", table(rows, ["package", "current", "latest"])]
    if data["unpinned"]:
        rows = [[u["name"], u["spec"]] for u in data["unpinned"]]
        parts += ["<h2>Unpinned</h2>", table(rows, ["package", "spec"])]
    if data["unused"]:
        parts += ["<h2>Unused</h2>", "<p>" + ", ".join(sorted(data["unused"])) + "</p>"]
    parts.append("</body></html>")
    return "\n".join(parts)


def generate_report(
        project_root: Path,
        src_root: Optional[Path] = None,
        out_path: Optional[Path] = None,
        *,
        mode: str = "declared",  # declared | installed
        ignore: set[str] | None = None,  # игнор пакетов по имени (case-insensitive)
        ttl_seconds: int = 86400,
        concurrency: int = 8,
        output_format: str = "json",  # json | md | html
) -> Path:
    """
    Генерирует отчёт (json/md/html) по выбранному режиму.
    """
    if not (project_root / "pyproject.toml").is_file() and not (project_root / "requirements.txt").is_file():
        raise FileNotFoundError(f"No pyproject.toml or requirements.txt in: {project_root}")

    ignore = {s.lower() for s in (ignore or set())}

    declared_reqs: list[Requirement] = []
    imports: set[str] = set()

    if mode == "declared":
        declared_reqs = load_declared_deps_any(project_root).requirements
        imports = find_top_level_imports(src_root or project_root)
        # Version check on declared
        checker = VersionChecker(ttl_seconds=ttl_seconds, concurrency=concurrency)
        outdated, unpinned = checker.check_declared(declared_reqs)
    elif mode == "installed":
        # соберём установленные пакеты
        from importlib import metadata as im
        installed = {d.metadata["Name"]: d.version for d in im.distributions()}
        checker = VersionChecker(ttl_seconds=ttl_seconds, concurrency=concurrency)
        outdated, unpinned = checker.check_installed(installed)
        # для installed импорт-скан имеет меньший смысл, но оставим для консистентности
        imports = find_top_level_imports(src_root or project_root)
    else:
        raise ValueError("mode must be 'declared' or 'installed'")

    # Игнорируем пакеты в отчёте
    outdated = [o for o in outdated if o.name.lower() not in ignore]
    unpinned = [u for u in unpinned if u.name.lower() not in ignore]

    unused: list[str] = []
    if mode == "declared":
        unused = [u for u in guess_unused(declared_reqs, imports) if u.lower() not in ignore]

    data = {
        "summary": {
            "declared": len(declared_reqs) if mode == "declared" else 0,
            "imports_found": len(imports),
            "outdated": len(outdated),
            "unpinned": len(unpinned),
            "unused": len(unused),
        },
        "outdated": [asdict(o) for o in outdated],
        "unpinned": [asdict(u) for u in unpinned],
        "unused": unused,
        "imports": sorted(imports),
        "mode": mode,
    }

    # Пишем файл
    out = out_path or (project_root / ("report." + ("json" if output_format == "json" else output_format)))
    if output_format == "json":
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    elif output_format == "md":
        out.write_text(_render_md(data), encoding="utf-8")
    elif output_format == "html":
        out.write_text(_render_html(data), encoding="utf-8")
    else:
        raise ValueError("output_format must be one of: json|md|html")
    return out
