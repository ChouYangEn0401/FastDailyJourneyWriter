"""Glue between the API layer and the renderers: validation, sanitising, loading."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app import storage
from app.models import (
    Entry,
    FieldKind,
    JournalTemplate,
    TemplateField,
    TemplateSection,
)
from app.richtext import normalize_color, sanitize
from app.template_registry import get_template

MAX_LIST_ROWS = 40
MAX_TEXT_CHARS = 20_000


def _sanitize_unknown(value: Any) -> Any | None:
    """Sanitise an answer whose field is no longer in the template.

    The field's kind is unknown here, so only the two shapes the editor can
    produce are preserved: one rich-text blob, or a list of them.
    """
    if isinstance(value, str):
        cleaned = sanitize(value)[:MAX_TEXT_CHARS]
        return cleaned or None
    if isinstance(value, list):
        items = [
            sanitize(str(v))[:MAX_TEXT_CHARS]
            for v in value[:MAX_LIST_ROWS]
            if isinstance(v, (str, int, float))
        ]
        items = [i for i in items if i]
        return items or None
    return None


def orphan_answers(
    template: JournalTemplate, answers: dict[str, Any]
) -> dict[str, Any]:
    """Answers stored on the entry that this template has no field for."""
    known = set(template.field_map())
    return {k: v for k, v in answers.items() if k not in known}


def sanitize_answers(
    template: JournalTemplate,
    answers: dict[str, Any],
    *,
    keep_extra: bool = True,
) -> dict[str, Any]:
    """Coerce every answer to the shape its field expects, and strip unsafe HTML.

    Answers whose field is not in this template are **kept**, not dropped.
    Switching an entry to a different question set must never destroy writing:
    the other template's answers stay in storage (sanitised as plain rich
    text) so they can be shown, recovered or carried back. Only an explicit
    delete removes anything.
    """
    fields = template.field_map()
    clean: dict[str, Any] = {}

    for field_id, value in answers.items():
        tf = fields.get(field_id)
        if tf is None:
            if keep_extra:
                carried = _sanitize_unknown(value)
                if carried is not None:
                    clean[field_id] = carried
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


def recovery_template(entry: Entry) -> JournalTemplate:
    """A stand-in for a question set that no longer exists.

    Deleting a question set must never make the entries written with it
    unreadable. When the original is gone, every stored answer is shown as
    plain text under one section, so the writing can still be read, exported
    and copied out.
    """
    fields = [
        TemplateField(
            id=field_id,
            label=field_id,
            kind=FieldKind.LIST if isinstance(value, list) else FieldKind.TEXT,
        )
        for field_id, value in entry.answers.items()
    ]
    return JournalTemplate(
        id=entry.template_id,
        name=f"{entry.template_id}（題組已刪除）",
        description="原本的題組已經不在了，以下是這篇保留下來的內容。",
        sections=[
            TemplateSection(
                id="recovered", title="保留下來的內容", color="#6b675e", fields=fields
            )
        ],
    )


def require_entry(entry_id: int) -> tuple[Entry, JournalTemplate]:
    entry = storage.get_entry(entry_id)
    if entry is None:
        raise HTTPException(404, f"找不到日記 #{entry_id}")
    template = get_template(entry.template_id)
    return entry, template or recovery_template(entry)


def entries_using_template(template_id: str) -> int:
    return sum(
        1 for e in storage.list_entries(limit=10_000) if e.template_id == template_id
    )
