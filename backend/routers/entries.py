"""CRUD for journal entries."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend import storage
from backend.models import Entry, EntryCreate, EntryRevision, EntryUpdate, FieldKind
from backend.richtext import sanitize, to_plain
from backend.template_registry import get_template
from backend.services import (
    orphan_answers,
    require_entry,
    require_template,
    sanitize_answers,
    sanitize_field_colors,
)

router = APIRouter(prefix="/api/entries", tags=["entries"])


class EntrySummary(BaseModel):
    id: int
    entry_date: date
    title: str
    template_id: str
    layout: str
    #: Characters of actual writing — lets the editor show which entries are
    #: blank leftovers without downloading everyone's journal.
    word_count: int
    is_empty: bool
    updated_at: str


class OrphanInfo(BaseModel):
    """Answers kept on the entry that the current template has no field for."""

    field_id: str
    preview: str


#: Answers to these kinds are option ids ("yes"), not writing — counting them
#: would make a single tick look like a written entry.
_TICK_KINDS = {FieldKind.CHOICE, FieldKind.SCALE, FieldKind.MULTI_CHOICE}


def _entry_word_count(entry: Entry) -> int:
    template = get_template(entry.template_id)
    kinds = (
        {fid: f.kind for fid, f in template.field_map().items()} if template else {}
    )

    parts: list[str] = [to_plain(entry.closing)]
    for field_id, value in entry.answers.items():
        if kinds.get(field_id) in _TICK_KINDS:
            continue
        if isinstance(value, str):
            parts.append(to_plain(value))
        elif isinstance(value, list):
            parts.extend(to_plain(str(v)) for v in value)
    return len([c for c in "".join(parts) if not c.isspace()])


@router.get("", response_model=list[EntrySummary])
def list_entries(
    limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)
) -> list[EntrySummary]:
    out: list[EntrySummary] = []
    for entry in storage.list_entries(limit=limit, offset=offset):
        count = _entry_word_count(entry)
        out.append(
            EntrySummary(
                id=entry.id,
                entry_date=entry.entry_date,
                title=entry.title,
                template_id=entry.template_id,
                layout=entry.layout,
                word_count=count,
                is_empty=count == 0 and not entry.title.strip(),
                updated_at=entry.updated_at.isoformat(timespec="minutes"),
            )
        )
    return out


@router.get("/by-date/{entry_date}", response_model=Entry | None)
def read_entry_by_date(entry_date: date) -> Entry | None:
    """The entry already in progress for a day, if there is one."""
    return storage.get_entry_by_date(entry_date)


@router.post("", response_model=Entry, status_code=201)
def create_entry(payload: EntryCreate) -> Entry:
    template = require_template(payload.template_id)
    payload = payload.model_copy(
        update={
            "answers": sanitize_answers(template, payload.answers),
            "field_colors": sanitize_field_colors(payload.field_colors),
            "closing": sanitize(payload.closing),
        }
    )
    return storage.create_entry(payload)


@router.get("/{entry_id}", response_model=Entry)
def read_entry(entry_id: int) -> Entry:
    entry, _ = require_entry(entry_id)
    return entry


@router.get("/{entry_id}/orphans", response_model=list[OrphanInfo])
def read_orphans(entry_id: int, template_id: str | None = None) -> list[OrphanInfo]:
    """What this entry holds that the given template would not show.

    The editor calls this before switching question sets, so "will I lose what
    I already wrote?" has a concrete answer instead of a guess.
    """
    entry, entry_template = require_entry(entry_id)
    template = require_template(template_id) if template_id else entry_template

    out: list[OrphanInfo] = []
    for field_id, value in orphan_answers(template, entry.answers).items():
        if isinstance(value, list):
            # Drop blank rows before joining, or an all-empty list previews as
            # a row of separators ("/ / /") and looks like content.
            written = [t for t in (to_plain(str(v)) for v in value) if t.strip()]
            text = " / ".join(written)
        else:
            text = to_plain(str(value))
        text = text.strip()
        if text:
            out.append(
                OrphanInfo(
                    field_id=field_id,
                    preview=text[:80] + ("…" if len(text) > 80 else ""),
                )
            )
    return out


@router.get("/{entry_id}/revisions", response_model=list[EntryRevision])
def list_revisions(entry_id: int) -> list[EntryRevision]:
    """Past versions of this entry, newest first."""
    require_entry(entry_id)
    return [EntryRevision(**row) for row in storage.list_revisions(entry_id)]


@router.post("/revisions/{revision_id}/restore", response_model=Entry)
def restore_revision(revision_id: int) -> Entry:
    entry = storage.restore_revision(revision_id)
    if entry is None:
        raise HTTPException(404, f"找不到這個版本 #{revision_id}")
    return entry


@router.patch("/{entry_id}", response_model=Entry)
def update_entry(entry_id: int, payload: EntryUpdate) -> Entry:
    existing, _ = require_entry(entry_id)
    template = require_template(payload.template_id or existing.template_id)

    updates: dict[str, object] = {}
    if payload.answers is not None:
        # Merge over what is already stored: a PATCH carrying only the fields
        # the current template renders must not delete the rest.
        merged = {**existing.answers, **payload.answers}
        updates["answers"] = sanitize_answers(template, merged)
    if payload.field_colors is not None:
        updates["field_colors"] = sanitize_field_colors(payload.field_colors)
    if payload.closing is not None:
        updates["closing"] = sanitize(payload.closing)

    try:
        updated = storage.update_entry(entry_id, payload.model_copy(update=updates))
    except storage.StaleWriteError as exc:
        # 409 rather than an overwrite: the client decides whether to keep its
        # own version or take the newer one.
        raise HTTPException(
            409,
            "這篇日記在別的地方被改過了（可能是另一個分頁）。"
            "請重新載入，避免蓋掉比較新的內容。",
        ) from exc
    if updated is None:
        raise HTTPException(404, f"找不到日記 #{entry_id}")
    return updated


@router.delete("/{entry_id}", status_code=204)
def delete_entry(entry_id: int) -> None:
    if not storage.delete_entry(entry_id):
        raise HTTPException(404, f"找不到日記 #{entry_id}")
