from __future__ import annotations

import csv
import io
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.connection import app_dir
from app.invoice.db import db_session
from app.invoice.models import GameCreate, InvoiceCreate, PaymentCreate, SchoolCreate
from app.invoice.service import (
    create_game,
    create_invoice,
    create_payment,
    create_school,
    list_schools,
)

ACCESS_DATE_FORMATS = (
    "%m/%d/%y %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%y",
    "%m/%d/%Y",
    "%Y-%m-%d",
)


@dataclass
class ImportSummary:
    schools: int = 0
    invoices: int = 0
    payments: int = 0
    games: int = 0
    pdf_invoices: int = 0
    warnings: list[str] | None = None


def default_accdb_path() -> Path:
    return app_dir() / "Invoice Database.accdb"


def default_pdf_path() -> Path:
    return app_dir() / "Invoice  - Wentzville Lacrosse Club.pdf"


def find_mdb_export() -> str:
    path = shutil.which("mdb-export")
    if path:
        return path
    brew_path = Path("/opt/homebrew/bin/mdb-export")
    if brew_path.exists():
        return str(brew_path)
    raise FileNotFoundError(
        "mdb-export not found. Install mdbtools (brew install mdbtools on macOS)."
    )


def export_table(accdb_path: Path, table_name: str) -> list[dict[str, str]]:
    command = [find_mdb_export(), str(accdb_path), table_name]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    reader = csv.DictReader(io.StringIO(result.stdout))
    return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def parse_currency(value: str | None) -> float:
    if not value:
        return 0.0
    cleaned = value.replace("$", "").replace(",", "").strip()
    if not cleaned:
        return 0.0
    return round(float(cleaned), 2)


def parse_access_time(value: str | None) -> str | None:
    if not value:
        return None
    for fmt in ACCESS_DATE_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%H:%M")
        except ValueError:
            continue
    return None


def parse_access_date(value: str | None) -> str | None:
    if not value:
        return None
    for fmt in ACCESS_DATE_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def normalize_school_name(name: str) -> str:
    cleaned = name.strip().lower()
    cleaned = cleaned.replace("'", "").replace("'", "").replace("'", "")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


SCHOOL_NAME_ALIASES: dict[str, str] = {
    "clayton high school": "school district of clayton",
    "john burroughs high school": "john burroughs school",
    "st. dominic's high school": "st. dominic high school",
    "st dominic's high school": "st. dominic high school",
    "st dominics high school": "st. dominic high school",
    "st. dominics high school": "st. dominic high school",
    "wentzville holt high school": "wentzville lacrosse club",
    "micds": "mary institute country day school",
    "belleville": "belleville west high school",
    "francis howell high school central": "francis howell central high school",
    "parkway central": "parkway central high school",
}


def canonical_school_name(name: str) -> str:
    normalized = normalize_school_name(name)
    return SCHOOL_NAME_ALIASES.get(normalized, normalized)


def build_school_lookup() -> dict[str, int]:
    lookup: dict[str, int] = {}
    for school in list_schools():
        normalized = normalize_school_name(school.school_name)
        lookup[normalized] = school.id
        lookup[canonical_school_name(school.school_name)] = school.id
    return lookup


def resolve_school_id(name: str, lookup: dict[str, int], warnings: list[str]) -> int | None:
    if not name or name.strip().upper() == "TBD":
        return None

    normalized = canonical_school_name(name)
    if normalized in lookup:
        return lookup[normalized]

    for candidate, school_id in lookup.items():
        if candidate.startswith(normalized) or normalized.startswith(candidate):
            if normalize_school_name(name) != candidate:
                warning = f"Matched school '{name}' to existing '{candidate}'"
                if warning not in warnings:
                    warnings.append(warning)
            return school_id

    warning = f"Could not match school name: {name}"
    if warning not in warnings:
        warnings.append(warning)
    return None


def sports_from_school_row(row: dict[str, str]) -> list[str]:
    sports: list[str] = []
    if row.get("Sport 1"):
        sports.append(row["Sport 1"].strip())
    if row.get("Field Hockey"):
        sport = row["Field Hockey"].strip()
        if sport and sport not in sports:
            sports.append(sport)
    return sports


