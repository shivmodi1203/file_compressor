#!/usr/bin/env bash
# Builds the Linux AppImage and tar.gz into release/. Run from this folder.
# The AppImage step needs appimagetool on PATH, or its path in $APPIMAGETOOL.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

python tools/build.py
