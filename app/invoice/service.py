from __future__ import annotations

import sqlite3
from typing import Any

from app.invoice.db import db_session, row_to_dict
from app.invoice.models import (
    Game,
    GameCreate,
    GameUpdate,
    Invoice,
    InvoiceCreate,
    InvoiceUpdate,
    Payment,
    PaymentCreate,
    PaymentUpdate,
    School,
    SchoolCreate,
    SchoolUpdate,
    invoice_total,
)


def _school_sports(conn: sqlite3.Connection, school_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT sport FROM school_sports WHERE school_id = ? ORDER BY sport",
        (school_id,),
    ).fetchall()
    return [row["sport"] for row in rows]


def _set_school_sports(conn: sqlite3.Connection, school_id: int, sports: list[str]) -> None:
    conn.execute("DELETE FROM school_sports WHERE school_id = ?", (school_id,))
    for sport in sorted({s.strip() for s in sports if s.strip()}):
        conn.execute(
            "INSERT INTO school_sports (school_id, sport) VALUES (?, ?)",
            (school_id, sport),
        )


def _school_from_row(conn: sqlite3.Connection, row: sqlite3.Row) -> School:
    data = row_to_dict(row)
    assert data is not None
    sports = _school_sports(conn, data["id"])
    return School(
        id=data["id"],
        school_name=data["school_name"],
        address=data["address"],
        city=data["city"],
        state=data["state"],
        zip=data["zip"],
        field_location=data["field_location"],
        subsite=data["subsite"],
        varsity_game_time=data["varsity_game_time"],
        jv_game_time=data["jv_game_time"],
        rank=data["rank"],
        parkway_district=bool(data["parkway_district"]),
        sports=sports,
    )


def list_schools() -> list[School]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM schools ORDER BY rank IS NULL, rank, school_name"
        ).fetchall()
        return [_school_from_row(conn, row) for row in rows]


def get_school(school_id: int) -> School | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM schools WHERE id = ?", (school_id,)).fetchone()
        if row is None:
            return None
        return _school_from_row(conn, row)


def create_school(payload: SchoolCreate) -> School:
    with db_session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO schools (
                school_name, address, city, state, zip, field_location, subsite,
                varsity_game_time, jv_game_time, rank, parkway_district
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.school_name.strip(),
                payload.address,
                payload.city,
                payload.state,
                payload.zip,
                payload.field_location,
                payload.subsite,
                payload.varsity_game_time,
                payload.jv_game_time,
                payload.rank,
                1 if payload.parkway_district else 0,
            ),
        )
        school_id = cursor.lastrowid
        assert school_id is not None
        _set_school_sports(conn, school_id, payload.sports)
        row = conn.execute("SELECT * FROM schools WHERE id = ?", (school_id,)).fetchone()
        assert row is not None
        return _school_from_row(conn, row)


def update_school(school_id: int, payload: SchoolUpdate) -> School | None:
    existing = get_school(school_id)
    if existing is None:
        return None

    merged = existing.model_copy(update=payload.model_dump(exclude_unset=True, exclude={"sports"}))
    sports = payload.sports if payload.sports is not None else existing.sports

    with db_session() as conn:
        conn.execute(
            """
            UPDATE schools SET
                school_name = ?, address = ?, city = ?, state = ?, zip = ?,
                field_location = ?, subsite = ?, varsity_game_time = ?, jv_game_time = ?,
                rank = ?, parkway_district = ?
            WHERE id = ?
            """,
            (
                merged.school_name.strip(),
                merged.address,
                merged.city,
                merged.state,
                merged.zip,
                merged.field_location,
                merged.subsite,
                merged.varsity_game_time,
                merged.jv_game_time,
                merged.rank,
                1 if merged.parkway_district else 0,
                school_id,
            ),
        )
        _set_school_sports(conn, school_id, sports)
        row = conn.execute("SELECT * FROM schools WHERE id = ?", (school_id,)).fetchone()
        assert row is not None
        return _school_from_row(conn, row)


def delete_school(school_id: int) -> bool:
    with db_session() as conn:
        cursor = conn.execute("DELETE FROM schools WHERE id = ?", (school_id,))
        return cursor.rowcount > 0


