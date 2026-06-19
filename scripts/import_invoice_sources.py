from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.connection import app_dir
from app.invoice.access_import import (
    default_accdb_path,
    default_pdf_path,
    import_default_sources,
)
from app.invoice.db import init_db


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import schools, invoices, payments, and schedules from Access + PDF sources.",
    )
    parser.add_argument(
        "--accdb",
        type=Path,
        default=default_accdb_path(),
        help="Path to Invoice Database.accdb",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=default_pdf_path(),
        help="Path to sample invoice PDF",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not clear the database before import",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print import summary as JSON",
    )
    args = parser.parse_args()

    if not args.accdb.is_absolute():
        args.accdb = app_dir() / args.accdb
    if not args.pdf.is_absolute():
        args.pdf = app_dir() / args.pdf

    init_db()
    summary = import_default_sources(
        accdb_path=args.accdb,
        pdf_path=args.pdf,
        replace=not args.keep_existing,
    )

    payload = {
        "schools": summary.schools,
        "invoices": summary.invoices,
        "payments": summary.payments,
        "games": summary.games,
        "pdf_invoices": summary.pdf_invoices,
        "warnings": summary.warnings or [],
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Imported {summary.schools} schools")
        print(f"Imported {summary.invoices} invoices ({summary.pdf_invoices} from PDF)")
        print(f"Imported {summary.payments} payments")
        print(f"Imported {summary.games} games")
        if summary.warnings:
            print("\nWarnings:")
            for warning in summary.warnings:
                print(f"  - {warning}")

    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    raise SystemExit(main())
