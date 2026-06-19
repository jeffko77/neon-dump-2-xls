from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.connection import app_dir
from app.invoice.backup import export_json_backup
from app.invoice.db import init_db
from app.invoice.seed_data import SEED_FILENAME


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export the current invoice database as the bundled seed file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=app_dir() / "data" / SEED_FILENAME,
        help="Path to write the seed JSON file",
    )
    args = parser.parse_args()

    if not args.output.is_absolute():
        args.output = app_dir() / args.output

    init_db()
    payload = export_json_backup()
    payload["description"] = (
        "Original invoice dataset bundled with the app. "
        "Imported from Invoice Database.accdb for offline reset."
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Wrote {args.output}")
    print(f"  schools:  {len(payload['schools'])}")
    print(f"  invoices: {len(payload['invoices'])}")
    print(f"  payments: {len(payload['payments'])}")
    print(f"  games:    {len(payload['games'])}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    raise SystemExit(main())
