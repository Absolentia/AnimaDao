from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

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


class VersionChecker:
    """
    Checks declared, marker-satisfied, pinned requirements (==) against PyPI latest.
    """

    PYPI_JSON = "https://pypi.org/pypi/{name}/json"

    def __init__(self, requirements: list[Requirement]) -> None:
        self._requirements = requirements

    def _marker_ok(self, req: Requirement) -> bool:
        try:
            return bool(req.marker.evaluate()) if req.marker is not None else True
        except Exception:
            return True

    def _pinned_version(self, req: Requirement) -> Optional[Version]:
        # Only consider '==' pins as "current"
        equals = [sp for sp in req.specifier if sp.operator == "=="]
        if not equals:
            return None
        try:
            return parse_version(equals[-1].version)
        except Exception:
            return None

    def get_latest_version(self, name: str) -> Optional[Version]:
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(self.PYPI_JSON.format(name=name))
                r.raise_for_status()
                data = r.json()
            v_str = data["info"]["version"]
            return parse_version(v_str)
        except Exception:
            return None

    def check(self) -> tuple[list[Outdated], list[Unpinned]]:
        outdated: list[Outdated] = []
        unpinned: list[Unpinned] = []

        for req in self._requirements:
            if not self._marker_ok(req):
                continue

            pinned = self._pinned_version(req)
            if pinned is None:
                spec = str(req.specifier) if str(req.specifier) else "*"
                unpinned.append(Unpinned(name=req.name, spec=spec))
                continue

            latest = self.get_latest_version(req.name)
            if latest is None:
                continue
            if pinned < latest:
                outdated.append(Outdated(name=req.name, current=str(pinned), latest=str(latest)))

        return outdated, unpinned
