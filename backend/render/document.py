"""Normalise an ``Entry`` + its template into one structure both renderers use.

Answer values are stored loosely (whatever kind the field is), so this module
is the single place that knows how to read each kind. The HTML generator and
the SVG card generator both consume :class:`RenderedDoc`, which keeps them
from drifting apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from backend.models import Entry, FieldKind, JournalTemplate, TemplateField
from backend.richtext import Run, to_plain, to_runs

WEEKDAYS_ZH = ["一", "二", "三", "四", "五", "六", "日"]


@dataclass
class Chip:
    label: str
    selected: bool


@dataclass
class RenderedField:
    id: str
    label: str
    kind: FieldKind
    color: str
    chips: list[Chip] = field(default_factory=list)
    #: Each entry is one visual line, already flattened into colour runs.
    lines: list[list[Run]] = field(default_factory=list)
    #: ``True`` for LIST fields, so renderers can number them.
    numbered: bool = False
    plain: str = ""
    #: ``"ai"`` when the text was written by an assistant on the author's
    #: behalf (``entry put --author=ai``). The label already says 「AI 整理」
    #: so every layout shows it; this is for renderers that want to do more.
    author: str = "user"

    @property
    def is_empty(self) -> bool:
        """Was this question left unanswered?

        A tick question always carries its full row of chips — that is how the
        unpicked options get drawn next to the picked one — so "has chips" says
        nothing about whether it was answered. Only a selection does.
        """
        if self.chips:
            return not any(c.selected for c in self.chips)
        return not any(
            any(r.text.strip() for r in line) for line in self.lines
        )


@dataclass
class RenderedSection:
    id: str
    title: str
    color: str
    icon: str | None
    fields: list[RenderedField] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return all(f.is_empty for f in self.fields)


@dataclass
class RenderedDoc:
    entry_id: int
    title: str
    entry_date: date
    date_display: str
    weekday: str
    template_name: str
    theme: str
    layout: str
    sections: list[RenderedSection]
    closing_lines: list[list[Run]]
    word_count: int
    palette: list[str]
    #: What the closing block is called in this question set — "給主的話" for
    #: the devotional sets, something else for the ones that are not.
    closing_label: str = "給主的話"

    @property
    def has_closing(self) -> bool:
        return any(any(r.text.strip() for r in line) for line in self.closing_lines)

    def to_plain_text(self) -> str:
        """A compact text digest — this is what gets sent to Claude."""
        parts = [f"{self.date_display}（週{self.weekday}）"]
        if self.title:
            parts.append(self.title)
        for section in self.sections:
            if section.is_empty:
                continue
            parts.append(f"\n## {section.title}")
            for f in section.fields:
                if f.is_empty:
                    continue
                if f.chips:
                    picked = "、".join(c.label for c in f.chips if c.selected)
                    parts.append(f"- {f.label}：{picked}")
                else:
                    parts.append(f"- {f.label}：")
                    for line in f.lines:
                        text = "".join(r.text for r in line).strip()
                        if text:
                            parts.append(f"    {text}")
        if self.has_closing:
            parts.append(f"\n## {self.closing_label}")
            for line in self.closing_lines:
                text = "".join(r.text for r in line).strip()
                if text:
                    parts.append(text)
        return "\n".join(parts)


def _split_lines(runs: list[Run]) -> list[list[Run]]:
    """Split a run list on newlines into per-line run lists."""
    lines: list[list[Run]] = [[]]
    for run in runs:
        if "\n" not in run.text:
            lines[-1].append(run)
            continue
        chunks = run.text.split("\n")
        for i, chunk in enumerate(chunks):
            if i:
                lines.append([])
            if chunk:
                lines[-1].append(Run(chunk, run.color, run.bold, run.italic))
    return [ln for ln in lines if ln] or [[]]


def _fill_runs(
    pattern: str, values: list[str], color: str
) -> list[Run]:
    """Weave ``values`` into ``pattern``'s ``{}`` holes as coloured, bold runs."""
    runs: list[Run] = []
    parts = pattern.split("{}")
    for i, part in enumerate(parts):
        if part:
            runs.append(Run(part))
        if i < len(parts) - 1:
            value = values[i] if i < len(values) else ""
            runs.append(Run(value or "＿＿＿＿", color, bold=bool(value)))
    return runs


