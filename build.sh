#!/usr/bin/env bash
# build.sh - Build server, tool and gui on Linux.
# Run from the repository root: bash build.sh
# PyInstaller does not cross-compile:
# Windows binaries must be built on Windows (build.ps1).

set -e

# -- 1. Virtual environment ---------------------------------------------------
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

# -- 2. Dependencies ----------------------------------------------------------
echo "Installing dependencies..."
pip install -r requirements.txt -r requirements-build.txt --quiet

# -- 3. Build -----------------------------------------------------------------
echo "Building server..."
pyinstaller server.spec --noconfirm

echo "Building tool..."
pyinstaller tool.spec --noconfirm

echo "Building gui  (PySide6 - may take a while)..."
pyinstaller gui.spec --noconfirm

# -- 4. config.json next to binaries ------------------------------------------
# All three binaries live in dist/, so one copy of config.json covers all.
if [ ! -f "dist/config.json" ]; then
    if [ -f "server/config.json" ]; then
        cp server/config.json dist/config.json
        echo "Copied config.json to dist/"
    else
        echo "Warning: server/config.json not found - copy it to dist/ manually."
    fi
fi

# -- 5. Summary ---------------------------------------------------------------
echo ""
echo "=== Build complete ==="
echo "  dist/server          <- HTTP server + web dashboard"
echo "  dist/tool            <- CLI: config / log"
echo "  dist/gui             <- Desktop GUI (PySide6; large binary)"
echo "  dist/config.json     <- Edit before first run"
echo ""
echo "Files created automatically next to the binary at runtime:"
echo "  sensor_data.db       <- SQLite database"
echo "  device_config.json   <- Desired device config (web channel)"
echo ""
echo "Usage:"
echo "  dist/server"
echo "  dist/tool config --show"
echo "  dist/tool config --upload"
echo "  dist/tool log"
echo "  dist/tool log --monitor"
echo "  dist/gui"
echo ""
echo "Note: gui extracts Qt on every launch (onefile)."
echo "If startup is too slow, rebuild with --onedir (see README)."
