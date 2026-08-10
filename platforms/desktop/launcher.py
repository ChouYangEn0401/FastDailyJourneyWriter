"""Entry point for the packaged desktop build.

Everything OS-specific about the desktop build lives in this one file, which
is why ``backend/`` can stay platform-agnostic. This script works out where
the bundled files and the user's journal belong, puts both in the
environment, and only then imports the app — ``backend.config`` reads those
two variables and otherwise behaves exactly as it does from a checkout.

Not used when running from source; ``run.py`` is the entry point there.
"""

from __future__ import annotations

import os
import sys
import threading
import webbrowser
from pathlib import Path

APP_NAME = "FastDailyJourneyWriter"


def bundle_dir() -> Path:
    """Where the shipped read-only files (``content/``, ``web/``) ended up.

    PyInstaller sets ``sys._MEIPASS`` to the unpacked bundle. Falling back to
    the repo root means this file still runs from a checkout.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent.parent


def data_dir() -> Path:
    """Where the journal is written.

    Never inside the bundle: a onefile build unpacks to a temp directory that
    is deleted on exit, and an installed app directory is often read-only. So
    the data goes where each OS expects user data to go.
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / APP_NAME


def main() -> None:
    # setdefault, so someone can still point a packaged build at another
    # folder with JOURNAL_DATA_DIR.
    os.environ.setdefault("JOURNAL_BUNDLE_DIR", str(bundle_dir()))
    os.environ.setdefault("JOURNAL_DATA_DIR", str(data_dir()))
    # There is no source tree to watch in a frozen build, and the reloader
    # would try to re-exec the bundle.
    os.environ["JOURNAL_RELOAD"] = "0"

    host = os.environ.get("JOURNAL_HOST", "127.0.0.1")
    port = int(os.environ.get("JOURNAL_PORT", "8888"))

    import uvicorn

    from backend.main import app  # imported after the environment is set

    url = f"http://{host}:{port}"
    print(f"\n  每日日記  ->  {url}")
    print(f"  日記存放在：{os.environ['JOURNAL_DATA_DIR']}")
    print("  關掉這個視窗就會停止。\n")

    # The server blocks, so the browser has to be opened from a timer.
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
