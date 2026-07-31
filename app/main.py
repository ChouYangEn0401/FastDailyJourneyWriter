"""FastAPI application entry point.

Both of these work:

    python app/main.py            # or hit Run in your editor
    uvicorn app.main:app --reload
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Running this file directly puts ``app/`` on sys.path, not the project root,
# so ``import app`` fails. Put the project root first before anything else.
_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import storage
from app.config import PROJECT_ROOT, settings
from app.routers import ai, entries, export, layouts, templates
from app.seed_manager import install_seeds

WEB_DIR = PROJECT_ROOT / "web"


@asynccontextmanager
async def lifespan(_: FastAPI):
    install_seeds()
    storage.init_db()
    yield


app = FastAPI(
    title="FastDailyJourneyWriter",
    description="每天的靈修日記：勾一勾、填一填，就能匯出好看的頁面與卡片。",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(templates.router)
app.include_router(layouts.router)
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


def main() -> None:
    """Start the dev server. Lets you just press Run on this file."""
    import uvicorn

    # The reloader re-imports "app.main:app" in a subprocess, which resolves
    # against the working directory — so make that the project root no matter
    # where the file was launched from.
    os.chdir(PROJECT_ROOT)

    host = os.getenv("JOURNAL_HOST", "127.0.0.1")
    port = int(os.getenv("JOURNAL_PORT", "8000"))
    reload = os.getenv("JOURNAL_RELOAD", "1") != "0"
    print(f"\n  每日靈修日記  ->  http://{host}:{port}\n")
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
