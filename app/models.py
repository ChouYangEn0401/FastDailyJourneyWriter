"""Pydantic schemas shared by the API, the storage layer and the renderers."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------


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
    #: What the free-text block at the end of the entry is called. The
    #: devotional sets keep "給主的話"; the rest name it something that fits.
    closing_label: str = "給主的話"
    closing_hint: str = "今天想對主說的一段話。也可以換色。"
    closing_placeholder: str = "親愛的主耶穌，今天…"
    sections: list[TemplateSection] = Field(default_factory=list)

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

    @field_validator("theme")
    @classmethod
    def _known_theme(cls, v: str) -> str:
        from app.render.themes import THEMES

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
