"""SQLite persistence for journal entries.

The database file lives under the gitignored data directory, so journal
content never reaches the repository.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from typing import Any, Iterator

from app.config import settings
from app.models import Entry, EntryCreate, EntryUpdate

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date   TEXT    NOT NULL,
    title        TEXT    NOT NULL DEFAULT '',
    template_id  TEXT    NOT NULL,
    theme        TEXT    NOT NULL DEFAULT 'letterpress',
    layout       TEXT    NOT NULL DEFAULT 'letter',
    answers      TEXT    NOT NULL DEFAULT '{}',
    closing      TEXT    NOT NULL DEFAULT '',
    field_colors TEXT    NOT NULL DEFAULT '{}',
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entries_date ON entries(entry_date DESC, id DESC);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


#: Columns added after the first release. SQLite has no "ADD COLUMN IF NOT
#: EXISTS", so bring an older file forward by hand.
_MIGRATIONS = (("layout", "TEXT NOT NULL DEFAULT 'letter'"),)


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(entries)")}
        for column, spec in _MIGRATIONS:
            if column not in existing:
                conn.execute(f"ALTER TABLE entries ADD COLUMN {column} {spec}")


def _row_to_entry(row: sqlite3.Row) -> Entry:
    return Entry(
        id=row["id"],
        entry_date=date.fromisoformat(row["entry_date"]),
        title=row["title"],
        template_id=row["template_id"],
        theme=row["theme"],
        layout=row["layout"],
        answers=json.loads(row["answers"]),
        closing=row["closing"],
        field_colors=json.loads(row["field_colors"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def create_entry(payload: EntryCreate) -> Entry:
    now = datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO entries (entry_date, title, template_id, theme, layout,
                                 answers, closing, field_colors,
                                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.entry_date.isoformat(),
                payload.title,
                payload.template_id,
                payload.theme,
                payload.layout,
                json.dumps(payload.answers, ensure_ascii=False),
                payload.closing,
                json.dumps(payload.field_colors, ensure_ascii=False),
                now,
                now,
            ),
        )
        entry_id = cur.lastrowid
    entry = get_entry(entry_id)
    assert entry is not None
    return entry


def get_entry(entry_id: int) -> Entry | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        ).fetchone()
    return _row_to_entry(row) if row else None


def list_entries(limit: int = 100, offset: int = 0) -> list[Entry]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM entries ORDER BY entry_date DESC, id DESC "
            "LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [_row_to_entry(r) for r in rows]


def update_entry(entry_id: int, payload: EntryUpdate) -> Entry | None:
    existing = get_entry(entry_id)
    if existing is None:
        return None

    updates: dict[str, Any] = {}
    if payload.entry_date is not None:
        updates["entry_date"] = payload.entry_date.isoformat()
    if payload.title is not None:
        updates["title"] = payload.title
    if payload.template_id is not None:
        updates["template_id"] = payload.template_id
    if payload.theme is not None:
        updates["theme"] = payload.theme
    if payload.layout is not None:
        updates["layout"] = payload.layout
    if payload.answers is not None:
        updates["answers"] = json.dumps(payload.answers, ensure_ascii=False)
    if payload.closing is not None:
        updates["closing"] = payload.closing
    if payload.field_colors is not None:
        updates["field_colors"] = json.dumps(
            payload.field_colors, ensure_ascii=False
        )

    if not updates:
        return existing

    updates["updated_at"] = datetime.now().isoformat(timespec="seconds")
    assignments = ", ".join(f"{col} = ?" for col in updates)
    with _connect() as conn:
        conn.execute(
            f"UPDATE entries SET {assignments} WHERE id = ?",
            (*updates.values(), entry_id),
        )
    return get_entry(entry_id)


def delete_entry(entry_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    return cur.rowcount > 0


def iter_entries() -> Iterator[Entry]:
    yield from list_entries(limit=10_000)
