from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.invoice.seed_data import import_bundled_seed
from app.invoice.backup import export_excel_backup, export_json_backup, write_excel_backup, write_json_backup
from app.invoice.db import database_path, init_db
from app.invoice.fee_schedule import FEE_DEFAULTS_BY_SPORT, STANDARD_FEE_SCHEDULE
from app.invoice.invoice_pdf import invoice_pdf_filename, render_invoice_pdf
from app.invoice.models import (
    GameCreate,
    GameUpdate,
    InvoiceCreate,
    InvoiceUpdate,
    PaymentCreate,
    PaymentUpdate,
    SchoolCreate,
    SchoolUpdate,
)
from app.invoice.seed import seed_if_empty
from app.invoice.service import (
    create_game,
    create_invoice,
    create_payment,
    create_school,
    delete_game,
    delete_invoice,
    delete_payment,
    delete_school,
    get_game,
    get_invoice,
    get_payment,
    get_school,
    import_all,
    list_games,
    list_invoices,
    list_payments,
    list_schools,
    update_game,
    update_invoice,
    update_payment,
    update_school,
)
from app.connection import app_dir, is_frozen


def default_backups_dir() -> Path:
    if is_frozen() and sys.platform == "win32":
        return Path.home() / "Documents" / "InvoiceDatabase" / "backups"
    return app_dir() / "data" / "backups"


BACKUPS_DIR = default_backups_dir()


def init_invoice_db() -> None:
    init_db()
    seed_if_empty()