def merge_school_rows(
    schools_rows: list[dict[str, str]],
    venue_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    venue_by_name = {
        canonical_school_name(row["SchoolName"]): row for row in venue_rows
    }
    merged: list[dict[str, Any]] = []

    for row in schools_rows:
        venue = venue_by_name.get(canonical_school_name(row["SchoolName"]), {})
        rank_value = row.get("Field1") or venue.get("Rank")
        rank = int(rank_value) if rank_value else None
        merged.append(
            {
                "school_name": row["SchoolName"].strip(),
                "address": row.get("SchoolAddress") or venue.get("SchoolAddress") or None,
                "city": row.get("SchoolCity") or venue.get("SchoolCity") or None,
                "state": row.get("SchoolStateAbbreviation") or venue.get("SchoolStateAbbreviation") or None,
                "zip": row.get("SchoolZip") or venue.get("SchoolZip") or None,
                "field_location": venue.get("Field Location") or None,
                "subsite": venue.get("Subsite") or None,
                "varsity_game_time": parse_access_time(venue.get("Varsity Game Time")),
                "jv_game_time": parse_access_time(venue.get("JV Game Time")),
                "rank": rank,
                "parkway_district": row.get("Parkway", "").upper() == "Y",
                "sports": sports_from_school_row(row),
                "fees": {
                    "base_amount": parse_currency(row.get("InvoiceAmt")) or 110.0,
                    "revision_amount": parse_currency(row.get("Revision")),
                    "dual_sport_fee": parse_currency(row.get("Field2")),
                    "ranking_services": parse_currency(row.get("Ranking Services")),
                    "c_team_scheduling": parse_currency(row.get("C Team Scheduling")),
                    "fh_ranking_services": parse_currency(row.get("FH Ranking Services")),
                    "address_note": None,
                    "collection_status": row.get("NOTE:") or None,
                    "paid_lx2017": row.get("Paid LX2017") or None,
                    "fh2018": row.get("FH2018") or None,
                    "due_lx2019": row.get("Due LX2019") or None,
                },
            }
        )
    return merged


def import_schools_from_access(accdb_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    schools_rows = export_table(accdb_path, "Schools")
    venue_rows = export_table(accdb_path, "tblSchool")
    merged = merge_school_rows(schools_rows, venue_rows)
    warnings: list[str] = []

    for school_data in merged:
        create_school(
            SchoolCreate(
                school_name=school_data["school_name"],
                address=school_data["address"],
                city=school_data["city"],
                state=school_data["state"],
                zip=school_data["zip"],
                field_location=school_data["field_location"],
                subsite=school_data["subsite"],
                varsity_game_time=school_data["varsity_game_time"],
                jv_game_time=school_data["jv_game_time"],
                rank=school_data["rank"],
                parkway_district=school_data["parkway_district"],
                sports=school_data["sports"],
            )
        )

    return merged, warnings


def import_invoices_from_access(
    merged_schools: list[dict[str, Any]],
    accdb_path: Path,
    warnings: list[str],
) -> tuple[int, int]:
    lookup = build_school_lookup()
    invoice_count = 0
    payment_count = 0

    for school_data in merged_schools:
        school_id = lookup.get(canonical_school_name(school_data["school_name"]))
        if school_id is None:
            continue

        fees = school_data["fees"]
        sports = school_data["sports"]

        if "Lacrosse" in sports:
            season_year = 2019 if fees["due_lx2019"] else 2017 if fees["paid_lx2017"] else 2019
            invoice = create_invoice(
                InvoiceCreate(
                    school_id=school_id,
                    season_year=season_year,
                    sport="Lacrosse",
                    base_amount=fees["base_amount"],
                    revision_amount=fees["revision_amount"],
                    dual_sport_fee=fees["dual_sport_fee"] if len(sports) > 1 else 0.0,
                    ranking_services=fees["ranking_services"],
                    c_team_scheduling=fees["c_team_scheduling"],
                    fh_ranking_services=0.0,
                    address_note=fees["address_note"],
                    collection_status=fees["collection_status"],
                )
            )
            invoice_count += 1
            if fees["due_lx2019"] and fees["due_lx2019"].lower() == "paid":
                create_payment(
                    PaymentCreate(
                        invoice_id=invoice.id,
                        amount_paid=invoice.total_amount,
                        date_paid=f"{season_year}-08-24",
                        payment_method="Check",
                        notes="Imported from Access Due LX2019 status",
                    )
                )
                payment_count += 1

        if "Field Hockey" in sports:
            if fees["fh2018"]:
                invoice = create_invoice(
                    InvoiceCreate(
                        school_id=school_id,
                        season_year=2018,
                        sport="Field Hockey",
                        base_amount=fees["base_amount"],
                        revision_amount=fees["revision_amount"],
                        dual_sport_fee=fees["dual_sport_fee"] if len(sports) > 1 else 0.0,
                        ranking_services=0.0,
                        c_team_scheduling=0.0,
                        fh_ranking_services=fees["fh_ranking_services"] or 15.0,
                        address_note=fees["address_note"],
                        collection_status=fees["collection_status"],
                    )
                )
                invoice_count += 1
                if fees["fh2018"].upper() == "Y":
                    create_payment(
                        PaymentCreate(
                            invoice_id=invoice.id,
                            amount_paid=invoice.total_amount,
                            date_paid="2018-08-24",
                            payment_method="Check",
                            notes="Imported from Access FH2018 status",
                        )
                    )
                    payment_count += 1

    fh_rows = export_table(accdb_path, "Field Hockey Account Payable")
    for row in fh_rows:
        school_id = resolve_school_id(row["SchoolName"], lookup, warnings)
        if school_id is None:
            continue

        invoice = create_invoice(
            InvoiceCreate(
                school_id=school_id,
                season_year=2022,
                sport="Field Hockey",
                base_amount=parse_currency(row.get("InvoiceAmt")) or 110.0,
                fh_ranking_services=15.0,
            )
        )
        invoice_count += 1

        paid_date = parse_access_date(row.get("Date Paid"))
        if paid_date:
            create_payment(
                PaymentCreate(
                    invoice_id=invoice.id,
                    amount_paid=invoice.total_amount,
                    date_paid=paid_date,
                    payment_method="Check",
                    notes="Imported from Field Hockey Account Payable",
                )
            )
            payment_count += 1

    return invoice_count, payment_count


def import_games_from_access(accdb_path: Path, warnings: list[str]) -> int:
    lookup = build_school_lookup()
    rows = export_table(accdb_path, "Schedule 2016")
    count = 0

    for row in rows:
        home_id = resolve_school_id(row["Home-Team16"], lookup, warnings)
        away_id = resolve_school_id(row["Away-Team16"], lookup, warnings)
        game_date = parse_access_date(row.get("Date2016"))
        if not game_date:
            warnings.append(f"Skipping game with invalid date: {row}")
            continue

        create_game(
            GameCreate(
                game_date=game_date,
                game_time=parse_access_time(row.get("Game Time")),
                level=row.get("Level") or None,
                home_school_id=home_id,
                away_school_id=away_id,
                field_location=row.get("Field Location") or None,
                season_year=2016,
                sport="Lacrosse",
            )
        )
        count += 1

    return count


def parse_pdf_invoice(pdf_path: Path) -> dict[str, Any] | None:
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError("pdfplumber is required for PDF import. Run: uv pip install pdfplumber") from exc

    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    if not text.strip():
        return None

    school_match = re.search(r"TO:\s*(.+?)\s+Invoice Number", text, re.IGNORECASE)
    invoice_number_match = re.search(r"Invoice Number\s+(\S+)", text, re.IGNORECASE)
    invoice_date_match = re.search(r"Invoice Date:\s*(\d{1,2}/\d{1,2}/\d{4})", text, re.IGNORECASE)
    season_match = re.search(r"Spring\s+(\d{4})", text, re.IGNORECASE)
    base_match = re.search(
        r"Schedule Preparation for Lacrosse - Spring\s+\d{4}\s+\$?([\d,]+\.\d{2})",
        text,
        re.IGNORECASE,
    )
    c_team_match = re.search(r"C Team Scheduling\s+\$?([\d,]+\.\d{2})", text, re.IGNORECASE)
    ranking_match = re.search(r"Ranking Services\s+\$?([\d,]+\.\d{2})", text, re.IGNORECASE)
    note_match = re.search(r"NOTE:\s*(.+?)(?:Please make check payable|$)", text, re.IGNORECASE | re.DOTALL)

    if not school_match:
        return None

    note = note_match.group(1).strip() if note_match else None
    if note:
        note = re.sub(r"\s+", " ", note)

    return {
        "school_name": school_match.group(1).strip(),
        "invoice_number": invoice_number_match.group(1).strip() if invoice_number_match else None,
        "invoice_date": invoice_date_match.group(1).strip() if invoice_date_match else None,
        "season_year": int(season_match.group(1)) if season_match else None,
        "sport": "Lacrosse",
        "base_amount": parse_currency(base_match.group(1)) if base_match else 110.0,
        "c_team_scheduling": parse_currency(c_team_match.group(1)) if c_team_match else 0.0,
        "ranking_services": parse_currency(ranking_match.group(1)) if ranking_match else 0.0,
        "collection_status": note,
    }


def import_invoice_from_pdf(pdf_path: Path, warnings: list[str]) -> int:
    parsed = parse_pdf_invoice(pdf_path)
    if parsed is None:
        warnings.append(f"Could not parse invoice data from PDF: {pdf_path}")
        return 0

    lookup = build_school_lookup()
    school_id = resolve_school_id(parsed["school_name"], lookup, warnings)
    if school_id is None:
        return 0

    season_year = parsed["season_year"] or datetime.now().year
    notes_parts = []
    if parsed.get("invoice_number"):
        notes_parts.append(f"Invoice Number {parsed['invoice_number']}")
    if parsed.get("invoice_date"):
        notes_parts.append(f"Invoice Date {parsed['invoice_date']}")

    create_invoice(
        InvoiceCreate(
            school_id=school_id,
            season_year=season_year,
            sport=parsed["sport"],
            base_amount=parsed["base_amount"],
            c_team_scheduling=parsed["c_team_scheduling"],
            ranking_services=parsed["ranking_services"],
            collection_status=parsed["collection_status"],
            notes=" | ".join(notes_parts) if notes_parts else None,
        )
    )
    return 1


def clear_database() -> None:
    with db_session() as conn:
        conn.execute("DELETE FROM payments")
        conn.execute("DELETE FROM invoices")
        conn.execute("DELETE FROM games")
        conn.execute("DELETE FROM school_sports")
        conn.execute("DELETE FROM schools")


def import_default_sources(
    *,
    accdb_path: Path | None = None,
    pdf_path: Path | None = None,
    replace: bool = True,
) -> ImportSummary:
    accdb = accdb_path or default_accdb_path()
    pdf = pdf_path or default_pdf_path()
    warnings: list[str] = []

    if not accdb.exists():
        raise FileNotFoundError(f"Access database not found: {accdb}")

    if replace:
        clear_database()

    merged_schools, school_warnings = import_schools_from_access(accdb)
    warnings.extend(school_warnings)

    invoice_count, payment_count = import_invoices_from_access(merged_schools, accdb, warnings)
    game_count = import_games_from_access(accdb, warnings)

    pdf_count = 0
    if pdf.exists():
        pdf_count = import_invoice_from_pdf(pdf, warnings)
    else:
        warnings.append(f"PDF not found, skipped: {pdf}")

    return ImportSummary(
        schools=len(merged_schools),
        invoices=invoice_count + pdf_count,
        payments=payment_count,
        games=game_count,
        pdf_invoices=pdf_count,
        warnings=warnings,
    )
