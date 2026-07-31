"""CRUD for journal entries."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app import storage
from app.models import Entry, EntryCreate, EntryUpdate
from app.richtext import sanitize
from app.services import (
    require_entry,
    require_template,
    sanitize_answers,
    sanitize_field_colors,
)

router = APIRouter(prefix="/api/entries", tags=["entries"])


@router.get("", response_model=list[Entry])
def list_entries(
    limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)
) -> list[Entry]:
    return storage.list_entries(limit=limit, offset=offset)


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


@router.patch("/{entry_id}", response_model=Entry)
def update_entry(entry_id: int, payload: EntryUpdate) -> Entry:
    existing, _ = require_entry(entry_id)
    template = require_template(payload.template_id or existing.template_id)

    updates: dict[str, object] = {}
    if payload.answers is not None:
        updates["answers"] = sanitize_answers(template, payload.answers)
    if payload.field_colors is not None:
        updates["field_colors"] = sanitize_field_colors(payload.field_colors)
    if payload.closing is not None:
        updates["closing"] = sanitize(payload.closing)

    updated = storage.update_entry(entry_id, payload.model_copy(update=updates))
    if updated is None:
        raise HTTPException(404, f"找不到日記 #{entry_id}")
    return updated


@router.delete("/{entry_id}", status_code=204)
def delete_entry(entry_id: int) -> None:
    if not storage.delete_entry(entry_id):
        raise HTTPException(404, f"找不到日記 #{entry_id}")