def _invoice_from_row(row: sqlite3.Row, paid: float) -> Invoice:
    data = row_to_dict(row)
    assert data is not None
    total = invoice_total(
        base_amount=data["base_amount"],
        revision_amount=data["revision_amount"],
        dual_sport_fee=data["dual_sport_fee"],
        ranking_services=data["ranking_services"],
        c_team_scheduling=data["c_team_scheduling"],
        fh_ranking_services=data["fh_ranking_services"],
    )
    return Invoice(
        id=data["id"],
        school_id=data["school_id"],
        season_year=data["season_year"],
        sport=data["sport"],
        base_amount=data["base_amount"],
        revision_amount=data["revision_amount"],
        dual_sport_fee=data["dual_sport_fee"],
        ranking_services=data["ranking_services"],
        c_team_scheduling=data["c_team_scheduling"],
        fh_ranking_services=data["fh_ranking_services"],
        address_note=data["address_note"],
        collection_status=data["collection_status"],
        notes=data["notes"],
        created_at=data["created_at"],
        school_name=data.get("school_name"),
        total_amount=total,
        amount_paid=round(paid, 2),
        balance_due=round(total - paid, 2),
    )


def list_invoices() -> list[Invoice]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT i.*, s.school_name,
                   COALESCE(SUM(p.amount_paid), 0) AS amount_paid
            FROM invoices i
            JOIN schools s ON s.id = i.school_id
            LEFT JOIN payments p ON p.invoice_id = i.id
            GROUP BY i.id
            ORDER BY i.season_year DESC, s.school_name, i.sport
            """
        ).fetchall()
        return [_invoice_from_row(row, row["amount_paid"]) for row in rows]


def get_invoice(invoice_id: int) -> Invoice | None:
    with db_session() as conn:
        row = conn.execute(
            """
            SELECT i.*, s.school_name,
                   COALESCE(SUM(p.amount_paid), 0) AS amount_paid
            FROM invoices i
            JOIN schools s ON s.id = i.school_id
            LEFT JOIN payments p ON p.invoice_id = i.id
            WHERE i.id = ?
            GROUP BY i.id
            """,
            (invoice_id,),
        ).fetchone()
        if row is None:
            return None
        return _invoice_from_row(row, row["amount_paid"])


def create_invoice(payload: InvoiceCreate) -> Invoice:
    with db_session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO invoices (
                school_id, season_year, sport, base_amount, revision_amount,
                dual_sport_fee, ranking_services, c_team_scheduling,
                fh_ranking_services, address_note, collection_status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.school_id,
                payload.season_year,
                payload.sport.strip(),
                payload.base_amount,
                payload.revision_amount,
                payload.dual_sport_fee,
                payload.ranking_services,
                payload.c_team_scheduling,
                payload.fh_ranking_services,
                payload.address_note,
                payload.collection_status,
                payload.notes,
            ),
        )
        invoice_id = cursor.lastrowid
        assert invoice_id is not None
    invoice = get_invoice(invoice_id)
    assert invoice is not None
    return invoice


def update_invoice(invoice_id: int, payload: InvoiceUpdate) -> Invoice | None:
    existing = get_invoice(invoice_id)
    if existing is None:
        return None

    merged = existing.model_copy(update=payload.model_dump(exclude_unset=True))

    with db_session() as conn:
        conn.execute(
            """
            UPDATE invoices SET
                school_id = ?, season_year = ?, sport = ?, base_amount = ?,
                revision_amount = ?, dual_sport_fee = ?, ranking_services = ?,
                c_team_scheduling = ?, fh_ranking_services = ?, address_note = ?,
                collection_status = ?, notes = ?
            WHERE id = ?
            """,
            (
                merged.school_id,
                merged.season_year,
                merged.sport.strip(),
                merged.base_amount,
                merged.revision_amount,
                merged.dual_sport_fee,
                merged.ranking_services,
                merged.c_team_scheduling,
                merged.fh_ranking_services,
                merged.address_note,
                merged.collection_status,
                merged.notes,
                invoice_id,
            ),
        )
    return get_invoice(invoice_id)


def delete_invoice(invoice_id: int) -> bool:
    with db_session() as conn:
        cursor = conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
        return cursor.rowcount > 0


def _payment_from_row(row: sqlite3.Row) -> Payment:
    data = row_to_dict(row)
    assert data is not None
    return Payment(
        id=data["id"],
        invoice_id=data["invoice_id"],
        amount_paid=data["amount_paid"],
        date_paid=data["date_paid"],
        payment_method=data["payment_method"],
        notes=data["notes"],
        school_name=data.get("school_name"),
        season_year=data.get("season_year"),
        sport=data.get("sport"),
    )


def list_payments() -> list[Payment]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT p.*, s.school_name, i.season_year, i.sport
            FROM payments p
            JOIN invoices i ON i.id = p.invoice_id
            JOIN schools s ON s.id = i.school_id
            ORDER BY p.date_paid IS NULL, p.date_paid DESC, p.id DESC
            """
        ).fetchall()
        return [_payment_from_row(row) for row in rows]


def get_payment(payment_id: int) -> Payment | None:
    with db_session() as conn:
        row = conn.execute(
            """
            SELECT p.*, s.school_name, i.season_year, i.sport
            FROM payments p
            JOIN invoices i ON i.id = p.invoice_id
            JOIN schools s ON s.id = i.school_id
            WHERE p.id = ?
            """,
            (payment_id,),
        ).fetchone()
        if row is None:
            return None
        return _payment_from_row(row)


