"""Whole-database snapshots, and export/import of everything you own.

Three layers of safety sit under the editor, each catching what the one above
it cannot:

1. **Entry revisions** (:mod:`backend.storage`) — undo a single bad save.
2. **Snapshots** (here) — undo a bad *release*: a code change that corrupts
   many entries at once is still recoverable, because a copy of the whole
   database is taken before anything risky and on a rolling schedule.
3. **Export** (here) — a plain JSON file you can keep somewhere else
   entirely, so a lost laptop is not a lost journal.

Snapshots use SQLite's own backup API rather than copying the file, so a
snapshot taken while the app is mid-write is still a consistent database.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from backend import preferences, storage
from backend.config import settings
from backend.models import BackupInfo

log = logging.getLogger(__name__)

#: Automatic snapshots to keep. Manual ones are never pruned.
KEEP_AUTOMATIC = 20
#: Take a rolling snapshot at most this often.
ROLLING_INTERVAL = timedelta(hours=6)

_AUTO_RE = re.compile(r"^journal-(\d{8}-\d{6})(?:-(.+?))?\.sqlite3$")
_MANUAL_PREFIX = "manual-"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+\.sqlite3$")


def _dir() -> Path:
    settings.backups_dir.mkdir(parents=True, exist_ok=True)
    return settings.backups_dir


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def snapshot(reason: str = "auto", *, manual: bool = False) -> BackupInfo | None:
    """Copy the database to ``data/backups/``.

    ``reason`` becomes part of the filename so it is obvious later *why* a
    snapshot exists ("before-import", "before-restore").
    """
    if not settings.db_path.exists():
        return None

    safe_reason = re.sub(r"[^a-z0-9-]+", "-", reason.lower()).strip("-") or "auto"
    prefix = _MANUAL_PREFIX if manual else ""
    name = f"{prefix}journal-{_timestamp()}-{safe_reason}.sqlite3"
    target = _dir() / name

    source = sqlite3.connect(settings.db_path)
    try:
        dest = sqlite3.connect(target)
        try:
            # Consistent even if a write is in flight, unlike a file copy.
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()

    if not manual:
        _prune()
    log.info("snapshot: %s", name)
    return _describe(target)


def snapshot_if_stale(reason: str = "rolling") -> BackupInfo | None:
    """Take a rolling snapshot unless a recent one already exists."""
    newest = max(
        (b for b in list_backups() if b.automatic),
        key=lambda b: b.created_at,
        default=None,
    )
    if newest and datetime.now() - newest.created_at < ROLLING_INTERVAL:
        return None
    return snapshot(reason)


def _describe(path: Path) -> BackupInfo:
    stat = path.stat()
    manual = path.name.startswith(_MANUAL_PREFIX)
    match = _AUTO_RE.match(path.name.removeprefix(_MANUAL_PREFIX))
    created = (
        datetime.strptime(match.group(1), "%Y%m%d-%H%M%S")
        if match
        else datetime.fromtimestamp(stat.st_mtime)
    )
    return BackupInfo(
        name=path.name,
        size_bytes=stat.st_size,
        created_at=created,
        automatic=not manual,
    )


def list_backups() -> list[BackupInfo]:
    out = [
        _describe(p)
        for p in _dir().glob("*.sqlite3")
        if p.is_file()
    ]
    out.sort(key=lambda b: b.created_at, reverse=True)
    return out


def _prune() -> None:
    automatic = [b for b in list_backups() if b.automatic]
    for old in automatic[KEEP_AUTOMATIC:]:
        (_dir() / old.name).unlink(missing_ok=True)


def resolve(name: str) -> Path:
    """Turn a client-supplied backup name into a path inside the backup dir.

    Rejects anything that is not a plain filename, so a crafted name cannot
    read or overwrite a file elsewhere on disk.
    """
    if not _SAFE_NAME.match(name):
        raise ValueError("備份檔名不合法。")
    path = (_dir() / name).resolve()
    if path.parent != _dir().resolve() or not path.is_file():
        raise ValueError("找不到這個備份。")
    return path


def restore(name: str) -> BackupInfo:
    """Replace the live database with a snapshot.

    Takes a snapshot of the *current* state first, so restoring the wrong one
    is itself undoable.
    """
    source = resolve(name)
    safety = snapshot("before-restore")
    shutil.copyfile(source, settings.db_path)
    storage.init_db()
    log.info("restored %s (safety copy: %s)", name, safety.name if safety else "none")
    return _describe(source)


def delete_backup(name: str) -> bool:
    path = resolve(name)
    path.unlink()
    return True


# --------------------------------------------------------------------------
# Export / import
# --------------------------------------------------------------------------

EXPORT_VERSION = 1


def export_all() -> dict[str, Any]:
    """Everything the user owns, as one JSON-able document."""
    return {
        "format": "fastdailyjournalwriter.export",
        "version": EXPORT_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "entries": [
            e.model_dump(mode="json") for e in storage.list_entries(limit=100_000)
        ],
        "templates": [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(settings.templates_dir.glob("*.json"))
        ],
        "layouts": [
            {
                "id": p.name.removesuffix(".html.j2"),
                "html": p.read_text(encoding="utf-8"),
                "meta": json.loads(
                    (settings.layouts_dir / f"{p.name.removesuffix('.html.j2')}.json")
                    .read_text(encoding="utf-8")
                )
                if (
                    settings.layouts_dir
                    / f"{p.name.removesuffix('.html.j2')}.json"
                ).exists()
                else {},
            }
            for p in sorted(settings.layouts_dir.glob("*.html.j2"))
            if not p.name.startswith("_")
        ],
        "preferences": preferences.load().model_dump(mode="json"),
    }


def import_all(document: dict[str, Any], *, replace: bool = False) -> dict[str, int]:
    """Load an export back in.

    Defaults to **merging**: existing entries are kept and the imported ones
    are added alongside. Nothing already on disk is destroyed unless
    ``replace`` is asked for explicitly — and even then a snapshot is taken
    first, so the previous state is one click away.
    """
    if document.get("format") != "fastdailyjournalwriter.export":
        raise ValueError("這不是這個程式匯出的檔案。")

    snapshot("before-import")

    counts = {"entries": 0, "templates": 0, "layouts": 0, "skipped_entries": 0}

    if replace:
        for entry in storage.list_entries(limit=100_000):
            storage.delete_entry(entry.id)

    existing = {
        (e.entry_date.isoformat(), e.title, e.template_id)
        for e in storage.list_entries(limit=100_000)
    }

    from backend.models import EntryCreate

    for raw in document.get("entries", []):
        key = (raw.get("entry_date"), raw.get("title", ""), raw.get("template_id"))
        if key in existing:
            # Same day, same title, same question set — treat as already here
            # rather than making a duplicate on every import.
            counts["skipped_entries"] += 1
            continue
        try:
            storage.create_entry(EntryCreate.model_validate(raw))
            counts["entries"] += 1
            existing.add(key)
        except Exception as exc:  # noqa: BLE001 - one bad row must not abort
            log.warning("skipping unreadable entry in import: %s", exc)
            counts["skipped_entries"] += 1

    for tpl in document.get("templates", []):
        tid = tpl.get("id")
        if not tid:
            continue
        (settings.templates_dir / f"{tid}.json").write_text(
            json.dumps(tpl, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        counts["templates"] += 1

    for layout in document.get("layouts", []):
        lid = layout.get("id")
        if not lid or not _SAFE_NAME.match(f"{lid}.sqlite3"):
            continue  # same filename rules; keeps ids to safe characters
        (settings.layouts_dir / f"{lid}.html.j2").write_text(
            layout.get("html", ""), encoding="utf-8"
        )
        if layout.get("meta"):
            (settings.layouts_dir / f"{lid}.json").write_text(
                json.dumps(layout["meta"], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        counts["layouts"] += 1

    if document.get("preferences"):
        from backend.models import Preferences

        try:
            preferences.save(Preferences.model_validate(document["preferences"]))
        except Exception as exc:  # noqa: BLE001
            log.warning("preferences in import were unreadable: %s", exc)

    return counts