def _render_field(
    tf: TemplateField, raw_value: object, color: str
) -> RenderedField:
    rendered = RenderedField(
        id=tf.id, label=tf.label, kind=tf.kind, color=color
    )

    if tf.kind in (FieldKind.CHOICE, FieldKind.SCALE):
        picked = raw_value if isinstance(raw_value, str) else ""
        rendered.chips = [
            Chip(label=o.label, selected=o.id == picked) for o in tf.options
        ]
        rendered.plain = next(
            (o.label for o in tf.options if o.id == picked), ""
        )

    elif tf.kind is FieldKind.MULTI_CHOICE:
        picked_ids = set(raw_value) if isinstance(raw_value, list) else set()
        rendered.chips = [
            Chip(label=o.label, selected=o.id in picked_ids) for o in tf.options
        ]
        rendered.plain = "、".join(
            o.label for o in tf.options if o.id in picked_ids
        )

    elif tf.kind is FieldKind.SHORT_TEXT:
        text = raw_value if isinstance(raw_value, str) else ""
        rendered.lines = [[Run(text, color)]] if text else []
        rendered.plain = text

    elif tf.kind is FieldKind.FILL:
        values = [str(v) for v in raw_value] if isinstance(raw_value, list) else []
        runs = _fill_runs(tf.pattern or "{}", values, color)
        rendered.lines = _split_lines(runs) if any(values) else []
        rendered.plain = "".join(r.text for r in runs) if any(values) else ""

    elif tf.kind is FieldKind.LIST:
        items = raw_value if isinstance(raw_value, list) else []
        rendered.numbered = True
        for item in items:
            runs = to_runs(str(item), color)
            if any(r.text.strip() for r in runs):
                rendered.lines.append(runs)
        rendered.plain = "\n".join(
            "".join(r.text for r in line) for line in rendered.lines
        )

    else:  # TEXT
        runs = to_runs(str(raw_value or ""), color)
        rendered.lines = [
            ln for ln in _split_lines(runs) if any(r.text.strip() for r in ln)
        ]
        rendered.plain = to_plain(str(raw_value or ""))

    return rendered


#: What an assistant-written field is labelled, and what the author's own
#: words are called next to it. Every layout prints field labels, so this is
#: enough for the mark to show on the page, the card and the plain text.
AI_LABEL = "（AI 整理）"
SOURCE_LABEL = "作者原文"
SOURCE_COLOR = "#6b675e"


def _source_field(field_id: str, text: str) -> RenderedField:
    rendered = RenderedField(id=f"{field_id}__source", label=SOURCE_LABEL, kind=FieldKind.TEXT, color=SOURCE_COLOR)
    runs = [Run(text, SOURCE_COLOR)]
    rendered.lines = [ln for ln in _split_lines(runs) if any(r.text.strip() for r in ln)]
    rendered.plain = text
    return rendered


def build_document(
    entry: Entry, template: JournalTemplate, *, drop_empty: bool = True
) -> RenderedDoc:
    sections: list[RenderedSection] = []
    palette: list[str] = []
    marks = entry.provenance.get("fields", {}) if isinstance(entry.provenance, dict) else {}
    marks = marks if isinstance(marks, dict) else {}
    ai_written = False

    for ts in template.sections:
        rs = RenderedSection(
            id=ts.id, title=ts.title, color=ts.color, icon=ts.icon
        )
        for tf in ts.fields:
            color = entry.field_colors.get(tf.id) or tf.color or ts.color
            rf = _render_field(tf, entry.answers.get(tf.id), color)
            if drop_empty and rf.is_empty:
                continue
            mark = marks.get(tf.id)
            if isinstance(mark, dict) and mark.get("author") == "ai":
                # Polished by an assistant: say so on the page, and keep the
                # author's own words right under it.
                rf.label, rf.author, ai_written = rf.label + AI_LABEL, "ai", True
                rs.fields.append(rf)
                if str(mark.get("source") or "").strip():
                    rs.fields.append(_source_field(tf.id, str(mark["source"]).strip()))
            else:
                rs.fields.append(rf)
            if color not in palette:
                palette.append(color)
        if not (drop_empty and rs.is_empty):
            sections.append(rs)
        if ts.color not in palette:
            palette.append(ts.color)

    source_text = str(entry.provenance.get("source_text") or "").strip() if isinstance(entry.provenance, dict) else ""
    closing_mark = marks.get("closing")
    closing_ai = isinstance(closing_mark, dict) and closing_mark.get("author") == "ai"
    if source_text and (ai_written or closing_ai):
        sections.append(RenderedSection(id="source", title=SOURCE_LABEL, color=SOURCE_COLOR, icon="✎",
                                        fields=[_source_field("entry", source_text)]))

    closing_runs = to_runs(entry.closing, "#22252a")
    closing_lines = [
        ln for ln in _split_lines(closing_runs) if any(r.text.strip() for r in ln)
    ]

    body = "\n".join(
        f.plain for s in sections for f in s.fields
    ) + "\n" + "\n".join("".join(r.text for r in ln) for ln in closing_lines)

    d = entry.entry_date
    return RenderedDoc(
        entry_id=entry.id,
        title=entry.title.strip(),
        entry_date=d,
        date_display=f"{d.year}．{d.month:02d}．{d.day:02d}",
        weekday=WEEKDAYS_ZH[d.weekday()],
        template_name=template.name,
        theme=entry.theme,
        layout=entry.layout,
        sections=sections,
        closing_lines=closing_lines,
        word_count=len([c for c in body if not c.isspace()]),
        palette=palette,
        closing_label=(template.closing_label or "給主的話") + (AI_LABEL if closing_ai else ""),
    )
