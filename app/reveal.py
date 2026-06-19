from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def allowed_export_roots(exports_dir: Path, app_directory: Path) -> list[Path]:
    roots: list[Path] = []
    for candidate in (exports_dir, app_directory / "exports"):
        try:
            roots.append(candidate.expanduser().resolve())
        except OSError:
            continue
    return roots


def validate_reveal_path(path: str, *, exports_dir: Path, app_directory: Path) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise ValueError(f"Path does not exist: {path}")

    roots = allowed_export_roots(exports_dir, app_directory)
    if not any(resolved == root or root in resolved.parents for root in roots):
        raise ValueError("Path is outside the allowed export directories")

    return resolved


def reveal_path(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606
        return
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
        return
    subprocess.run(["xdg-open", str(path)], check=False)
