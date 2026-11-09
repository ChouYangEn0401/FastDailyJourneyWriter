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


# --------------------------------------------------------------------------
# Every setting, by name — what the command line's ``settings`` verbs read
# --------------------------------------------------------------------------

#: ``{key: (what it is, how to write the value)}`` for every field of
#: :class:`Preferences`. The editor writes the same file through
#: ``PUT /api/preferences``; this table is what makes each one reachable
#: from ``python -m backend.cli settings set --key=… --value=…``. Keep it in
#: step with the model: the test fails when a field is missing here.
FIELDS: dict[str, tuple[str, str]] = {
    "palette": ("編輯器上方那一排墨水色", "JSON 清單：[{\"hex\": \"#22252a\", \"name\": \"墨黑\"}, …]；default＝內建六色"),
    "template_id": ("預設題組：開編輯器、新的一天先用哪一個", "題組 id（templates 看全部），空字串＝不指定"),
    "layout": ("預設輸出版型", "版型 id（layouts 看全部），空字串＝不指定"),
    "theme": ("預設紙張顏色", "letterpress、notebook、linen、dawn、midnight，空字串＝不指定"),
    "card_paper": ("卡片的紙", "ruled、grid、plain、dotted，空字串＝跟版型"),
    "card_width": ("卡片寬度（px）", "480–2400 的整數"),
    "image_style": ("繪圖 prompt 的風格", "一個英文字，例 watercolor"),
    "use_as_default": ("新日記要不要套用上面的預設", "true／false"),
    "day_start_hour": ("幾點以前「今天」還算昨天（熬夜寫的人用）", "0–23 的整數，0＝午夜換日"),
    "export_dir": ("export 寫到哪個資料夾", "資料夾路徑，空字串＝日記資料夾的 exports/"),
    "preset": ("這份安裝用的起始題組（setup init 寫的）", "generic、devotional，空字串＝沒跑過"),
    "suggest_faith": ("templates suggest 怎麼對待信仰類題組", "auto（字裡沒提信仰就放後面）、prefer（一視同仁）、never（不列）"),
}

#: Values that mean "not set" for the optional ids.
_UNSET = ("", None, "null", "none")


def describe() -> list[dict]:
    """Every setting with its current value, default and meaning — for ``settings``."""
    prefs, blank = load(), Preferences()
    return [
        {"key": key, "value": getattr(prefs, key), "default": getattr(blank, key) if key != "palette" else
         [p.model_dump() for p in DEFAULT_PALETTE], "what": what, "how": how}
        for key, (what, how) in FIELDS.items()
    ]


def set_value(key: str, raw: str) -> Preferences:
    """Set one setting from text. ``raw`` may be JSON (lists, numbers, true/false) or a plain word;
    ``default`` puts the shipped value back. Raises ``ValueError`` with a sentence when the value is not acceptable."""
    if key not in FIELDS:
        raise ValueError(f"沒有這個設定：{key}（有：{'、'.join(FIELDS)}）")
    if raw == "default":
        value = [p.model_dump() for p in DEFAULT_PALETTE] if key == "palette" else getattr(Preferences(), key)
    else:
        try:
            value = json.loads(raw)
        except ValueError:
            value = raw
        if key in ("template_id", "layout", "theme", "card_paper") and value in _UNSET:
            value = None
        if key == "card_width" and isinstance(value, int) and not 480 <= value <= 2400:
            raise ValueError("card_width 要在 480 到 2400 之間")
    data = {**load().model_dump(), key: value}
    try:
        prefs = Preferences.model_validate(data)
    except Exception as exc:  # noqa: BLE001 - turned into one sentence for the person
        lines = [ln.strip() for ln in str(exc).splitlines() if ln.strip()]
        hint = next((ln for ln in lines if ln.startswith(("Input", "Value", "Assertion", "Field"))), lines[-1] if lines else str(exc))
        raise ValueError(f"{key} 的值不對：{hint}（{FIELDS[key][1]}）") from exc
    if key == "palette" and not prefs.palette:
        raise ValueError("palette 不能是空的")
    return save(prefs)
