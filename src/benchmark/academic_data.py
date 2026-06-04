from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AcademicDataStatus:
    provider: str
    configured: bool
    reachable: bool
    status: str
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "configured": self.configured,
            "reachable": self.reachable,
            "status": self.status,
            "detail": self.detail,
        }


def check_wrds_configuration() -> AcademicDataStatus:
    username = os.getenv("WRDS_USERNAME", "").strip()
    if not username:
        return AcademicDataStatus(
            provider="wrds",
            configured=False,
            reachable=False,
            status="missing_credentials",
            detail="Set WRDS_USERNAME and complete WRDS account setup before testing academic market-data access.",
        )

    try:
        import wrds  # type: ignore[import-not-found]
    except ImportError:
        return AcademicDataStatus(
            provider="wrds",
            configured=True,
            reachable=False,
            status="missing_optional_dependency",
            detail='Install optional dependencies with `pip install -e ".[wrds]"`.',
        )

    try:
        connection = wrds.Connection(wrds_username=username)
        libraries = connection.list_libraries()
        connection.close()
    except Exception as exc:  # pragma: no cover - depends on local credentials/network
        return AcademicDataStatus(
            provider="wrds",
            configured=True,
            reachable=False,
            status="connection_failed",
            detail=f"{type(exc).__name__}: {exc}",
        )

    useful_libraries = sorted(
        library
        for library in libraries
        if library.lower().startswith(("crsp", "comp", "ibes", "taq"))
    )
    return AcademicDataStatus(
        provider="wrds",
        configured=True,
        reachable=True,
        status="available",
        detail="Accessible finance libraries: " + (", ".join(useful_libraries[:20]) or "none detected"),
    )