def create_payment(payload: PaymentCreate) -> Payment:
    with db_session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO payments (invoice_id, amount_paid, date_paid, payment_method, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload.invoice_id,
                payload.amount_paid,
                payload.date_paid,
                payload.payment_method,
                payload.notes,
            ),
        )
        payment_id = cursor.lastrowid
        assert payment_id is not None
    payment = get_payment(payment_id)
    assert payment is not None
    return payment


def update_payment(payment_id: int, payload: PaymentUpdate) -> Payment | None:
    existing = get_payment(payment_id)
    if existing is None:
        return None

    merged = existing.model_copy(update=payload.model_dump(exclude_unset=True))

    with db_session() as conn:
        conn.execute(
            """
            UPDATE payments SET
                invoice_id = ?, amount_paid = ?, date_paid = ?,
                payment_method = ?, notes = ?
            WHERE id = ?
            """,
            (
                merged.invoice_id,
                merged.amount_paid,
                merged.date_paid,
                merged.payment_method,
                merged.notes,
                payment_id,
            ),
        )
    return get_payment(payment_id)


def delete_payment(payment_id: int) -> bool:
    with db_session() as conn:
        cursor = conn.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
        return cursor.rowcount > 0


def _game_from_row(row: sqlite3.Row) -> Game:
    data = row_to_dict(row)
    assert data is not None
    return Game(
        id=data["id"],
        game_date=data["game_date"],
        game_time=data["game_time"],
        level=data["level"],
        home_school_id=data["home_school_id"],
        away_school_id=data["away_school_id"],
        field_location=data["field_location"],
        season_year=data["season_year"],
        sport=data["sport"],
        home_school_name=data.get("home_school_name"),
        away_school_name=data.get("away_school_name"),
    )


