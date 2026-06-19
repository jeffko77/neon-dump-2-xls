# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH).resolve().parent

block_cipher = None

datas = [
    (str(root / "static"), "static"),
    (str(root / "config.example.json"), "."),
    (str(root / "data"), "data"),
    (str(root / "docs" / "INVOICE_PDF_FORMAT.md"), "docs"),
]

for filename in ("Invoice Database.accdb", "Invoice  - Wentzville Lacrosse Club.pdf"):
    bundle_file = root / filename
    if bundle_file.exists():
        datas.append((str(bundle_file), "."))

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "psycopg2",
    "psycopg2._psycopg",
    "encodings",
    "app.export.database_excel_export",
    "app.invoice.routes",
    "app.invoice.invoice_pdf",
    "app.invoice.access_import",
    "app.invoice.service",
    "app.invoice.db",
    "reportlab",
    "reportlab.lib",
    "reportlab.platypus",
    "reportlab.graphics",
    "PIL",
    "PIL.Image",
    "multipart",
]

a = Analysis(
    [str(root / "app" / "launcher.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LaxSchedulerExport",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LaxSchedulerExport",
)
