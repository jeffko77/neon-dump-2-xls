# Build the Windows desktop bundle and installer.
# Requires: Python 3.11+, uv, PyInstaller, Inno Setup 6 (ISCC.exe on PATH)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> Syncing Python dependencies"
uv sync
uv pip install pyinstaller

Write-Host "==> Building PyInstaller bundle"
uv run pyinstaller build/pyinstaller.spec --noconfirm --clean

$BundleDir = Join-Path $Root "dist\LaxSchedulerExport"
if (-not (Test-Path $BundleDir)) {
    throw "Expected bundle at $BundleDir"
}

Write-Host "==> Building Inno Setup installer"
$Iscc = $env:ISCC_PATH
if (-not $Iscc) {
    $Iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
}
if (-not (Test-Path $Iscc)) {
    Write-Warning "Inno Setup compiler not found. Bundle is ready at dist\LaxSchedulerExport"
    Write-Warning "Install Inno Setup 6 and re-run, or set ISCC_PATH to ISCC.exe"
    exit 0
}

& $Iscc "installer\lax-scheduler-export.iss"
Write-Host "==> Done. Installer: dist\LaxSchedulerExport-Setup.exe"