def list_games() -> list[Game]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT g.*,
                   hs.school_name AS home_school_name,
                   aws.school_name AS away_school_name
            FROM games g
            LEFT JOIN schools hs ON hs.id = g.home_school_id
            LEFT JOIN schools aws ON aws.id = g.away_school_id
            ORDER BY g.game_date, g.game_time, g.id
            """
        ).fetchall()
        return [_game_from_row(row) for row in rows]


def get_game(game_id: int) -> Game | None:
    with db_session() as conn:
        row = conn.execute(
            """
            SELECT g.*,
                   hs.school_name AS home_school_name,
                   aws.school_name AS away_school_name
            FROM games g
            LEFT JOIN schools hs ON hs.id = g.home_school_id
            LEFT JOIN schools aws ON aws.id = g.away_school_id
            WHERE g.id = ?
            """,
            (game_id,),
        ).fetchone()
        if row is None:
            return None
        return _game_from_row(row)


def create_game(payload: GameCreate) -> Game:
    with db_session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO games (
                game_date, game_time, level, home_school_id, away_school_id,
                field_location, season_year, sport
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.game_date,
                payload.game_time,
                payload.level,
                payload.home_school_id,
                payload.away_school_id,
                payload.field_location,
                payload.season_year,
                payload.sport.strip(),
            ),
        )
        game_id = cursor.lastrowid
        assert game_id is not None
    game = get_game(game_id)
    assert game is not None
    return game


def update_game(game_id: int, payload: GameUpdate) -> Game | None:
    existing = get_game(game_id)
    if existing is None:
        return None

    merged = existing.model_copy(update=payload.model_dump(exclude_unset=True))

    with db_session() as conn:
        conn.execute(
            """
            UPDATE games SET
                game_date = ?, game_time = ?, level = ?,
                home_school_id = ?, away_school_id = ?,
                field_location = ?, season_year = ?, sport = ?
            WHERE id = ?
            """,
            (
                merged.game_date,
                merged.game_time,
                merged.level,
                merged.home_school_id,
                merged.away_school_id,
                merged.field_location,
                merged.season_year,
                merged.sport.strip(),
                game_id,
            ),
        )
    return get_game(game_id)


def delete_game(game_id: int) -> bool:
    with db_session() as conn:
        cursor = conn.execute("DELETE FROM games WHERE id = ?", (game_id,))
        return cursor.rowcount > 0


def export_all() -> dict[str, Any]:
    return {
        "version": 1,
        "schools": [school.model_dump() for school in list_schools()],
        "invoices": [
            invoice.model_dump()
            for invoice in list_invoices()
        ],
        "payments": [payment.model_dump() for payment in list_payments()],
        "games": [game.model_dump() for game in list_games()],
    }


def import_all(data: dict[str, Any], *, replace: bool = True) -> dict[str, int]:
    with db_session() as conn:
        if replace:
            conn.execute("DELETE FROM payments")
            conn.execute("DELETE FROM invoices")
            conn.execute("DELETE FROM games")
            conn.execute("DELETE FROM school_sports")
            conn.execute("DELETE FROM schools")

        school_id_map: dict[int, int] = {}
        for school_data in data.get("schools", []):
            sports = school_data.pop("sports", [])
            old_id = school_data.pop("id", None)
            cursor = conn.execute(
                """
                INSERT INTO schools (
                    school_name, address, city, state, zip, field_location, subsite,
                    varsity_game_time, jv_game_time, rank, parkway_district
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    school_data["school_name"],
                    school_data.get("address"),
                    school_data.get("city"),
                    school_data.get("state"),
                    school_data.get("zip"),
                    school_data.get("field_location"),
                    school_data.get("subsite"),
                    school_data.get("varsity_game_time"),
                    school_data.get("jv_game_time"),
                    school_data.get("rank"),
                    1 if school_data.get("parkway_district") else 0,
                ),
            )
            new_id = cursor.lastrowid
            assert new_id is not None
            if old_id is not None:
                school_id_map[old_id] = new_id
            _set_school_sports(conn, new_id, sports)

        invoice_id_map: dict[int, int] = {}
        for invoice_data in data.get("invoices", []):
            old_id = invoice_data.pop("id", None)
            invoice_data.pop("school_name", None)
            invoice_data.pop("total_amount", None)
            invoice_data.pop("amount_paid", None)
            invoice_data.pop("balance_due", None)
            created_at = invoice_data.pop("created_at", None)
            old_school_id = invoice_data["school_id"]
            invoice_data["school_id"] = school_id_map.get(old_school_id, old_school_id)

            cursor = conn.execute(
                """
                INSERT INTO invoices (
                    school_id, season_year, sport, base_amount, revision_amount,
                    dual_sport_fee, ranking_services, c_team_scheduling,
                    fh_ranking_services, address_note, collection_status, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, datetime('now')))
                """,
                (
                    invoice_data["school_id"],
                    invoice_data["season_year"],
                    invoice_data["sport"],
                    invoice_data.get("base_amount", 110.0),
                    invoice_data.get("revision_amount", 0.0),
                    invoice_data.get("dual_sport_fee", 0.0),
                    invoice_data.get("ranking_services", 0.0),
                    invoice_data.get("c_team_scheduling", 0.0),
                    invoice_data.get("fh_ranking_services", 0.0),
                    invoice_data.get("address_note"),
                    invoice_data.get("collection_status"),
                    invoice_data.get("notes"),
                    created_at,
                ),
            )
            new_id = cursor.lastrowid
            assert new_id is not None
            if old_id is not None:
                invoice_id_map[old_id] = new_id

        payment_count = 0
        for payment_data in data.get("payments", []):
            payment_data.pop("id", None)
            payment_data.pop("school_name", None)
            payment_data.pop("season_year", None)
            payment_data.pop("sport", None)
            old_invoice_id = payment_data["invoice_id"]
            payment_data["invoice_id"] = invoice_id_map.get(old_invoice_id, old_invoice_id)
            conn.execute(
                """
                INSERT INTO payments (invoice_id, amount_paid, date_paid, payment_method, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    payment_data["invoice_id"],
                    payment_data.get("amount_paid"),
                    payment_data.get("date_paid"),
                    payment_data.get("payment_method"),
                    payment_data.get("notes"),
                ),
            )
            payment_count += 1

        game_count = 0
        for game_data in data.get("games", []):
            game_data.pop("id", None)
            game_data.pop("home_school_name", None)
            game_data.pop("away_school_name", None)
            if game_data.get("home_school_id") is not None:
                game_data["home_school_id"] = school_id_map.get(
                    game_data["home_school_id"],
                    game_data["home_school_id"],
                )
            if game_data.get("away_school_id") is not None:
                game_data["away_school_id"] = school_id_map.get(
                    game_data["away_school_id"],
                    game_data["away_school_id"],
                )
            conn.execute(
                """
                INSERT INTO games (
                    game_date, game_time, level, home_school_id, away_school_id,
                    field_location, season_year, sport
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    game_data["game_date"],
                    game_data.get("game_time"),
                    game_data.get("level"),
                    game_data.get("home_school_id"),
                    game_data.get("away_school_id"),
                    game_data.get("field_location"),
                    game_data.get("season_year"),
                    game_data.get("sport", "Lacrosse"),
                ),
            )
            game_count += 1

    return {
        "schools": len(data.get("schools", [])),
        "invoices": len(data.get("invoices", [])),
        "payments": payment_count,
        "games": game_count,
    }
