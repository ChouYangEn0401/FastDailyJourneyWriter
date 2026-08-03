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

-- Every version an entry has ever had that we were about to replace or
-- delete. This is what makes a bad save survivable: the previous text is
-- still here, and can be put back.
CREATE TABLE IF NOT EXISTS entry_revisions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id     INTEGER NOT NULL,
    entry_date   TEXT    NOT NULL,
    title        TEXT    NOT NULL DEFAULT '',
    template_id  TEXT    NOT NULL,
    theme        TEXT    NOT NULL DEFAULT 'letterpress',
    layout       TEXT    NOT NULL DEFAULT 'letter',
    answers      TEXT    NOT NULL DEFAULT '{}',
    closing      TEXT    NOT NULL DEFAULT '',
    field_colors TEXT    NOT NULL DEFAULT '{}',
    char_count   INTEGER NOT NULL DEFAULT 0,
    -- 'edit' | 'delete' | 'restore' | 'import'
    reason       TEXT    NOT NULL DEFAULT 'edit',
    created_at   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rev_entry ON entry_revisions(entry_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_rev_reason ON entry_revisions(reason, id DESC);
"""

#: How many ordinary edit revisions to keep per entry. Deletions are never
#: pruned — they are the only remaining copy of that writing.
MAX_EDIT_REVISIONS = 40

#: Don't snapshot on every debounced autosave. One per this many seconds is
#: enough to recover from a mistake, unless the change destroys text (see
#: :func:`_should_snapshot`), in which case we always snapshot.
SNAPSHOT_INTERVAL_SECONDS = 180


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


def _plain_length(answers: dict[str, Any], closing: str) -> int:
    """Roughly how much writing an entry holds.

    Used to decide whether a save is destroying text, so it counts the same
    way for every shape an answer can take.
    """
    from app.richtext import to_plain

    parts = [to_plain(closing)]
    for value in answers.values():
        if isinstance(value, str):
            parts.append(to_plain(value))
        elif isinstance(value, list):
            parts.extend(to_plain(str(v)) for v in value)
    return len([c for c in "".join(parts) if not c.isspace()])


def _snapshot(conn: sqlite3.Connection, row: sqlite3.Row, reason: str) -> None:
    conn.execute(
        """
        INSERT INTO entry_revisions
            (entry_id, entry_date, title, template_id, theme, layout,
             answers, closing, field_colors, char_count, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["id"],
            row["entry_date"],
            row["title"],
            row["template_id"],
            row["theme"],
            row["layout"],
            row["answers"],
            row["closing"],
            row["field_colors"],
            _plain_length(json.loads(row["answers"]), row["closing"]),
            reason,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    # Prune only ordinary edits; a 'delete' revision may be the last copy.
    conn.execute(
        """
        DELETE FROM entry_revisions
         WHERE reason = 'edit' AND entry_id = ? AND id NOT IN (
               SELECT id FROM entry_revisions
                WHERE reason = 'edit' AND entry_id = ?
                ORDER BY id DESC LIMIT ?
         )
        """,
        (row["id"], row["id"], MAX_EDIT_REVISIONS),
    )


def _should_snapshot(
    conn: sqlite3.Connection, row: sqlite3.Row, new_len: int
) -> bool:
    """Snapshot before an overwrite?

    Always, when the save shrinks the entry — that is the case where someone
    loses work and needs it back. Otherwise at a modest interval, so ordinary
    typing does not fill the table.
    """
    old_len = _plain_length(json.loads(row["answers"]), row["closing"])
    if old_len == 0:
        return False
    if new_len < old_len:
        return True

    last = conn.execute(
        "SELECT created_at FROM entry_revisions WHERE entry_id = ? "
        "ORDER BY id DESC LIMIT 1",
        (row["id"],),
    ).fetchone()
    if last is None:
        return True
    age = (
        datetime.now() - datetime.fromisoformat(last["created_at"])
    ).total_seconds()
    return age >= SNAPSHOT_INTERVAL_SECONDS


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


def get_entry_by_date(entry_date: date) -> Entry | None:
    """The most recently touched entry for a day.

    The editor uses this on startup so reopening the app continues the day you
    were already writing, instead of silently starting a second entry for it.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM entries WHERE entry_date = ? "
            "ORDER BY updated_at DESC, id DESC LIMIT 1",
            (entry_date.isoformat(),),
        ).fetchone()
    return _row_to_entry(row) if row else None


def count_entries_on(entry_date: date) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM entries WHERE entry_date = ?",
            (entry_date.isoformat(),),
        ).fetchone()
    return int(row["n"])


def list_entries(limit: int = 100, offset: int = 0) -> list[Entry]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM entries ORDER BY entry_date DESC, id DESC "
            "LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [_row_to_entry(r) for r in rows]


class StaleWriteError(RuntimeError):
    """The entry changed since the client last read it.

    Raised instead of overwriting, so a second tab (or a stale form left open
    overnight) cannot silently replace newer writing.
    """

    def __init__(self, current: Entry) -> None:
        super().__init__("這篇日記在別的地方被改過了。")
        self.current = current


def update_entry(entry_id: int, payload: EntryUpdate) -> Entry | None:
    existing = get_entry(entry_id)
    if existing is None:
        return None

    if (
        payload.expected_updated_at is not None
        and payload.expected_updated_at.replace(microsecond=0)
        != existing.updated_at.replace(microsecond=0)
    ):
        raise StaleWriteError(existing)

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
        row = conn.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        ).fetchone()
        new_len = _plain_length(
            payload.answers if payload.answers is not None else existing.answers,
            payload.closing if payload.closing is not None else existing.closing,
        )
        if _should_snapshot(conn, row, new_len):
            _snapshot(conn, row, "edit")

        conn.execute(
            f"UPDATE entries SET {assignments} WHERE id = ?",
            (*updates.values(), entry_id),
        )
    return get_entry(entry_id)


def delete_entry(entry_id: int) -> bool:
    """Delete an entry, keeping a copy that can be put back.

    Nothing anyone wrote is destroyed by a delete — it moves to the trash,
    which is what :func:`list_trash` and :func:`undelete_entry` read.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if row is None:
            return False
        _snapshot(conn, row, "delete")
        conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    return True


# --------------------------------------------------------------------------
# Revisions and trash
# --------------------------------------------------------------------------


def list_revisions(entry_id: int) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, entry_id, entry_date, title, template_id, char_count, "
            "reason, created_at FROM entry_revisions WHERE entry_id = ? "
            "ORDER BY id DESC",
            (entry_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_trash() -> list[dict[str, Any]]:
    """Deleted entries whose id no longer exists in ``entries``."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT r.id, r.entry_id, r.entry_date, r.title, r.template_id,
                   r.char_count, r.created_at
              FROM entry_revisions r
              JOIN (SELECT entry_id, MAX(id) AS top
                      FROM entry_revisions WHERE reason = 'delete'
                     GROUP BY entry_id) latest
                ON latest.top = r.id
             WHERE r.entry_id NOT IN (SELECT id FROM entries)
             ORDER BY r.id DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def _revision_row(conn: sqlite3.Connection, revision_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM entry_revisions WHERE id = ?", (revision_id,)
    ).fetchone()


def restore_revision(revision_id: int) -> Entry | None:
    """Put a past version back.

    The version being replaced is snapshotted first, so restoring is itself
    undoable and can never be the step that loses something.
    """
    now = datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        rev = _revision_row(conn, revision_id)
        if rev is None:
            return None
        entry_id = rev["entry_id"]
        current = conn.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        ).fetchone()

        if current is not None:
            _snapshot(conn, current, "restore")
            conn.execute(
                """
                UPDATE entries SET entry_date = ?, title = ?, template_id = ?,
                       theme = ?, layout = ?, answers = ?, closing = ?,
                       field_colors = ?, updated_at = ?
                 WHERE id = ?
                """,
                (
                    rev["entry_date"], rev["title"], rev["template_id"],
                    rev["theme"], rev["layout"], rev["answers"], rev["closing"],
                    rev["field_colors"], now, entry_id,
                ),
            )
        else:
            # The entry itself is gone (deleted). Recreate it under its
            # original id so links and revision history stay attached.
            conn.execute(
                """
                INSERT INTO entries (id, entry_date, title, template_id, theme,
                                     layout, answers, closing, field_colors,
                                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id, rev["entry_date"], rev["title"], rev["template_id"],
                    rev["theme"], rev["layout"], rev["answers"], rev["closing"],
                    rev["field_colors"], rev["created_at"], now,
                ),
            )
    return get_entry(entry_id)


def undelete_entry(entry_id: int) -> Entry | None:
    with _connect() as conn:
        rev = conn.execute(
            "SELECT id FROM entry_revisions WHERE entry_id = ? AND reason = 'delete' "
            "ORDER BY id DESC LIMIT 1",
            (entry_id,),
        ).fetchone()
    return restore_revision(rev["id"]) if rev else None


def purge_trash(entry_id: int) -> bool:
    """Permanently drop a deleted entry's history. Not undoable."""
    with _connect() as conn:
        if conn.execute(
            "SELECT 1 FROM entries WHERE id = ?", (entry_id,)
        ).fetchone():
            return False  # still live; deleting its history is not "purge"
        cur = conn.execute(
            "DELETE FROM entry_revisions WHERE entry_id = ?", (entry_id,)
        )
    return cur.rowcount > 0


def stats() -> dict[str, int]:
    with _connect() as conn:
        entries = conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]
        revisions = conn.execute(
            "SELECT COUNT(*) AS n FROM entry_revisions"
        ).fetchone()["n"]
    return {"entries": entries, "revisions": revisions, "trash": len(list_trash())}


def iter_entries() -> Iterator[Entry]:
    yield from list_entries(limit=10_000)
