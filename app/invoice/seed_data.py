from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.connection import app_dir, is_frozen
from app.invoice.service import import_all

SEED_FILENAME = "invoice_database_seed.json"


def bundled_seed_path() -> Path | None:
    candidates: list[Path] = []
    if is_frozen():
        candidates.extend(
            [
                app_dir() / "data" / SEED_FILENAME,
                app_dir() / "_internal" / "data" / SEED_FILENAME,
            ]
        )
    else:
        candidates.append(app_dir() / "data" / SEED_FILENAME)

    for path in candidates:
        if path.exists():
            return path
    return None


def load_bundled_seed() -> dict[str, Any]:
    path = bundled_seed_path()
    if path is None:
        raise FileNotFoundError(
            f"Bundled seed file not found ({SEED_FILENAME}). "
            "Run scripts/export_invoice_seed.py to regenerate it."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if "schools" not in data:
        raise ValueError("Seed file missing 'schools' array")
    return data


def import_bundled_seed(*, replace: bool = True) -> dict[str, int]:
    data = load_bundled_seed()
    counts = import_all(data, replace=replace)
    return {
        "schools": counts["schools"],
        "invoices": counts["invoices"],
        "payments": counts["payments"],
        "games": counts["games"],
    }
