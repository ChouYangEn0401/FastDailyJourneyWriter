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


class Entry(EntryBase):
    id: int
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------
# AI request/response payloads
# --------------------------------------------------------------------------


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
