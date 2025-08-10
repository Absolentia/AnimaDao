# AnimaDao

[![ci](https://github.com/Absolentia/AnimaDao/actions/workflows/ci.yml/badge.svg)](https://github.com/Absolentia/AnimaDao/actions/workflows/ci.yml)
[![tagger](https://github.com/Absolentia/AnimaDao/actions/workflows/tag.yml/badge.svg)](https://github.com/Absolentia/AnimaDao/actions/workflows/tag.yml)
[![PyPI version](https://img.shields.io/pypi/v/anima-dao.svg)](https://pypi.org/project/anima-dao/)
![Python](https://img.shields.io/badge/python-3.13%2B-blue.svg)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**AnimaDao** is a pragmatic dependency health checker for Python projects.  
It compares **declared** dependencies with **actual imports**, flags **unused** ones, and checks **pinned** specs (`==`)
against the latest PyPI releases.  
Works with **uv** and supports three declaration styles.

---

## Features

- 🗂 **Multiple sources** of declared deps:
    1. `pyproject.toml` — **PEP 621** `[project].dependencies`
    2. `pyproject.toml` — **Poetry** `[tool.poetry.dependencies]`
    3. **`requirements.txt`** (incl. nested `-r` includes)
- 🔍 **Import scan**: walks your source tree and extracts top-level imports (AST).
- 🧹 **Unused deps**: declared but not imported (heuristic, import-name ≈ normalized dist name).
- ⏫ **Outdated pins**: checks only `==`-pinned requirements against PyPI **latest**.
- ⚙️ **Two modes**: `--mode declared` (default) and `--mode installed`.
- 🚫 **Ignore lists**: skip tool packages (e.g. `pip`, `setuptools`, `wheel`) or any custom names.
- 🧩 **Config file**: project-level `.animadao.toml` with sane defaults and CLI overrides.
- 🗃️ **PyPI cache**: TTL + ETag with configurable concurrency for faster checks.
- 📄 **Reports**: `--format json | md | html`.

---

## Requirements

- Python 3.10+
- **uv** (modern Python package/dependency manager)

---

## Installation

### With `uv`

```bash
pip install uv
uv pip install anima-dao
```

### With `pip`

```bash
pip install anima-dao
```

### From sources

1) Clone:

```bash
git clone https://github.com/Absolentia/AnimaDao.git
cd AnimaDao
```

2) Install `uv`:

```bash
pip install --upgrade pip
pip install uv
```

3) Create a virtual env:

```bash
uv venv
```

4) Install project deps:

```bash
uv sync
```

---

## Configuration

Create `.animadao.toml` in your project root (optional):

```toml
[core]
mode = "declared"          # declared | installed
src = ["src", "app"]       # optional, source roots for import scan

# PyPI cache / concurrency
pypi_ttl_seconds = 86400   # default: 24h
pypi_concurrency = 8       # default: 8 parallel requests

[ignore]
distributions = ["pip", "setuptools", "wheel"]
imports = []
```

CLI flags always override config values.

---

## Usage (CLI)

All commands accept a project root (where either `pyproject.toml` or `requirements.txt` resides) and an optional source
root to scan imports.

### Scan: declared vs imports

```bash
uv run animadao scan --project . --src src
```

### Check against PyPI

**Declared dependencies (default mode):**

```bash
uv run animadao check --project . --mode declared --ignore pip --ignore setuptools
```

**Installed packages in the current venv:**

```bash
uv run animadao check --project . --mode installed --pypi-ttl 43200 --pypi-concurrency 16
```

### Find unused deps (declared but not imported)

```bash
uv run animadao unused --project . --src src --ignore pip --ignore wheel
```

### Generate report

**JSON:**

```bash
uv run animadao report --project . --src src --out report.json --format json
```

**Markdown:**

```bash
uv run animadao report --project . --src src --out report.md --format md
```

**HTML:**

```bash
uv run animadao report --project . --src src --out report.html --format html
```

Example `report.json`:

```json
{
  "summary": {
    "declared": 12,
    "imports_found": 34,
    "outdated": 2,
    "unpinned": 7,
    "unused": 3
  },
  "outdated": [
    {
      "name": "requests",
      "current": "2.31.0",
      "latest": "2.32.3"
    }
  ],
  "unpinned": [
    {
      "name": "numpy",
      "spec": ">=1.26"
    }
  ],
  "unused": [
    "rich",
    "typer"
  ],
  "imports": [
    "requests",
    "json",
    "..."
  ],
  "mode": "declared"
}
```

---

## Supported dependency sources & priority

When resolving declared dependencies, AnimaDao uses the first matching source:

1. `pyproject.toml` — **PEP 621** `[project].dependencies` (+ `[project.optional-dependencies]` merged)
2. `pyproject.toml` — **Poetry** `[tool.poetry.dependencies]`
    - `python = "^3.10"` is ignored
    - Exact versions become `name==X.Y.Z`
    - Caret `^` ranges are converted to PEP 440 intervals (best-effort)
    - Poetry **dev/group** deps are **not** included
3. `requirements.txt` — plain lines + nested includes via `-r` / `--requirement`

> Only the **first** detected source is used to avoid mixing ecosystems.

---

## How it works (quick notes)

- **Import mapping:** compares normalized distribution names (`-` → `_`) with top-level imports. Known alias:
  `beautifulsoup4` ↔ `bs4`.
- **Modes:**
    - `declared`: checks only `==` pins from declarations; non-pinned specs appear under `unpinned`.
    - `installed`: checks versions of packages currently installed in the environment.
- **Networking:** PyPI queries via `httpx` with timeouts, using a TTL/ETag cache; failures fall back to cached data.

---

## CI & Releases

- **CI (`ci.yml`)**: runs `pytest` with `uv` on every push/PR to `main` (matrix: Python 3.10–3.13).
- **Tagger (`tag.yml`)**: manual tagging `vX.Y.Z`.
- **Publish**: recommended trigger by tag `v*` or via `workflow_run` after tagger.

Create a release:

```bash
# bump version in pyproject.toml
git commit -am "chore: bump version to 0.1.1"
git tag -a v0.1.1 -m "v0.1.1"
git push origin v0.1.1
```

---

## Support matrix

- Python: 3.10 / 3.11 / 3.12 / 3.13
- OS: Linux, macOS, Windows
- Packaging: PEP 621 (project), Poetry, requirements.txt
- Manager: `uv` (install & run)

---

## Troubleshooting

- **`No module named build`**  
  `uv pip install build twine` or `uv sync --extra dev`.

- **Hatch: “Unable to determine which files to ship”**  
  Ensure package directory exists and add to `pyproject.toml`:
  ```toml
  [tool.hatch.build.targets.wheel]
  packages = ["anima_dao"]
  ```

- **Publish doesn’t start after tagger**  
  Events from `GITHUB_TOKEN` don’t trigger other workflows. Push tag with a PAT or use `workflow_run` trigger.

- **403 after moving repo to org**  
  Update remote: `git remote set-url origin git@github.com:<ORG>/AnimaDao.git` and check org permissions/SSO.

---

## Contributing

```bash
pip install uv
uv sync --extra dev
uv run pytest -vvvv
```

Please keep type hints (3.10+), docstrings and comments in English, and add tests for new loaders/edge cases.

## License