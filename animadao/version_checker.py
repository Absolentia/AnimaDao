from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Iterable

import httpx
from packaging.requirements import Requirement
from packaging.version import Version, parse as parse_version


@dataclass(frozen=True)
class Outdated:
    """Represents a pinned requirement that is behind PyPI latest."""
    name: str
    current: str
    latest: str


@dataclass(frozen=True)
class Unpinned:
    """Represents a requirement that isn't pinned with '==' (we don't check it)."""
    name: str
    spec: str


class PyPICache:
    """
    Very small file cache for /pypi/{name}/json with ETag + TTL.
    File content: {"version": "...", "etag": "...", "ts": <epoch>}
    """

    def __init__(self, ttl_seconds: int = 86400, cache_dir: Optional[Path] = None) -> None:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")).expanduser()
        self.dir = (cache_dir or (base / "animadao" / "pypi")).resolve()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_seconds

    def _path(self, name: str) -> Path:
        return self.dir / f"{name.lower()}.json"

    def load(self, name: str) -> tuple[Optional[str], Optional[str], float]:
        p = self._path(name)
        if not p.is_file():
            return None, None, 0.0
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data.get("version"), data.get("etag"), float(data.get("ts", 0))
        except Exception:
            return None, None, 0.0

    def save(self, name: str, version: str, etag: Optional[str]) -> None:
        p = self._path(name)
        payload = {"version": version, "etag": etag, "ts": time.time()}
        p.write_text(json.dumps(payload), encoding="utf-8")


class VersionChecker:
    """
    Backward-compatible version checker.

    - __init__ now accepts optional `requirements` (legacy behavior),
      plus keyword-only TTL & concurrency (reserved).
    - get_latest_version(name) is back (sync) for monkeypatching in tests.
    - check_declared(Optional[list[Requirement]]) and check_installed(mapping)
      compare against PyPI latest using cache.
    """

    PYPI_JSON = "https://pypi.org/pypi/{name}/json"

    def __init__(self, requirements: list[Requirement] | None = None, *, ttl_seconds: int = 86400,
                 concurrency: int = 8) -> None:
        self._requirements: list[Requirement] = requirements or []
        self.cache = PyPICache(ttl_seconds=ttl_seconds)
        # `concurrency` зарезервирован под будущий async-bulk, здесь не критичен
        self.concurrency = max(1, int(concurrency))

    # -------- compatibility method (used by tests to monkeypatch) --------
    def get_latest_version(self, name: str) -> Optional[Version]:
        """
        Return latest version from PyPI for `name`, with ETag/TTL cache.
        Sync on purpose so tests can monkeypatch it easily.
        """
        cached_ver, etag, ts = self.cache.load(name)
        # valid TTL?
        if cached_ver and (time.time() - ts) < self.cache.ttl:
            try:
                return parse_version(cached_ver)
            except Exception:
                pass

        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(self.PYPI_JSON.format(name=name), headers=headers)
                if r.status_code == 304 and cached_ver:
                    return parse_version(cached_ver)
                r.raise_for_status()
                data = r.json()
                v_str = data["info"]["version"]
                new_etag = r.headers.get("ETag")
                self.cache.save(name, v_str, new_etag)
                return parse_version(v_str)
        except Exception:
            if cached_ver:
                try:
                    return parse_version(cached_ver)
                except Exception:
                    return None
            return None

    # -------- declared --------
    def check_declared(self, requirements: Iterable[Requirement] | None = None) -> tuple[
        list[Outdated], list[Unpinned]]:
        reqs = list(requirements) if requirements is not None else list(self._requirements)
        outdated: list[Outdated] = []
        unpinned: list[Unpinned] = []

        pins: dict[str, Version] = {}
        for req in reqs:
            try:
                if req.marker and not req.marker.evaluate():
                    continue
            except Exception:
                pass
            equals = [sp for sp in req.specifier if sp.operator == "=="]
            if not equals:
                spec = str(req.specifier) if str(req.specifier) else "*"
                unpinned.append(Unpinned(name=req.name, spec=spec))
            else:
                try:
                    pins[req.name] = parse_version(equals[-1].version)
                except Exception:
                    pass

        # Если метод замокан — уважаем monkeypatch и вызываем его по одному
        use_monkeypatched = type(self).get_latest_version is not VersionChecker.get_latest_version

        for name, cur in pins.items():
            latest = self.get_latest_version(name) if use_monkeypatched else self.get_latest_version(name)
            if latest is not None and cur < latest:
                outdated.append(Outdated(name=name, current=str(cur), latest=str(latest)))

        return outdated, unpinned

    # -------- installed --------
    def check_installed(self, installed: dict[str, str]) -> tuple[list[Outdated], list[Unpinned]]:
        outdated: list[Outdated] = []
        for name, cur_str in installed.items():
            try:
                cur = parse_version(cur_str)
            except Exception:
                continue
            latest = self.get_latest_version(name)
            if latest is not None and cur < latest:
                outdated.append(Outdated(name=name, current=str(cur), latest=str(latest)))
        return outdated, []

    # -------- backward-compat shims --------
    def check(self):
        """
        Backward-compatible adapter for old tests:
        returns (outdated, unpinned) for declared requirements attached to the instance.
        """
        return self.check_declared()

    def check_versions(self):
        """
        Older name used previously in the project/tests.
        Delegates to `check_declared()`.
        """
        return self.check_declared()
