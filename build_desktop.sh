#!/usr/bin/env sh
# Package the app into dist/ (macOS .app, or a folder on Linux).
# First time only:  .venv/bin/pip install -r requirements-dev.txt
set -e
cd "$(dirname "$0")"
.venv/bin/python -m PyInstaller --noconfirm --clean platforms/desktop/journal.spec
echo
echo "Done. The app is in dist/"
