# Building the Windows installer

## Customer install (one click)

1. Send the customer `LaxSchedulerExport-Setup.exe` and their readonly connection string (separate message).
2. Customer runs the installer, pastes the connection string on the **Database Connection** step.
3. Customer double-clicks **Lax Scheduler Export** — browser opens, click **Export**.

Exports are written to `Documents\LaxSchedulerExports\`.

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

## Build via GitHub Actions

Push a version tag to trigger a Windows build:

```bash
git tag v0.1.0
git push origin v0.1.0
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
