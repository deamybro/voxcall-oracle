from __future__ import annotations

import os
import platform
from dataclasses import dataclass

from utils.kraken_cli import is_paper_mode, kraken_available


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def runtime_checks() -> list[Check]:
    return [
        Check("Python", True, platform.python_version()),
        Check(
            "Speechmatics API key",
            bool(os.getenv("SPEECHMATICS_API_KEY")),
            "configured" if os.getenv("SPEECHMATICS_API_KEY") else "missing; demo/upload fallback still works",
        ),
        Check(
            "Featherless API key",
            bool(os.getenv("FEATHERLESS_API_KEY")),
            "configured" if os.getenv("FEATHERLESS_API_KEY") else "missing; deterministic demo analyst is active",
        ),
        Check(
            "Kraken CLI",
            kraken_available(),
            "installed" if kraken_available() else "missing; app will show intended paper/live command",
        ),
        Check("Kraken mode", True, "paper" if is_paper_mode() else "live"),
    ]


def readiness_summary() -> dict[str, object]:
    checks = runtime_checks()
    return {
        "ready": all(check.ok for check in checks if check.name in {"Python"}),
        "checks": [check.__dict__ for check in checks],
    }
