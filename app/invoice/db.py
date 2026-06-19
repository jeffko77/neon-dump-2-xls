from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.connection import app_dir, is_frozen

SCHEMA = """
CREATE TABLE IF NOT EXISTS schools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_name TEXT NOT NULL UNIQUE,
    address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    field_location TEXT,
    subsite TEXT,
    varsity_game_time TEXT,
    jv_game_time TEXT,
    rank INTEGER,
    parkway_district INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS school_sports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    sport TEXT NOT NULL,
    UNIQUE(school_id, sport)
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    season_year INTEGER NOT NULL,
    sport TEXT NOT NULL,
    base_amount REAL NOT NULL DEFAULT 110.0,
    revision_amount REAL NOT NULL DEFAULT 0,
    dual_sport_fee REAL NOT NULL DEFAULT 0,
    ranking_services REAL NOT NULL DEFAULT 0,
    c_team_scheduling REAL NOT NULL DEFAULT 0,
    fh_ranking_services REAL NOT NULL DEFAULT 0,
    address_note TEXT,
    collection_status TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    amount_paid REAL,
    date_paid TEXT,
    payment_method TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_date TEXT NOT NULL,
    game_time TEXT,
    level TEXT,
    home_school_id INTEGER REFERENCES schools(id) ON DELETE SET NULL,
    away_school_id INTEGER REFERENCES schools(id) ON DELETE SET NULL,
    field_location TEXT,
    season_year INTEGER,
    sport TEXT NOT NULL DEFAULT 'Lacrosse'
);

CREATE INDEX IF NOT EXISTS idx_school_sports_school_id ON school_sports(school_id);
CREATE INDEX IF NOT EXISTS idx_invoices_school_id ON invoices(school_id);
CREATE INDEX IF NOT EXISTS idx_payments_invoice_id ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_games_game_date ON games(game_date);
CREATE INDEX IF NOT EXISTS idx_games_home_school_id ON games(home_school_id);
CREATE INDEX IF NOT EXISTS idx_games_away_school_id ON games(away_school_id);
"""


def database_path() -> Path:
    if is_frozen() and __import__("sys").platform == "win32":
        base = Path.home() / "Documents" / "InvoiceDatabase"
    else:
        base = app_dir() / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base / "invoices.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(database_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db_session() as conn:
        conn.executescript(SCHEMA)


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}
