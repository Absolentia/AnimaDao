# AnimaDao

[![tests](https://github.com/Absolentia/AnimaDao/actions/workflows/ci.yml/badge.svg)](https://github.com/Absolentia/AnimaDao/actions/workflows/ci.yml)

AnimaDao is a tiny, pragmatic dependency health checker for Python projects:

- Reads declared deps from `pyproject.toml` (PEP 621).
- Scans your source tree for actual imports.
- Flags unused deps (declared but never imported).
- Checks pinned deps (`==`) against the latest PyPI version.
- Writes a JSON report.

## Requirements

- Python 3.10+
- **uv** (modern asynchronous package manager for Python)

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/your-repository/anima-dao.git
    cd anima-dao
    ```

2. Install `uv` – the modern Python dependency manager:

    ```bash
    pip install --upgrade pip
    pip install uv
    ```

3. Create a virtual env:

    ```bash
    uv venv
    ```

4. Install Python dependencies with `uv`

    ```bash
    uv sync
    ```
    This will install dependencies listed in the `pyproject.toml` file.

## Usage

1. **Check Dependencies**: Scans the project's dependencies.
    ```bash
    uv run animadao scan --project . --src src
    ```

2. **Check Versions**: Checks if your dependencies are up-to-date.
    ```bash
    uv run animadao check --project .
    uv run animadao unused --project . --src src
    ```

3. **Generate Report**: Generates a report on outdated or unused dependencies.
    ```bash
    uv run animadao report --project . --src src --out report.json
    ```

## Running Tests

To run the tests, use **pytest**:

```bash
uv run pytest
```
