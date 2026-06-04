from __future__ import annotations

from pathlib import Path

from src.config import ROOT_DIR


def portable_path(path: Path | str) -> str:
    """Return a repository-relative path when the file lives inside the repo."""
    candidate = Path(path)
    try:
        return str(candidate.resolve().relative_to(ROOT_DIR.resolve()))
    except (OSError, RuntimeError, ValueError):
        return str(path)
