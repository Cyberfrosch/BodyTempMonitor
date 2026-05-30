# build.ps1 — Сборка бинарей server.exe и tool.exe под Windows.
# Запускать из корня репозитория: .\build.ps1
# PyInstaller не выполняет кросс-компиляцию:
# бинари для Linux нужно собирать на Linux (bash build.sh).

$ErrorActionPreference = "Stop"

# ── 1. Виртуальное окружение ─────────────────────────────────────────────────
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv venv
}

Write-Host "Activating virtual environment..."
.\venv\Scripts\Activate.ps1

# ── 2. Зависимости ───────────────────────────────────────────────────────────
Write-Host "Installing dependencies..."
pip install -r requirements.txt -r requirements-build.txt --quiet

# ── 3. Сборка ────────────────────────────────────────────────────────────────
Write-Host "Building server.exe..."
pyinstaller server.spec --noconfirm

Write-Host "Building tool.exe..."
pyinstaller tool.spec --noconfirm

# ── 4. config.json рядом с бинарями ──────────────────────────────────────────
if (-not (Test-Path "dist\config.json")) {
    Copy-Item "server\config.json" "dist\config.json"
    Write-Host "Copied config.json to dist\"
}

# ── 5. Итог ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Build complete ==="
Write-Host "  dist\server.exe"
Write-Host "  dist\tool.exe"
Write-Host "  dist\config.json   <- edit before use"
Write-Host ""
Write-Host "Usage:"
Write-Host "  dist\server.exe"
Write-Host "  dist\tool.exe config --show"
Write-Host "  dist\tool.exe log"
Write-Host "  dist\tool.exe log --monitor"
