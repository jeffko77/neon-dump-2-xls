# Building the Windows installer

## Customer install (one click)

1. Send the customer `LaxSchedulerExport-Setup.exe` and their readonly connection string (separate message).
2. Customer runs the installer, pastes the connection string on the **Database Connection** step (needed for database export).
3. Customer double-clicks **Lax Scheduler Export** — browser opens to the home page.

**Link to share with the assigner:**

```
http://127.0.0.1:8765/
```

From the home page they can open:

| Tool | URL |
|---|---|
| Home | `http://127.0.0.1:8765/` |
| Database Export | `http://127.0.0.1:8765/export` |
| Invoice Database | `http://127.0.0.1:8765/invoices` |

Exports are written to `Documents\LaxSchedulerExports\`.  
Invoice data lives in `Documents\InvoiceDatabase\`.

## Build on Windows (local)

Requirements:
- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- [Inno Setup 6](https://jrsoftware.org/isinfo.php)

```powershell
cd neon-dump-2-xls
.\scripts\build_windows.ps1
```

Output:
- `dist\LaxSchedulerExport\` — portable bundle (no installer)
- `dist\LaxSchedulerExport-Setup.exe` — customer installer

The bundle includes:
- Database Excel export (requires Neon readonly connection string)
- Invoice database with PDF export (works offline)
- Bundled original dataset (`data/invoice_database_seed.json`) for first launch and reset

On first launch, the invoice database is populated automatically from the bundled seed file.
Use **Reset to original dataset** on the Backup tab to restore after edits.

To regenerate the bundled seed after importing from Access:

```bash
uv run import-invoice-sources   # refresh local DB from .accdb
uv run export-invoice-seed      # write data/invoice_database_seed.json
```

Commit `data/invoice_database_seed.json` so CI builds include the reset dataset.

## Build via GitHub Actions

Push a version tag to trigger a Windows build:

```bash
git tag v0.2.0
git push origin v0.2.0
```

Or run **Build Windows Installer** manually from the Actions tab.

Download `LaxSchedulerExport-Setup.exe` from the workflow artifacts.

## Vendor-only: provision readonly user

```bash
uv run provision-readonly \
  --database-url "postgresql://owner:pass@host/neondb?sslmode=require" \
  --rotate-password \
  --print-connection-string
```

Send the printed readonly URL to the customer for the installer wizard.

## Local development

```bash
uv sync
uv run neon-dump
```

Opens `http://127.0.0.1:8765/` with both tools. The standalone `invoice-app` command runs the same server.
