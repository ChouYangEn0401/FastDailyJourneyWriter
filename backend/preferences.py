"""Personal setup, persisted to ``data/preferences.json``.

Kept deliberately small and human-readable: it is one file you can back up,
edit by hand, or copy to another machine to bring your setup with you.
"""

from __future__ import annotations

import json
import logging

from backend.config import settings
from backend.models import PenColor, Preferences
from backend.richtext import normalize_color

log = logging.getLogger(__name__)

#: The palette a new install starts with — the four pens a paper journal tends
#: to settle into, plus two spares. Entirely replaceable: add your own, delete
#: any of these.
DEFAULT_PALETTE = [
    PenColor(hex="#22252a", name="墨黑"),
    PenColor(hex="#c8322c", name="硃紅"),
    PenColor(hex="#1f7a4d", name="松綠"),
    PenColor(hex="#2456b8", name="靛藍"),
    PenColor(hex="#8a5fbf", name="紫"),
    PenColor(hex="#c98a1e", name="赭黃"),
]

MAX_PALETTE = 24


def _path():
    return settings.data_dir / "preferences.json"


def load() -> Preferences:
    path = _path()
    if not path.exists():
        return Preferences(palette=list(DEFAULT_PALETTE))
    try:
        prefs = Preferences.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - a corrupt file must not block writing
        log.warning("preferences.json unreadable (%s); using defaults", exc)
        return Preferences(palette=list(DEFAULT_PALETTE))
    # An empty palette would leave the editor with no pens at all.
    if not prefs.palette:
        prefs = prefs.model_copy(update={"palette": list(DEFAULT_PALETTE)})
    return prefs


def save(prefs: Preferences) -> Preferences:
    clean: list[PenColor] = []
    seen: set[str] = set()
    for pen in prefs.palette[:MAX_PALETTE]:
        hex_value = normalize_color(pen.hex)
        if not hex_value or hex_value in seen:
            continue
        seen.add(hex_value)
        clean.append(PenColor(hex=hex_value, name=pen.name.strip()[:24]))

    prefs = prefs.model_copy(
        update={"palette": clean or list(DEFAULT_PALETTE)}
    )
    _path().write_text(
        json.dumps(prefs.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return prefs


def reset_palette() -> Preferences:
    return save(load().model_copy(update={"palette": list(DEFAULT_PALETTE)}))
