from __future__ import annotations

import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.connection import (
    ConfigError,
    app_dir,
    connection_host,
    is_frozen,
    load_database_url,
)
from app.export.database_excel_export import DEFAULT_SCHEMAS, export_database_to_excel
from app.invoice.routes import BACKUPS_DIR, init_invoice_db, register_invoice_routes
from app.reveal import reveal_path, validate_reveal_path


def static_dir() -> Path:
    if is_frozen():
        internal_static = app_dir() / "_internal" / "static"
        if internal_static.exists():
            return internal_static
    return app_dir() / "static"


def default_exports_dir() -> Path:
    if is_frozen() and sys.platform == "win32":
        return Path.home() / "Documents" / "LaxSchedulerExports"
    return app_dir() / "exports"


STATIC_DIR = static_dir()
EXPORTS_DIR = default_exports_dir()


@dataclass
class ExportState:
    status: str = "idle"
    current_table: str | None = None
    current_index: int = 0
    total_tables: int = 0
    output_path: str | None = None
    diagram_path: str | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


export_state = ExportState()
export_lock = threading.Lock()

app = FastAPI(title="Lax Scheduler Tools")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
register_invoice_routes(app)


class RevealRequest(BaseModel):
    path: str


class ExportRequest(BaseModel):
    output_dir: str | None = None
    schemas: list[str] = Field(default_factory=lambda: list(DEFAULT_SCHEMAS))


@app.on_event("startup")
def startup() -> None:
    init_invoice_db()
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    html = (STATIC_DIR / "home.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/export", response_class=HTMLResponse)
def export_page() -> HTMLResponse:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/invoices", response_class=HTMLResponse)
def invoices_page() -> HTMLResponse:
    html = (STATIC_DIR / "invoice.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/api/export/status")
def export_status() -> dict:
    try:
        database_url = load_database_url()
        configured = True
        host = connection_host(database_url)
        config_error = None
    except ConfigError as exc:
        configured = False
        host = None
        config_error = str(exc)

    with export_lock:
        state = asdict(export_state)

    return {
        "configured": configured,
        "host": host,
        "config_error": config_error,
        "export": state,
        "exports_dir": str(EXPORTS_DIR),
        "app_dir": str(app_dir()),
        "frozen": is_frozen(),
    }


def _run_export(output_path: Path, schemas: tuple[str, ...]) -> None:
    global export_state

    def on_progress(table_name: str, index: int, total: int) -> None:
        with export_lock:
            export_state.current_table = table_name
            export_state.current_index = index
            export_state.total_tables = total

    try:
        database_url = load_database_url()
        summary = export_database_to_excel(
            database_url,
            str(output_path),
            schemas=schemas,
            progress_callback=on_progress,
        )
        with export_lock:
            export_state.status = "completed"
            export_state.output_path = summary.output_path
            export_state.diagram_path = summary.diagram_path
            export_state.finished_at = datetime.now(UTC).isoformat()
    except Exception as exc:  # noqa: BLE001
        with export_lock:
            export_state.status = "failed"
            export_state.error = str(exc)
            export_state.finished_at = datetime.now(UTC).isoformat()


@app.post("/api/export")
def start_export(request: ExportRequest) -> dict:
    with export_lock:
        if export_state.status == "running":
            raise HTTPException(status_code=409, detail="Export already running")

        try:
            load_database_url()
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        output_dir = Path(request.output_dir) if request.output_dir else EXPORTS_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"lacrosse_scheduler_export_{timestamp}.xlsx"

        schemas = tuple(request.schemas) if request.schemas else DEFAULT_SCHEMAS

        export_state.status = "running"
        export_state.current_table = None
        export_state.current_index = 0
        export_state.total_tables = 0
        export_state.output_path = str(output_path)
        export_state.error = None
        export_state.started_at = datetime.now(UTC).isoformat()
        export_state.finished_at = None

    thread = threading.Thread(
        target=_run_export,
        args=(output_path, schemas),
        daemon=True,
    )
    thread.start()
    return {"status": "running", "output_path": str(output_path)}


@app.post("/api/reveal")
def reveal_file(request: RevealRequest) -> dict:
    try:
        resolved = validate_reveal_path(
            request.path,
            exports_dir=EXPORTS_DIR,
            app_directory=app_dir(),
            extra_roots=[BACKUPS_DIR, BACKUPS_DIR.parent],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    reveal_path(resolved)
    return {"status": "ok", "path": str(resolved)}


@app.get("/api/export/latest")
def latest_export() -> dict:
    with export_lock:
        return asdict(export_state)


def ensure_stdio() -> None:
    if not is_frozen():
        return
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115


def write_startup_error(exc: BaseException) -> None:
    if not is_frozen():
        return
    log_path = app_dir() / "startup-error.log"
    log_path.write_text(traceback.format_exc(), encoding="utf-8")


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
    try:
        ensure_stdio()
        host = "127.0.0.1"
        port = int(os.environ.get("LAX_SCHEDULER_PORT", os.environ.get("NEON_DUMP_PORT", "8765")))
        url = f"http://{host}:{port}/"
        if not is_frozen():
            print(f"Starting Lax Scheduler Tools at {url}")
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
    except Exception as exc:
        write_startup_error(exc)
        raise


if __name__ == "__main__":
    main()
