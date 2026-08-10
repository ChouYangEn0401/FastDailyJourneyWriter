#!/usr/bin/env sh
# macOS / Linux counterpart to run.bat.
#   chmod +x run.sh   (once)
#   ./run.sh
set -e
cd "$(dirname "$0")"
exec .venv/bin/python run.py
