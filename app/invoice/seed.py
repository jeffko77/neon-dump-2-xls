from __future__ import annotations

from app.invoice.access_import import default_accdb_path, import_default_sources
from app.invoice.db import db_session


def seed_if_empty() -> bool:
    with db_session() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM schools").fetchone()["c"]
        if count:
            return False

    accdb_path = default_accdb_path()
    if accdb_path.exists():
        import_default_sources(accdb_path=accdb_path, replace=True)
        return True

    from app.invoice.models import GameCreate, InvoiceCreate, PaymentCreate, SchoolCreate
    from app.invoice.service import create_game, create_invoice, create_payment, create_school

    SAMPLE_SCHOOLS = [
        {
            "school_name": "Kirkwood High School",
            "address": "801 W Essex Ave",
            "city": "Kirkwood",
            "state": "MO",
            "zip": "63122",
            "field_location": "Kirkwood High School",
            "subsite": "Field Hockey Field",
            "varsity_game_time": "16:00",
            "jv_game_time": "17:30",
            "rank": 1,
            "parkway_district": False,
            "sports": ["Lacrosse", "Field Hockey"],
        },
    ]

    schools = [create_school(SchoolCreate(**data)) for data in SAMPLE_SCHOOLS]
    school = schools[0]
    invoice = create_invoice(
        InvoiceCreate(
            school_id=school.id,
            season_year=2022,
            sport="Field Hockey",
            base_amount=110.0,
            fh_ranking_services=15.0,
        )
    )
    create_payment(
        PaymentCreate(
            invoice_id=invoice.id,
            amount_paid=125.0,
            date_paid="2022-08-24",
        )
    )
    create_game(
        GameCreate(
            game_date="2016-03-15",
            game_time="16:00",
            level="Varsity",
            home_school_id=school.id,
            away_school_id=school.id,
            field_location="Kirkwood High School",
            season_year=2016,
            sport="Lacrosse",
        )
    )
    return True
