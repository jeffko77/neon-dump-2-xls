from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import webbrowser
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.connection import app_dir, is_frozen
from app.invoice.access_import import default_accdb_path, default_pdf_path, import_default_sources
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
from app.reveal import reveal_path, validate_reveal_path


def static_dir() -> Path:
    if is_frozen():
        internal_static = app_dir() / "_internal" / "static"
        if internal_static.exists():
            return internal_static
    return app_dir() / "static"


def default_backups_dir() -> Path:
    if is_frozen() and sys.platform == "win32":
        return Path.home() / "Documents" / "InvoiceDatabase" / "backups"
    return app_dir() / "data" / "backups"


STATIC_DIR = static_dir()
BACKUPS_DIR = default_backups_dir()

app = FastAPI(title="Invoice Database")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ImportRequest(BaseModel):
    replace: bool = True


class RevealRequest(BaseModel):
    path: str


@app.on_event("startup")
def startup() -> None:
    init_db()
    seed_if_empty()


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = (STATIC_DIR / "invoice.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/api/fee-schedule")
def fee_schedule() -> dict[str, Any]:
    return {
        "fees": STANDARD_FEE_SCHEDULE,
        "defaults_by_sport": FEE_DEFAULTS_BY_SPORT,
    }


@app.get("/api/status")
def status() -> dict[str, Any]:
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


@app.get("/api/schools")
def api_list_schools() -> list[dict[str, Any]]:
    return [school.model_dump() for school in list_schools()]


@app.post("/api/schools")
def api_create_school(payload: SchoolCreate) -> dict[str, Any]:
    try:
        school = create_school(payload)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return school.model_dump()


@app.get("/api/schools/{school_id}")
def api_get_school(school_id: int) -> dict[str, Any]:
    school = get_school(school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")
    return school.model_dump()


@app.put("/api/schools/{school_id}")
def api_update_school(school_id: int, payload: SchoolUpdate) -> dict[str, Any]:
    try:
        school = update_school(school_id, payload)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")
    return school.model_dump()


@app.delete("/api/schools/{school_id}")
def api_delete_school(school_id: int) -> dict[str, str]:
    if not delete_school(school_id):
        raise HTTPException(status_code=404, detail="School not found")
    return {"status": "deleted"}


@app.get("/api/invoices")
def api_list_invoices() -> list[dict[str, Any]]:
    return [invoice.model_dump() for invoice in list_invoices()]


@app.post("/api/invoices")
def api_create_invoice(payload: InvoiceCreate) -> dict[str, Any]:
    if get_school(payload.school_id) is None:
        raise HTTPException(status_code=400, detail="School not found")
    invoice = create_invoice(payload)
    return invoice.model_dump()


@app.get("/api/invoices/{invoice_id}")
def api_get_invoice(invoice_id: int) -> dict[str, Any]:
    invoice = get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice.model_dump()


@app.put("/api/invoices/{invoice_id}")
def api_update_invoice(invoice_id: int, payload: InvoiceUpdate) -> dict[str, Any]:
    if payload.school_id is not None and get_school(payload.school_id) is None:
        raise HTTPException(status_code=400, detail="School not found")
    invoice = update_invoice(invoice_id, payload)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice.model_dump()


@app.get("/api/invoices/{invoice_id}/pdf")
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


@app.delete("/api/invoices/{invoice_id}")
def api_delete_invoice(invoice_id: int) -> dict[str, str]:
    if not delete_invoice(invoice_id):
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"status": "deleted"}


@app.get("/api/payments")
def api_list_payments() -> list[dict[str, Any]]:
    return [payment.model_dump() for payment in list_payments()]


@app.post("/api/payments")
def api_create_payment(payload: PaymentCreate) -> dict[str, Any]:
    if get_invoice(payload.invoice_id) is None:
        raise HTTPException(status_code=400, detail="Invoice not found")
    payment = create_payment(payload)
    return payment.model_dump()


@app.get("/api/payments/{payment_id}")
def api_get_payment(payment_id: int) -> dict[str, Any]:
    payment = get_payment(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment.model_dump()


@app.put("/api/payments/{payment_id}")
def api_update_payment(payment_id: int, payload: PaymentUpdate) -> dict[str, Any]:
    if payload.invoice_id is not None and get_invoice(payload.invoice_id) is None:
        raise HTTPException(status_code=400, detail="Invoice not found")
    payment = update_payment(payment_id, payload)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment.model_dump()


@app.delete("/api/payments/{payment_id}")
def api_delete_payment(payment_id: int) -> dict[str, str]:
    if not delete_payment(payment_id):
        raise HTTPException(status_code=404, detail="Payment not found")
    return {"status": "deleted"}


@app.get("/api/games")
def api_list_games() -> list[dict[str, Any]]:
    return [game.model_dump() for game in list_games()]


@app.post("/api/games")
def api_create_game(payload: GameCreate) -> dict[str, Any]:
    game = create_game(payload)
    return game.model_dump()


@app.get("/api/games/{game_id}")
def api_get_game(game_id: int) -> dict[str, Any]:
    game = get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return game.model_dump()


@app.put("/api/games/{game_id}")
def api_update_game(game_id: int, payload: GameUpdate) -> dict[str, Any]:
    game = update_game(game_id, payload)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return game.model_dump()


@app.delete("/api/games/{game_id}")
def api_delete_game(game_id: int) -> dict[str, str]:
    if not delete_game(game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    return {"status": "deleted"}


@app.get("/api/backup/json")
def api_download_json_backup() -> Response:
    payload = export_json_backup()
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"invoice_backup_{timestamp}.json"
    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/backup/excel")
def api_download_excel_backup() -> Response:
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"invoice_backup_{timestamp}.xlsx"
    return Response(
        content=export_excel_backup(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/backup/save")
def api_save_local_backup() -> dict[str, str]:
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    json_path = write_json_backup(BACKUPS_DIR / f"invoice_backup_{timestamp}.json")
    excel_path = write_excel_backup(BACKUPS_DIR / f"invoice_backup_{timestamp}.xlsx")
    return {
        "json_path": str(json_path),
        "excel_path": str(excel_path),
    }


@app.post("/api/backup/import")
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


@app.post("/api/import/access")
def api_import_access() -> dict[str, Any]:
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


@app.post("/api/reveal")
def reveal_file(request: RevealRequest) -> dict[str, str]:
    try:
        resolved = validate_reveal_path(
            request.path,
            exports_dir=BACKUPS_DIR,
            app_directory=app_dir(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    reveal_path(resolved)
    return {"status": "ok", "path": str(resolved)}


def open_browser_when_ready(url: str, port: int) -> None:
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.1)
    webbrowser.open(url)


def main() -> None:
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    host = "127.0.0.1"
    port = int(os.environ.get("INVOICE_APP_PORT", "8766"))
    url = f"http://{host}:{port}/"
    if not is_frozen():
        print(f"Starting Invoice Database at {url}")
        print(f"Database: {database_path()}")
    threading.Thread(
        target=open_browser_when_ready,
        args=(url, port),
        daemon=True,
    ).start()
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="warning",
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
