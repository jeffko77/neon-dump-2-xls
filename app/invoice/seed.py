from __future__ import annotations

from app.invoice.db import db_session
from app.invoice.seed_data import import_bundled_seed


def seed_if_empty() -> bool:
    with db_session() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM schools").fetchone()["c"]
        if count:
            return False

    try:
        import_bundled_seed(replace=True)
        return True
    except (FileNotFoundError, ValueError):
        pass

    from app.invoice.access_import import default_accdb_path, import_default_sources

    accdb_path = default_accdb_path()
    if accdb_path.exists():
        try:
            import_default_sources(accdb_path=accdb_path, replace=True)
            return True
        except FileNotFoundError:
            pass

    return False
