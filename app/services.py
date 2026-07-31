"""Glue between the API layer and the renderers: validation, sanitising, loading."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app import storage
from app.models import Entry, FieldKind, JournalTemplate
from app.richtext import normalize_color, sanitize
from app.template_registry import get_template

MAX_LIST_ROWS = 40
MAX_TEXT_CHARS = 20_000


def sanitize_answers(
    template: JournalTemplate, answers: dict[str, Any]
) -> dict[str, Any]:
    """Coerce every answer to the shape its field expects, and strip unsafe HTML.

    Unknown field ids are dropped rather than stored — that keeps a renamed
    template from silently accumulating orphaned answers.
    """
    fields = template.field_map()
    clean: dict[str, Any] = {}

    for field_id, value in answers.items():
        tf = fields.get(field_id)
        if tf is None:
            continue

        if tf.kind in (FieldKind.CHOICE, FieldKind.SCALE):
            valid = {o.id for o in tf.options}
            if isinstance(value, str) and value in valid:
                clean[field_id] = value

        elif tf.kind is FieldKind.MULTI_CHOICE:
            valid = {o.id for o in tf.options}
            if isinstance(value, list):
                clean[field_id] = [v for v in value if v in valid]

        elif tf.kind is FieldKind.SHORT_TEXT:
            if isinstance(value, str):
                clean[field_id] = value.strip()[:300]

        elif tf.kind is FieldKind.FILL:
            blanks = (tf.pattern or "").count("{}")
            if isinstance(value, list):
                clean[field_id] = [
                    str(v).strip()[:300] for v in value[: max(blanks, 1)]
                ]

        elif tf.kind is FieldKind.LIST:
            if isinstance(value, list):
                clean[field_id] = [
                    sanitize(str(v))[:MAX_TEXT_CHARS] for v in value[:MAX_LIST_ROWS]
                ]

        else:  # TEXT
            if isinstance(value, str):
                clean[field_id] = sanitize(value)[:MAX_TEXT_CHARS]

    return clean


def sanitize_field_colors(colors: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for field_id, raw in colors.items():
        normalized = normalize_color(raw)
        if normalized:
            out[str(field_id)[:64]] = normalized
    return out


def require_template(template_id: str) -> JournalTemplate:
    template = get_template(template_id)
    if template is None:
        raise HTTPException(404, f"找不到範本：{template_id}")
    return template


def require_entry(entry_id: int) -> tuple[Entry, JournalTemplate]:
    entry = storage.get_entry(entry_id)
    if entry is None:
        raise HTTPException(404, f"找不到日記 #{entry_id}")
    return entry, require_template(entry.template_id)
