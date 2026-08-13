"""Backups, trash, and export/import — everything that protects the writing."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend import backup, storage
from backend.models import BackupInfo, Entry, TrashItem

router = APIRouter(prefix="/api/backup", tags=["backup"])


class ImportRequest(BaseModel):
    document: dict[str, Any]
    #: Off by default. Merging can only add; replacing is the only way to lose
    #: something, so it has to be asked for.
    replace: bool = False


class ImportResult(BaseModel):
    entries: int
    templates: int
    layouts: int
    skipped_entries: int


class RestoreResult(BaseModel):
    restored: BackupInfo
    entries_now: int


@router.get("/status")
def status() -> dict[str, Any]:
    counts = storage.stats()
    backups = backup.list_backups()
    return {
        **counts,
        "backups": len(backups),
        "latest_backup": backups[0].created_at.isoformat() if backups else None,
    }


# ---- whole-database snapshots --------------------------------------------


@router.get("/list", response_model=list[BackupInfo])
def list_backups() -> list[BackupInfo]:
    return backup.list_backups()


@router.post("/create", response_model=BackupInfo)
def create_backup() -> BackupInfo:
    info = backup.snapshot("manual", manual=True)
    if info is None:
        raise HTTPException(400, "還沒有資料庫可以備份。")
    return info


@router.post("/restore/{name}", response_model=RestoreResult)
def restore_backup(name: str) -> RestoreResult:
    try:
        info = backup.restore(name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RestoreResult(restored=info, entries_now=storage.stats()["entries"])


@router.delete("/{name}", status_code=204)
def remove_backup(name: str) -> None:
    try:
        backup.delete_backup(name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


# ---- export / import ------------------------------------------------------


@router.get("/export")
def export_all() -> JSONResponse:
    return JSONResponse(
        backup.export_all(),
        headers={
            "Content-Disposition": 'attachment; filename="journal-export.json"'
        },
    )


@router.post("/import", response_model=ImportResult)
def import_all(req: ImportRequest) -> ImportResult:
    try:
        counts = backup.import_all(req.document, replace=req.replace)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return ImportResult(**counts)


# ---- trash ----------------------------------------------------------------


@router.get("/trash", response_model=list[TrashItem])
def list_trash() -> list[TrashItem]:
    return [
        TrashItem(
            revision_id=row["id"],
            entry_id=row["entry_id"],
            entry_date=row["entry_date"],
            title=row["title"],
            char_count=row["char_count"],
            deleted_at=row["created_at"],
        )
        for row in storage.list_trash()
    ]


@router.post("/trash/{entry_id}/restore", response_model=Entry)
def undelete(entry_id: int) -> Entry:
    entry = storage.undelete_entry(entry_id)
    if entry is None:
        raise HTTPException(404, "垃圾桶裡找不到這一篇。")
    return entry


@router.delete("/trash/{entry_id}", status_code=204)
def purge(entry_id: int, confirm: bool = Query(False)) -> None:
    """Permanently remove a deleted entry's history. Requires ``confirm``."""
    if not confirm:
        raise HTTPException(400, "永久刪除需要 confirm=true。")
    if not storage.purge_trash(entry_id):
        raise HTTPException(404, "垃圾桶裡找不到這一篇。")
