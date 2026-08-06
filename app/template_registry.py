"""Question sets, loaded from ``data/templates/*.json``.

Nothing here is hard-coded. The shipped defaults are JSON files under
``content/templates/`` that :mod:`app.seed_manager` copies into
``data/templates/`` on first run; from then on they are ordinary files the
user can edit, duplicate or delete. Anything else dropped into that directory
shows up alongside them.

A template file is a :class:`~app.models.JournalTemplate` — ``order`` places it
in the list and ``group`` decides which heading it sits under.
"""

from __future__ import annotations

import json
import logging

from app.config import settings
from app.models import JournalTemplate

log = logging.getLogger(__name__)


def _load_dir() -> list[JournalTemplate]:
    templates: list[tuple[int, str, JournalTemplate]] = []
    for path in sorted(settings.templates_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw.setdefault("id", path.stem)
            tpl = JournalTemplate.model_validate(raw)
            templates.append((tpl.order, path.stem, tpl))
        except Exception as exc:  # noqa: BLE001 - one bad file must not kill boot
            log.warning("Skipping invalid template %s: %s", path.name, exc)
    templates.sort(key=lambda item: (item[0], item[1]))
    return [t for _, _, t in templates]


def all_templates() -> list[JournalTemplate]:
    return _load_dir()


def get_template(template_id: str) -> JournalTemplate | None:
    return next((t for t in all_templates() if t.id == template_id), None)


def save_template(template: JournalTemplate) -> JournalTemplate:
    path = settings.templates_dir / f"{template.id}.json"
    payload = template.model_dump(mode="json")
    payload.pop("source", None)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return template


def delete_template(template_id: str) -> bool:
    path = settings.templates_dir / f"{template_id}.json"
    if not path.exists():
        return False
    path.unlink()
    return True
