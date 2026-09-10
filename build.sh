#!/usr/bin/env bash
set -e

echo "========================================"
echo "  Tomato Timer Builder (macOS / Linux)"
echo "========================================"
echo

cd "$(dirname "$0")"

echo "[1/2] Installing PyInstaller..."
python3 -m pip install pyinstaller -q

echo "[2/2] Building..."
python3 -m PyInstaller \
    --noconfirm \
    --onedir \
    --windowed \
    --name "TomatoTimer" \
    --add-data "app/ui/style.qss:app/ui" \
    main.py

echo
echo "========================================"
echo "  Build done!"
echo "  Output: dist/TomatoTimer/"
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "  Run:    open dist/TomatoTimer/TomatoTimer.app"
else
    echo "  Run:    ./dist/TomatoTimer/TomatoTimer"
fi
echo "========================================"
