"""FastAPI application entry point.

Both of these work:

    python backend/main.py            # or hit Run in your editor
    uvicorn backend.main:app --reload
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Running this file directly puts ``backend/`` on sys.path, not the project
# root, so ``import backend`` fails. Put the project root first before anything
# else.
_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import storage
from backend.config import PROJECT_ROOT, settings
from backend import backup as backup_service
from backend.routers import (
    ai,
    backup,
    entries,
    export,
    layouts,
    preferences,
    templates,
)
from backend.seed_manager import install_seeds

WEB_DIR = PROJECT_ROOT / "web"


@asynccontextmanager
async def lifespan(_: FastAPI):
    install_seeds()
    storage.init_db()
    # A rolling copy of the database, so a bad code change can never be the
    # last word on someone's journal.
    backup_service.snapshot_if_stale("startup")
    yield


app = FastAPI(
    title="FastDailyJourneyWriter",
    description="每天的日記：勾一勾、填一填，就能匯出好看的頁面與卡片。",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(templates.router)
app.include_router(layouts.router)
app.include_router(preferences.router)
app.include_router(backup.router)
app.include_router(entries.router)
app.include_router(export.router)
app.include_router(ai.router)


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "ai_available": settings.ai_enabled,
        "model": settings.model,
        "data_dir": str(settings.data_dir),
    }


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    # Both of these have to answer from the site root, not from /static/.
    # A service worker may only control paths at or below its own URL, and the
    # manifest's scope has to cover the pages it claims — served under /static/
    # they would only ever apply to /static/.
    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest() -> FileResponse:
        return FileResponse(
            WEB_DIR / "manifest.webmanifest", media_type="application/manifest+json"
        )

    @app.get("/sw.js", include_in_schema=False)
    def service_worker() -> FileResponse:
        return FileResponse(
            WEB_DIR / "sw.js",
            media_type="text/javascript",
            # The worker caches the interface, so a stale copy would pin people
            # to an old build. Let the browser re-check it on every load.
            headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
        )


def main() -> None:
    """Start the dev server. Lets you just press Run on this file."""
    import uvicorn

    # The reloader re-imports "backend.main:app" in a subprocess, which resolves
    # against the working directory — so make that the project root no matter
    # where the file was launched from.
    os.chdir(PROJECT_ROOT)

    host = os.getenv("JOURNAL_HOST", "127.0.0.1")
    port = int(os.getenv("JOURNAL_PORT", "8888"))
    reload = os.getenv("JOURNAL_RELOAD", "1") != "0"
    print(f"\n  每日日記  ->  http://{host}:{port}\n")
    uvicorn.run("backend.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
