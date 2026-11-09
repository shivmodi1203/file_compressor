#!/usr/bin/env bash
# Builds dist/FileCompressor. Run from this folder on a Linux machine.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

pyinstaller --noconfirm --clean --onefile --windowed \
    --name FileCompressor \
    --icon file_compressor/resources/icon.png \
    --add-data "file_compressor/resources:file_compressor/resources" \
    file_compressor/__main__.py

echo
echo "Build complete: dist/FileCompressor"
