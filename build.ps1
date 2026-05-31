# build.ps1 - Build BodyTempMonitor-server.exe, BodyTempMonitor-cli.exe and BodyTempMonitor-gui.exe on Windows.
# Run from the repository root: .\build.ps1
# PyInstaller does not cross-compile:
# Linux binaries must be built on Linux (bash build.sh).

$ErrorActionPreference = "Stop"

# -- 1. Virtual environment ---------------------------------------------------
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv venv
}

Write-Host "Activating virtual environment..."
.\venv\Scripts\Activate.ps1

# -- 2. Dependencies ----------------------------------------------------------
Write-Host "Installing dependencies..."
pip install -r requirements.txt -r requirements-build.txt --quiet

# -- 3. Build -----------------------------------------------------------------
Write-Host "Building BodyTempMonitor-server.exe..."
pyinstaller server.spec --noconfirm

Write-Host "Building BodyTempMonitor-cli.exe..."
pyinstaller tool.spec --noconfirm

Write-Host "Building BodyTempMonitor-gui.exe  (PySide6 - may take a while)..."
pyinstaller gui.spec --noconfirm

# -- 4. config.json next to binaries ------------------------------------------
# All three binaries live in dist\, so one copy of config.json covers all.
if (-not (Test-Path "dist\config.json")) {
    if (Test-Path "server\config.json") {
        Copy-Item "server\config.json" "dist\config.json"
        Write-Host "Copied config.json to dist\"
    } else {
        Write-Host "Warning: server\config.json not found - copy it to dist\ manually."
    }
}

# -- 5. Summary ---------------------------------------------------------------
Write-Host ""
Write-Host "=== Build complete ==="
Write-Host "  dist\BodyTempMonitor-server.exe   <- HTTP server + web dashboard"
Write-Host "  dist\BodyTempMonitor-cli.exe      <- CLI: config / log"
Write-Host "  dist\BodyTempMonitor-gui.exe      <- Desktop GUI (PySide6; large binary)"
Write-Host "  dist\config.json                  <- Edit before first run"
Write-Host ""
Write-Host "Files created automatically next to the binary at runtime:"
Write-Host "  sensor_data.db        <- SQLite database"
Write-Host "  device_config.json    <- Desired device config (web channel)"
Write-Host ""
Write-Host "Usage:"
Write-Host "  dist\BodyTempMonitor-server.exe"
Write-Host "  dist\BodyTempMonitor-cli.exe config --show"
Write-Host "  dist\BodyTempMonitor-cli.exe config --upload"
Write-Host "  dist\BodyTempMonitor-cli.exe log"
Write-Host "  dist\BodyTempMonitor-cli.exe log --monitor"
Write-Host "  dist\BodyTempMonitor-gui.exe"
Write-Host ""
Write-Host "Note: BodyTempMonitor-gui.exe extracts Qt on every launch (onefile)."
Write-Host "If startup is too slow, rebuild with --onedir (see README)."