def register_invoice_routes(app: FastAPI) -> None:
    router = APIRouter()

    @router.get("/api/fee-schedule")
    def fee_schedule() -> dict[str, Any]:
        return {
            "fees": STANDARD_FEE_SCHEDULE,
            "defaults_by_sport": FEE_DEFAULTS_BY_SPORT,
        }

    @router.get("/api/invoice-db/status")
    def invoice_status() -> dict[str, Any]:
        schools = list_schools()
        invoices = list_invoices()
        payments = list_payments()
        games = list_games()
        return {
            "database_path": str(database_path()),
            "backups_dir": str(BACKUPS_DIR),
            "counts": {
                "schools": len(schools),
                "invoices": len(invoices),
                "payments": len(payments),
                "games": len(games),
            },
            "app_dir": str(app_dir()),
            "frozen": is_frozen(),
        }

    @router.get("/api/schools")
    def api_list_schools() -> list[dict[str, Any]]:
        return [school.model_dump() for school in list_schools()]

    @router.post("/api/schools")
    def api_create_school(payload: SchoolCreate) -> dict[str, Any]:
        try:
            school = create_school(payload)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return school.model_dump()

    @router.get("/api/schools/{school_id}")
    def api_get_school(school_id: int) -> dict[str, Any]:
        school = get_school(school_id)
        if school is None:
            raise HTTPException(status_code=404, detail="School not found")
        return school.model_dump()

    @router.put("/api/schools/{school_id}")
    def api_update_school(school_id: int, payload: SchoolUpdate) -> dict[str, Any]:
        try:
            school = update_school(school_id, payload)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if school is None:
            raise HTTPException(status_code=404, detail="School not found")
        return school.model_dump()

    @router.delete("/api/schools/{school_id}")
    def api_delete_school(school_id: int) -> dict[str, str]:
        if not delete_school(school_id):
            raise HTTPException(status_code=404, detail="School not found")
        return {"status": "deleted"}

    @router.get("/api/invoices")
    def api_list_invoices() -> list[dict[str, Any]]:
        return [invoice.model_dump() for invoice in list_invoices()]

    @router.post("/api/invoices")
    def api_create_invoice(payload: InvoiceCreate) -> dict[str, Any]:
        if get_school(payload.school_id) is None:
            raise HTTPException(status_code=400, detail="School not found")
        invoice = create_invoice(payload)
        return invoice.model_dump()

    @router.get("/api/invoices/{invoice_id}")
    def api_get_invoice(invoice_id: int) -> dict[str, Any]:
        invoice = get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return invoice.model_dump()

    @router.put("/api/invoices/{invoice_id}")
    def api_update_invoice(invoice_id: int, payload: InvoiceUpdate) -> dict[str, Any]:
        if payload.school_id is not None and get_school(payload.school_id) is None:
            raise HTTPException(status_code=400, detail="School not found")
        invoice = update_invoice(invoice_id, payload)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return invoice.model_dump()

    @router.get("/api/invoices/{invoice_id}/pdf")
    def api_export_invoice_pdf(invoice_id: int) -> Response:
        invoice = get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found")
        try:
            pdf_bytes = render_invoice_pdf(invoice)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        filename = invoice_pdf_filename(invoice)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.delete("/api/invoices/{invoice_id}")
    def api_delete_invoice(invoice_id: int) -> dict[str, str]:
        if not delete_invoice(invoice_id):
            raise HTTPException(status_code=404, detail="Invoice not found")
        return {"status": "deleted"}

    @router.get("/api/payments")
    def api_list_payments() -> list[dict[str, Any]]:
        return [payment.model_dump() for payment in list_payments()]

    @router.post("/api/payments")
    def api_create_payment(payload: PaymentCreate) -> dict[str, Any]:
        if get_invoice(payload.invoice_id) is None:
            raise HTTPException(status_code=400, detail="Invoice not found")
        payment = create_payment(payload)
        return payment.model_dump()

    @router.get("/api/payments/{payment_id}")
    def api_get_payment(payment_id: int) -> dict[str, Any]:
        payment = get_payment(payment_id)
        if payment is None:
            raise HTTPException(status_code=404, detail="Payment not found")
        return payment.model_dump()

    @router.put("/api/payments/{payment_id}")
    def api_update_payment(payment_id: int, payload: PaymentUpdate) -> dict[str, Any]:
        if payload.invoice_id is not None and get_invoice(payload.invoice_id) is None:
            raise HTTPException(status_code=400, detail="Invoice not found")
        payment = update_payment(payment_id, payload)
        if payment is None:
            raise HTTPException(status_code=404, detail="Payment not found")
        return payment.model_dump()

    @router.delete("/api/payments/{payment_id}")
    def api_delete_payment(payment_id: int) -> dict[str, str]:
        if not delete_payment(payment_id):
            raise HTTPException(status_code=404, detail="Payment not found")
        return {"status": "deleted"}

    @router.get("/api/games")
    def api_list_games() -> list[dict[str, Any]]:
        return [game.model_dump() for game in list_games()]

    @router.post("/api/games")
    def api_create_game(payload: GameCreate) -> dict[str, Any]:
        game = create_game(payload)
        return game.model_dump()

    @router.get("/api/games/{game_id}")
    def api_get_game(game_id: int) -> dict[str, Any]:
        game = get_game(game_id)
        if game is None:
            raise HTTPException(status_code=404, detail="Game not found")
        return game.model_dump()

    @router.put("/api/games/{game_id}")
    def api_update_game(game_id: int, payload: GameUpdate) -> dict[str, Any]:
        game = update_game(game_id, payload)
        if game is None:
            raise HTTPException(status_code=404, detail="Game not found")
        return game.model_dump()

    @router.delete("/api/games/{game_id}")
    def api_delete_game(game_id: int) -> dict[str, str]:
        if not delete_game(game_id):
            raise HTTPException(status_code=404, detail="Game not found")
        return {"status": "deleted"}

    @router.get("/api/backup/json")
    def api_download_json_backup() -> Response:
        payload = export_json_backup()
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"invoice_backup_{timestamp}.json"
        return Response(
            content=json.dumps(payload, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/api/backup/excel")
    def api_download_excel_backup() -> Response:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"invoice_backup_{timestamp}.xlsx"
        return Response(
            content=export_excel_backup(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.post("/api/backup/save")
    def api_save_local_backup() -> dict[str, str]:
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        json_path = write_json_backup(BACKUPS_DIR / f"invoice_backup_{timestamp}.json")
        excel_path = write_excel_backup(BACKUPS_DIR / f"invoice_backup_{timestamp}.xlsx")
        return {
            "json_path": str(json_path),
            "excel_path": str(excel_path),
        }

    @router.post("/api/backup/import")
    async def api_import_backup(file: UploadFile, replace: bool = True) -> dict[str, Any]:
        try:
            raw = await file.read()
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON backup: {exc}") from exc

        if "schools" not in data:
            raise HTTPException(status_code=400, detail="Backup file missing 'schools' array")

        counts = import_all(data, replace=replace)
        return {"status": "imported", "counts": counts}

    @router.post("/api/import/seed")
    def api_import_seed() -> dict[str, Any]:
        try:
            counts = import_bundled_seed(replace=True)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return {"status": "imported", "counts": counts, "source": "bundled_seed"}

    @router.post("/api/import/access")
    def api_import_access() -> dict[str, Any]:
        from app.invoice.access_import import default_accdb_path, default_pdf_path, import_default_sources

        accdb_path = default_accdb_path()
        if not accdb_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Access database not found: {accdb_path}",
            )
        try:
            summary = import_default_sources(
                accdb_path=accdb_path,
                pdf_path=default_pdf_path(),
                replace=True,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return {
            "status": "imported",
            "counts": {
                "schools": summary.schools,
                "invoices": summary.invoices,
                "payments": summary.payments,
                "games": summary.games,
                "pdf_invoices": summary.pdf_invoices,
            },
            "warnings": summary.warnings or [],
        }

    app.include_router(router)
