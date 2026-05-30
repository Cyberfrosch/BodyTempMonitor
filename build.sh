#!/usr/bin/env bash
# build.sh — Сборка бинарей server и tool под Linux.
# Запускать из корня репозитория: bash build.sh
# PyInstaller не выполняет кросс-компиляцию:
# бинари для Windows нужно собирать на Windows (build.ps1).

set -e

# ── 1. Виртуальное окружение ─────────────────────────────────────────────────
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

# ── 2. Зависимости ───────────────────────────────────────────────────────────
echo "Installing dependencies..."
pip install -r requirements.txt -r requirements-build.txt --quiet

# ── 3. Сборка ────────────────────────────────────────────────────────────────
echo "Building server..."
pyinstaller server.spec --noconfirm

echo "Building tool..."
pyinstaller tool.spec --noconfirm

# ── 4. config.json рядом с бинарями ──────────────────────────────────────────
if [ ! -f "dist/config.json" ]; then
    cp server/config.json dist/config.json
    echo "Copied config.json to dist/"
fi

# ── 5. Итог ──────────────────────────────────────────────────────────────────
echo ""
echo "=== Build complete ==="
echo "  dist/server"
echo "  dist/tool"
echo "  dist/config.json   <- edit before use"
echo ""
echo "Usage:"
echo "  dist/server"
echo "  dist/tool config --show"
echo "  dist/tool log"
echo "  dist/tool log --monitor"
