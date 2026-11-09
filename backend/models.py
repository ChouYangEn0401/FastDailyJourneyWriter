"""Pydantic schemas shared by the API, the storage layer and the renderers."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------


#: Classification of a question set (``JournalTemplate.structure`` /
#: ``.reflection`` / ``.flow``). The ids are ASCII so other programs (the
#: Telegram side) can filter on them; the labels are what people see. The
#: order of ``REFLECTIONS`` is a ladder: each level includes the ones before.
STRUCTURES: dict[str, str] = {
    "one-part": "一段式",
    "three-part": "三段式",
    "n-part": "多段式",
}
REFLECTIONS: dict[str, str] = {
    "none": "只記錄",
    "reflection": "有反思（不談信仰）",
    "devotional": "有信仰的反思",
    "prayer": "有禱告／代禱",
}
FLOW_TOKENS: dict[str, str] = {
    "checkin": "與主同行的打卡",
    "events": "發生的事",
    "feelings": "感受",
    "worries": "擔心的事",
    "work": "工作與專案",
    "decision": "一個決定",
    "identity": "想成為的人",
    "review": "一段時間的回顧",
    "scripture": "經文",
    "reflection": "反思／學到什麼",
    "confession": "認罪／對不起",
    "gratitude": "感恩",
    "prayer": "禱告／代禱",
    "trust": "信靠",
    "people": "人",
    "quote": "別人說過的話",
    "plan": "下一步／明天",
}


class FieldKind(str, Enum):
    """How a field is rendered in the editor.

    ``choice`` / ``multi_choice`` / ``scale`` are the "tick a box and you're
    done" kinds — they need no typing at all. ``fill`` is the fill-in-the-blank
    kind: a sentence with ``{}`` holes the UI turns into inline inputs.
    """

    CHOICE = "choice"          # one option, rendered as radio pills
    MULTI_CHOICE = "multi_choice"  # several options, rendered as checkboxes
    SCALE = "scale"            # ordered options, rendered as a segmented bar
    SHORT_TEXT = "short_text"  # single line, plain
    FILL = "fill"              # sentence with {} blanks -> inline inputs
    TEXT = "text"              # multi-line rich text (colour supported)
    LIST = "list"              # repeating rich-text lines (感恩 / 代禱 …)


class FieldOption(BaseModel):
    id: str
    label: str


class TemplateField(BaseModel):
    id: str
    label: str
    kind: FieldKind = FieldKind.TEXT
    options: list[FieldOption] = Field(default_factory=list)
    #: For ``FILL`` — e.g. "今天讀了 {} ，最觸動我的是 {}".
    pattern: str | None = None
    placeholder: str | None = None
    #: For ``LIST`` — how many blank rows the editor starts with.
    min_rows: int = 2
    #: Suggested colour for answers to this field (hex). The user can override.
    color: str | None = None
    hint: str | None = None
    #: How an assistant should fill this question from free-form writing:
    #: what to pull out, and when to leave it blank. Never shown in the
    #: editor or the export — it is for whoever fills the set on your behalf
    #: (see ``skills/diary-templates/SKILL.md``).
    ai_hint: str | None = None


class TemplateSection(BaseModel):
    id: str
    title: str
    #: Accent colour for the whole section — this is what reproduces the
    #: "different colour per part" style.
    color: str = "#2f3437"
    icon: str | None = None
    fields: list[TemplateField] = Field(default_factory=list)


class JournalTemplate(BaseModel):
    id: str
    name: str
    description: str = ""
    default_theme: str = "letterpress"
    default_layout: str = "letter"
    #: Heading this question set sits under in the picker. Sets sharing a
    #: group are listed together; an empty group lands in a trailing "其他".
    group: str = ""
    #: Position in the list. Lower comes first; ties break on file name.
    order: int = 1000
    #: The situation this set is for, in one sentence ("很忙、但不想斷掉的日子").
    #: ``description`` is the short line under the name; this is what someone
    #: (or an assistant) reads when deciding *which* set to open today.
    when: str = ""
    #: Roughly how many minutes one honest pass takes. ``0`` = not stated.
    minutes: int = 0
    #: Moods or states this set fits ("疲累", "焦慮", "平靜"…). Free words.
    moods: list[str] = Field(default_factory=list)
    #: Short labels for filtering ("靈修", "勾選為主", "經文", "工作"…).
    tags: list[str] = Field(default_factory=list)
    #: How the set is built — one of :data:`STRUCTURES`. Left blank, it is
    #: derived from the number of sections (1 → ``one-part``, 3 →
    #: ``three-part``, anything else → ``n-part``). Declared when the count
    #: would mislead (``jot`` has a machine-filled second section).
    structure: str = ""
    #: The deepest kind of looking-back the set asks for — one of
    #: :data:`REFLECTIONS`: ``none`` (just records), ``reflection`` (meaning,
    #: lessons, no faith), ``devotional`` (before God / with scripture),
    #: ``prayer`` (devotional and talks to God: prayer, intercession, lament).
    reflection: str = "none"
    #: What the set walks through, in order, as tokens from :data:`FLOW_TOKENS`
    #: — e.g. ``["events", "scripture", "reflection", "prayer"]``. Each token
    #: once, at its first appearance. This is what the picker and the
    #: suggestion rule read; see ``backend/taxonomy.py``.
    flow: list[str] = Field(default_factory=list)
    #: What the free-text block at the end of the entry is called. The
    #: devotional sets keep "給主的話"; the rest name it something that fits.
    closing_label: str = "給主的話"
    closing_hint: str = "今天想對主說的一段話。也可以換色。"
    closing_placeholder: str = "親愛的主耶穌，今天…"
    sections: list[TemplateSection] = Field(default_factory=list)

    @field_validator("structure")
    @classmethod
    def _known_structure(cls, v: str) -> str:
        if v and v not in STRUCTURES:
            raise ValueError(f"structure 只能是 {'、'.join(STRUCTURES)}（收到：{v}）")
        return v

    @field_validator("reflection")
    @classmethod
    def _known_reflection(cls, v: str) -> str:
        v = v or "none"
        if v not in REFLECTIONS:
            raise ValueError(f"reflection 只能是 {'、'.join(REFLECTIONS)}（收到：{v}）")
        return v

    @field_validator("flow")
    @classmethod
    def _known_flow(cls, v: list[str]) -> list[str]:
        unknown = [t for t in v if t not in FLOW_TOKENS]
        if unknown:
            raise ValueError(f"flow 裡有不認識的步驟：{'、'.join(unknown)}（可用：{'、'.join(FLOW_TOKENS)}）")
        return list(dict.fromkeys(v))

    @model_validator(mode="after")
    def _derive_structure(self) -> "JournalTemplate":
        if not self.structure:
            n = len(self.sections)
            self.structure = "one-part" if n == 1 else "three-part" if n == 3 else "n-part"
        return self

    def field_map(self) -> dict[str, TemplateField]:
        return {f.id: f for s in self.sections for f in s.fields}


class Layout(BaseModel):
    """A finished page design. Rendering an entry is pure content-filling."""

    id: str
    name: str
    description: str = ""
    #: Shown in the picker so you can tell the designs apart at a glance.
    tags: list[str] = Field(default_factory=list)
    default_theme: str = "letterpress"
    #: Paper ruling the notebook card should use with this design.
    card_paper: Literal["ruled", "grid", "plain", "dotted"] = "ruled"
    #: ``shipped`` designs came with the app, ``custom`` ones you (or the
    #: layout designer) added. Both live in ``data/layouts/`` and both are
    #: editable.
    origin: Literal["shipped", "custom"] = "custom"


# --------------------------------------------------------------------------
# Entries
# --------------------------------------------------------------------------


class EntryBase(BaseModel):
    entry_date: date
    title: str = ""
    template_id: str
    theme: str = "letterpress"
    #: Which page design to export with. Resolved against ``data/layouts/``.
    layout: str = "letter"
    #: ``{field_id: value}``. Value shape depends on the field kind:
    #: choice -> str | scale -> str | multi_choice -> list[str] |
    #: short_text -> str | fill -> list[str] | text -> html str |
    #: list -> list[html str]
    answers: dict[str, Any] = Field(default_factory=dict)
    #: Free-form closing prayer / letter, rich text.
    closing: str = ""
    #: Per-field colour overrides chosen in the editor: ``{field_id: hex}``.
    field_colors: dict[str, str] = Field(default_factory=dict)
    #: Who wrote what, when it was not the author. ``{"fields": {field_id:
    #: {"author": "ai", "at": iso, "source": "原文"}}, "source_text": "原文"}``.
    #: Only the command line writes it (``entry put --author=ai``); the
    #: renderers label those fields 「AI 整理」 and print the author's original
    #: next to them, so polished text is never mistaken for the author's own.
    #: ``closing`` is a field id here too. Empty for everything the author
    #: wrote.
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("theme")
    @classmethod
    def _known_theme(cls, v: str) -> str:
        from backend.render.themes import THEMES

        return v if v in THEMES else "letterpress"


class EntryCreate(EntryBase):
    pass


class EntryUpdate(BaseModel):
    entry_date: date | None = None
    title: str | None = None
    template_id: str | None = None
    theme: str | None = None
    layout: str | None = None
    answers: dict[str, Any] | None = None
    closing: str | None = None
    field_colors: dict[str, str] | None = None
    provenance: dict[str, Any] | None = None
    #: What the client believes it last read. When supplied and no longer
    #: current, the write is refused instead of clobbering someone else's
    #: newer text.
    expected_updated_at: datetime | None = None


class EntryRevision(BaseModel):
    """A past version of an entry, kept so a bad save can be undone."""

    id: int
    entry_id: int
    entry_date: date
    title: str
    template_id: str
    char_count: int
    reason: str
    created_at: datetime


class TrashItem(BaseModel):
    """A deleted entry that can still be put back."""

    revision_id: int
    entry_id: int
    entry_date: date
    title: str
    char_count: int
    deleted_at: datetime


class BackupInfo(BaseModel):
    name: str
    size_bytes: int
    created_at: datetime
    #: Snapshots taken automatically are pruned; ones you asked for are kept.
    automatic: bool = True


class Entry(EntryBase):
    id: int
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------
# AI request/response payloads
# --------------------------------------------------------------------------


class PenColor(BaseModel):
    """One swatch in the palette bar."""

    hex: str
    name: str = ""


class Preferences(BaseModel):
    """Personal setup, stored in ``data/preferences.json``.

    Everyone settles into one or two question sets, a layout and a handful of
    pen colours. This is where that settles, so it survives restarts and can
    be carried to another machine as a single file.
    """

    palette: list[PenColor] = Field(default_factory=list)
    template_id: str | None = None
    layout: str | None = None
    theme: str | None = None
    card_paper: str | None = None
    card_width: int = 1080
    image_style: str = "watercolor"
    #: Applied to new entries when set.
    use_as_default: bool = True
    #: Before this hour, "today" still means yesterday (0 = midnight). For
    #: people who write after midnight: ``entry put --date=today`` at 01:30
    #: with ``day_start_hour`` 4 lands on the day that is ending.
    day_start_hour: int = 0
    #: Where ``export`` writes files; empty = ``<data dir>/exports``.
    export_dir: str = ""
    #: Which starter set this install was set up with (``setup init``):
    #: ``generic`` or ``devotional``. Empty = never run (the shipped default
    #: installs every set, which is what ``devotional`` means).
    preset: str = ""
    #: How ``templates suggest`` treats faith-oriented sets when the text
    #: does not mention faith: ``auto`` (set them back), ``prefer`` (treat
    #: them like any other), ``never`` (leave them out).
    suggest_faith: Literal["auto", "prefer", "never"] = "auto"

    @field_validator("day_start_hour")
    @classmethod
    def _hour(cls, v: int) -> int:
        if not 0 <= v <= 23:
            raise ValueError("day_start_hour 要在 0 到 23 之間")
        return v

    @field_validator("preset")
    @classmethod
    def _preset(cls, v: str) -> str:
        if v and v not in ("generic", "devotional"):
            raise ValueError("preset 只能是 generic 或 devotional")
        return v


class ArtifactRequest(BaseModel):
    entry_id: int
    theme: str | None = None
    layout: str | None = None
    #: Wrap the journal in a cover that flips open — the "gift a journal" idea.
    gift_cover: bool = False
    gift_message: str = ""


class LayoutDesignRequest(BaseModel):
    """Design-time only. Produces a new layout file you then own forever."""

    name: str
    brief: str = ""
    #: Which existing design to start from.
    base_layout: str = "letter"
    #: Preview the new design against a real entry.
    entry_id: int | None = None


class CardRequest(BaseModel):
    entry_id: int
    theme: str | None = None
    layout: str | None = None
    #: Logical card size in CSS px; the browser rasterises at 1x/2x/3x.
    width: int = 1080
    #: ``auto`` grows the card to fit the content.
    height: int | Literal["auto"] = "auto"
    #: ``None`` takes the ruling the chosen layout was designed for.
    paper: Literal["ruled", "grid", "plain", "dotted"] | None = None


class ImagePromptRequest(BaseModel):
    entry_id: int
    style: str = "watercolor"
    language: Literal["zh", "en", "both"] = "both"


class ImagePromptResponse(BaseModel):
    prompt_en: str
    prompt_zh: str
    mood: str
    keywords: list[str]
    negative_prompt: str = ""
    source: Literal["claude", "fallback"] = "fallback"
