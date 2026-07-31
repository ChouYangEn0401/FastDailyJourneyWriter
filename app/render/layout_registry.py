"""Page designs, loaded from ``data/layouts/``.

A layout is two files sharing a stem:

* ``<id>.html.j2`` — the whole page. It receives ``doc`` (the entry, already
  normalised), ``t`` (the theme's colour tokens), ``gift_cover`` and
  ``gift_message``, plus a ``runs`` filter that renders colour-annotated text.
* ``<id>.json``    — name, description, tags, and which card ruling suits it.

Designs are finished before anyone writes a word, so exporting is pure
content-filling: no API key, no network, no waiting. Adding a design means
dropping two files into the directory.
"""

from __future__ import annotations

import json
import logging

from app.config import settings
from app.models import Layout

log = logging.getLogger(__name__)

FALLBACK_LAYOUT = "letter"
#: Files installed by the seeder; anything else in the directory is the
#: user's own. Kept in code because it is a fact about the shipped package,
#: not a design decision the user can edit.
SHIPPED_IDS = frozenset({"letter", "ledger", "manuscript", "postcard"})


def template_filename(layout_id: str) -> str:
    return f"{layout_id}.html.j2"


def _meta_path(layout_id: str):
    return settings.layouts_dir / f"{layout_id}.json"


def all_layouts() -> list[Layout]:
    layouts: list[Layout] = []
    for path in sorted(settings.layouts_dir.glob("*.html.j2")):
        # Files starting with "_" are shared partials (cover markup, tokens),
        # not designs you can pick.
        if path.name.startswith("_"):
            continue
        layout_id = path.name.removesuffix(".html.j2")
        meta: dict = {}
        meta_file = _meta_path(layout_id)
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                log.warning("Bad layout metadata %s: %s", meta_file.name, exc)
        meta["id"] = layout_id
        meta.setdefault("name", layout_id)
        meta["origin"] = "shipped" if layout_id in SHIPPED_IDS else "custom"
        try:
            layouts.append(Layout.model_validate(meta))
        except Exception as exc:  # noqa: BLE001
            log.warning("Skipping layout %s: %s", layout_id, exc)

    shipped_order = {name: i for i, name in enumerate(
        ["letter", "ledger", "manuscript", "postcard"]
    )}
    layouts.sort(key=lambda x: (shipped_order.get(x.id, 100), x.name))
    return layouts


def get_layout(layout_id: str | None) -> Layout | None:
    wanted = layout_id or FALLBACK_LAYOUT
    layouts = all_layouts()
    found = next((x for x in layouts if x.id == wanted), None)
    if found:
        return found
    return next((x for x in layouts if x.id == FALLBACK_LAYOUT), None) or (
        layouts[0] if layouts else None
    )


def save_layout(layout: Layout, html: str) -> Layout:
    settings.layouts_dir.mkdir(parents=True, exist_ok=True)
    (settings.layouts_dir / template_filename(layout.id)).write_text(
        html, encoding="utf-8"
    )
    payload = layout.model_dump(mode="json")
    payload.pop("origin", None)
    _meta_path(layout.id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return layout


def read_layout_html(layout_id: str) -> str:
    return (settings.layouts_dir / template_filename(layout_id)).read_text(
        encoding="utf-8"
    )


def delete_layout(layout_id: str) -> bool:
    html = settings.layouts_dir / template_filename(layout_id)
    if not html.exists():
        return False
    html.unlink()
    _meta_path(layout_id).unlink(missing_ok=True)
    return True
