"""Entry -> a notebook-paper SVG card.

The output is one self-contained ``<svg>`` — no external images, no external
fonts, no scripts — so it can be dropped into a page, saved as ``.svg``, or
rasterised by the browser into a high-DPI PNG for sharing on LINE.

Vertical rhythm is snapped to the ruled-line grid, so the text genuinely sits
on the lines instead of floating near them.
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.sax.saxutils import escape as xml_escape

from app.models import Entry, JournalTemplate
from app.render.document import RenderedDoc, build_document
from app.render.textlayout import Piece, text_width, wrap_plain, wrap_runs
from app.render.themes import Theme, get_theme

PaperStyle = str  # "ruled" | "grid" | "plain" | "dotted"


def _fonts(stack: str) -> str:
    """SVG attributes can't carry raw double quotes."""
    return stack.replace('"', "'")


@dataclass
class _Geom:
    s: float          # scale factor relative to the 1080px design width
    width: float
    margin: float
    pad_x: float
    rule_top: float
    lh: float         # line height == ruled-line spacing

    @property
    def paper_x(self) -> float:
        return self.margin

    @property
    def paper_w(self) -> float:
        return self.width - 2 * self.margin

    @property
    def content_x(self) -> float:
        return self.paper_x + self.pad_x

    @property
    def content_w(self) -> float:
        return self.paper_w - 2 * self.pad_x


class _Builder:
    def __init__(self, g: _Geom, theme: Theme) -> None:
        self.g = g
        self.t = theme
        self.body: list[str] = []
        self.row = 0.0

    # -- geometry helpers ------------------------------------------------
    def baseline(self, row: float | None = None) -> float:
        r = self.row if row is None else row
        return self.g.margin + self.g.rule_top + r * self.g.lh - 11 * self.g.s

    def rule_y(self, row: float) -> float:
        return self.g.margin + self.g.rule_top + row * self.g.lh

    def advance(self, rows: float = 1.0) -> None:
        self.row += rows

    # -- primitives ------------------------------------------------------
    def line(
        self,
        pieces: list[Piece],
        *,
        x: float,
        size: float,
        family: str,
        color: str,
        weight: str = "400",
        letter_spacing: float = 0.0,
        opacity: float = 1.0,
        anchor: str = "start",
        row: float | None = None,
    ) -> None:
        if not pieces:
            return
        spans = []
        for p in pieces:
            attrs = ""
            if p.color and p.color != color:
                attrs += f' fill="{p.color}"'
            if p.bold:
                attrs += ' font-weight="600"'
            if p.italic:
                attrs += ' font-style="italic"'
            spans.append(f"<tspan{attrs}>{xml_escape(p.text)}</tspan>")
        ls = f' letter-spacing="{letter_spacing:.2f}"' if letter_spacing else ""
        op = f' opacity="{opacity}"' if opacity != 1.0 else ""
        anc = f' text-anchor="{anchor}"' if anchor != "start" else ""
        self.body.append(
            f'<text x="{x:.1f}" y="{self.baseline(row):.1f}" fill="{color}" '
            f'font-family="{family}" font-size="{size:.1f}" '
            f'font-weight="{weight}"{ls}{op}{anc}>{"".join(spans)}</text>'
        )

    def plain(self, text: str, **kw) -> None:
        if not text:
            return
        self.line([Piece(text)], **kw)

    def hairline(self, row: float, *, color: str, width: float = 1.0) -> None:
        y = self.rule_y(row) - self.g.lh * 0.55
        self.body.append(
            f'<line x1="{self.g.content_x:.1f}" y1="{y:.1f}" '
            f'x2="{self.g.content_x + self.g.content_w:.1f}" y2="{y:.1f}" '
            f'stroke="{color}" stroke-width="{width * self.g.s:.2f}"/>'
        )

    def rect(self, x, y, w, h, *, fill, rx=0.0, opacity=1.0) -> None:
        op = f' opacity="{opacity}"' if opacity != 1.0 else ""
        self.body.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="{rx:.1f}" fill="{fill}"{op}/>'
        )

    def circle(self, cx, cy, r, *, fill, opacity=1.0) -> None:
        op = f' opacity="{opacity}"' if opacity != 1.0 else ""
        self.body.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}"{op}/>'
        )


# --------------------------------------------------------------------------


def _render_chips(b: _Builder, labels: list[tuple[str, bool]], color: str) -> None:
    g, t = b.g, b.t
    body_font = _fonts(t.body_font)
    size = 25 * g.s
    pad = 20 * g.s
    gap = 11 * g.s
    h = 40 * g.s
    x = g.content_x
    top = b.rule_y(b.row) - g.lh + (g.lh - h) / 2 + 4 * g.s

    for label, selected in labels:
        w = text_width(label) * size + pad * 2
        if x + w > g.content_x + g.content_w and x > g.content_x:
            b.advance()
            x = g.content_x
            top = b.rule_y(b.row) - g.lh + (g.lh - h) / 2 + 4 * g.s
        if selected:
            b.rect(x, top, w, h, fill=color, rx=h / 2)
        else:
            b.rect(x, top, w, h, fill=t.ink, rx=h / 2, opacity=0.05)
        b.body.append(
            f'<text x="{x + w / 2:.1f}" y="{top + h / 2 + size * 0.36:.1f}" '
            f'text-anchor="middle" font-family="{body_font}" '
            f'font-size="{size:.1f}" font-weight="{"600" if selected else "400"}" '
            f'fill="{"#ffffff" if selected else t.ink_muted}">'
            f"{xml_escape(label)}</text>"
        )
        x += w + gap
    b.advance()


def _render_field(b: _Builder, f, section_color: str) -> None:
    g, t = b.g, b.t
    body_font = _fonts(t.body_font)
    indent = 26 * g.s
    x = g.content_x + indent
    avail_em = (g.content_w - indent) / (30 * g.s)

    # label
    b.plain(
        f.label,
        x=x,
        size=21 * g.s,
        family=body_font,
        color=t.ink_muted,
        letter_spacing=1.2 * g.s,
    )
    b.advance()

    if f.chips:
        _render_chips(b, [(c.label, c.selected) for c in f.chips], section_color)
        b.advance(0.35)
        return

    size = 30 * g.s
    if f.numbered:
        num_indent = 46 * g.s
        for i, runs in enumerate(f.lines, start=1):
            lines = wrap_runs(runs, avail_em - num_indent / size)
            cy = b.rule_y(b.row) - g.lh * 0.5 - 4 * g.s
            r = 15 * g.s
            b.circle(x + r, cy, r, fill=section_color, opacity=0.14)
            b.body.append(
                f'<text x="{x + r:.1f}" y="{cy + 7 * g.s:.1f}" text-anchor="middle" '
                f'font-family="{body_font}" font-size="{19 * g.s:.1f}" '
                f'font-weight="600" fill="{section_color}">{i}</text>'
            )
            for j, pieces in enumerate(lines):
                b.line(
                    pieces,
                    x=x + num_indent,
                    size=size,
                    family=body_font,
                    color=section_color,
                    row=b.row if j == 0 else b.row + j,
                )
            b.advance(len(lines))
    else:
        for runs in f.lines:
            for pieces in wrap_runs(runs, avail_em):
                b.line(
                    pieces, x=x, size=size, family=body_font, color=section_color
                )
                b.advance()

    b.advance(0.4)


def _render_body(b: _Builder, doc: RenderedDoc) -> None:
    g, t = b.g, b.t
    display = _fonts(t.display_font)
    body_font = _fonts(t.body_font)

    # ---- masthead ----
    b.plain(
        doc.template_name,
        x=g.content_x,
        size=20 * g.s,
        family=body_font,
        color=t.ink_muted,
        letter_spacing=3.4 * g.s,
    )
    b.advance(1.4)

    b.plain(
        doc.date_display,
        x=g.content_x,
        size=62 * g.s,
        family=display,
        color=t.ink,
        weight="600",
        letter_spacing=1.5 * g.s,
    )
    b.advance(1.5)

    meta = f"週{doc.weekday}　·　{doc.word_count} 字"
    b.plain(
        meta,
        x=g.content_x,
        size=22 * g.s,
        family=body_font,
        color=t.ink_muted,
        letter_spacing=1.4 * g.s,
    )
    b.advance()

    if doc.title:
        for pieces in wrap_plain(doc.title, g.content_w / (32 * g.s)):
            b.line(
                pieces,
                x=g.content_x,
                size=32 * g.s,
                family=display,
                color=t.ink,
                weight="500",
            )
            b.advance()

    b.advance(0.35)
    b.hairline(b.row, color=t.hairline, width=1.2)
    b.advance(0.9)

    # ---- sections ----
    for section in doc.sections:
        icon_size = 34 * g.s
        top = b.rule_y(b.row) - g.lh + (g.lh - icon_size) / 2 + 4 * g.s
        if section.icon:
            b.rect(
                g.content_x,
                top,
                icon_size,
                icon_size,
                fill=section.color,
                rx=9 * g.s,
            )
            b.body.append(
                f'<text x="{g.content_x + icon_size / 2:.1f}" '
                f'y="{top + icon_size / 2 + 8 * g.s:.1f}" text-anchor="middle" '
                f'font-family="{body_font}" font-size="{20 * g.s:.1f}" '
                f'fill="#ffffff">{xml_escape(section.icon)}</text>'
            )
        title_x = g.content_x + (icon_size + 14 * g.s if section.icon else 0)
        b.plain(
            section.title,
            x=title_x,
            size=31 * g.s,
            family=display,
            color=t.ink,
            weight="600",
        )
        b.advance(1.15)

        bar_top = b.rule_y(b.row) - g.lh
        for f in section.fields:
            _render_field(b, f, section.color)
        bar_bottom = b.rule_y(b.row) - g.lh * 0.9
        b.body.insert(
            0,
            f'<rect x="{g.content_x + 4 * g.s:.1f}" y="{bar_top:.1f}" '
            f'width="{2.5 * g.s:.1f}" height="{max(0.0, bar_bottom - bar_top):.1f}" '
            f'rx="{1.5 * g.s:.1f}" fill="{section.color}" opacity="0.35"/>',
        )
        b.advance(0.6)

    # ---- closing letter ----
    if doc.has_closing:
        b.advance(0.4)
        start = b.rule_y(b.row) - g.lh
        b.plain(
            "給主的話",
            x=g.content_x + 26 * g.s,
            size=21 * g.s,
            family=body_font,
            color=t.accent,
            letter_spacing=1.2 * g.s,
        )
        b.advance()
        size = 30 * g.s
        avail = (g.content_w - 26 * g.s) / size
        for runs in doc.closing_lines:
            for pieces in wrap_runs(runs, avail):
                b.line(
                    pieces,
                    x=g.content_x + 26 * g.s,
                    size=size,
                    family=display,
                    color=t.ink,
                )
                b.advance()
        end = b.rule_y(b.row) - g.lh * 0.9
        b.body.append(
            f'<rect x="{g.content_x:.1f}" y="{start:.1f}" width="{3.5 * g.s:.1f}" '
            f'height="{max(0.0, end - start):.1f}" rx="{2 * g.s:.1f}" '
            f'fill="{t.accent}"/>'
        )

    b.advance(0.8)


def _paper_pattern(paper: PaperStyle, g: _Geom, t: Theme, height: float) -> str:
    """Ruling drawn behind the text, aligned to the same grid the text uses."""
    if paper == "plain":
        return ""
    out: list[str] = []
    x1 = g.paper_x + g.pad_x * 0.45
    x2 = g.paper_x + g.paper_w - g.pad_x * 0.45
    sw = 1.1 * g.s

    if paper in ("ruled", "grid"):
        row = 0
        while True:
            y = g.margin + g.rule_top + row * g.lh
            if y > height - g.margin - g.lh * 0.4:
                break
            out.append(
                f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" '
                f'stroke="{t.rule}" stroke-width="{sw:.2f}"/>'
            )
            row += 1
    if paper == "grid":
        x = x1
        while x <= x2:
            out.append(
                f'<line x1="{x:.1f}" y1="{g.margin + g.rule_top - g.lh:.1f}" '
                f'x2="{x:.1f}" y2="{height - g.margin - g.lh * 0.4:.1f}" '
                f'stroke="{t.rule}" stroke-width="{sw:.2f}"/>'
            )
            x += g.lh
    if paper == "dotted":
        row = 0
        while True:
            y = g.margin + g.rule_top + row * g.lh
            if y > height - g.margin - g.lh * 0.4:
                break
            x = x1
            while x <= x2:
                out.append(
                    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{1.6 * g.s:.2f}" '
                    f'fill="{t.rule}"/>'
                )
                x += g.lh
            row += 1

    if paper in ("ruled", "grid"):
        mx = g.content_x - 24 * g.s
        out.append(
            f'<line x1="{mx:.1f}" y1="{g.margin + g.lh * 0.5:.1f}" x2="{mx:.1f}" '
            f'y2="{height - g.margin - g.lh * 0.5:.1f}" '
            f'stroke="{t.margin_rule}" stroke-width="{1.6 * g.s:.2f}"/>'
        )
        for k in range(3):
            cy = g.margin + g.lh * (2.6 + k * 4.2)
            if cy < height - g.margin - g.lh:
                out.append(
                    f'<circle cx="{g.paper_x + g.pad_x * 0.28:.1f}" cy="{cy:.1f}" '
                    f'r="{8 * g.s:.1f}" fill="{t.backdrop}" opacity="0.9"/>'
                )
    return "".join(out)


def render_document_svg(
    doc: RenderedDoc,
    *,
    width: int = 1080,
    min_height: int | None = None,
    paper: PaperStyle = "ruled",
) -> str:
    theme = get_theme(doc.theme)
    s = width / 1080
    g = _Geom(
        s=s,
        width=float(width),
        margin=30 * s,
        pad_x=66 * s,
        rule_top=100 * s,
        lh=54 * s,
    )

    b = _Builder(g, theme)
    _render_body(b, doc)

    height = g.margin * 2 + g.rule_top + b.row * g.lh + 30 * s
    if min_height:
        height = max(height, float(min_height))

    footer_y = height - g.margin - 26 * s
    footer = (
        f'<line x1="{g.content_x:.1f}" y1="{footer_y - 26 * s:.1f}" '
        f'x2="{g.content_x + g.content_w:.1f}" y2="{footer_y - 26 * s:.1f}" '
        f'stroke="{theme.hairline}" stroke-width="{1 * s:.2f}"/>'
        f'<text x="{g.content_x:.1f}" y="{footer_y:.1f}" '
        f'font-family="{_fonts(theme.body_font)}" font-size="{18 * s:.1f}" '
        f'fill="{theme.ink_muted}" letter-spacing="{2 * s:.2f}">'
        f"{xml_escape(doc.date_display)}</text>"
        f'<text x="{g.content_x + g.content_w:.1f}" y="{footer_y:.1f}" '
        f'text-anchor="end" font-family="{_fonts(theme.body_font)}" '
        f'font-size="{18 * s:.1f}" fill="{theme.ink_muted}" '
        f'letter-spacing="{2 * s:.2f}">耶穌同行日記</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height:.0f}" viewBox="0 0 {width} {height:.0f}" '
        f'role="img" aria-label="{xml_escape(doc.date_display)} 日記卡片">'
        "<defs>"
        '<filter id="cardShadow" x="-20%" y="-20%" width="140%" height="140%">'
        f'<feDropShadow dx="0" dy="{12 * s:.1f}" stdDeviation="{16 * s:.1f}" '
        'flood-color="#000000" flood-opacity="0.18"/>'
        "</filter>"
        '<linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#ffffff" stop-opacity="0.55"/>'
        '<stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>'
        "</linearGradient>"
        "</defs>"
        f'<rect width="{width}" height="{height:.0f}" fill="{theme.backdrop}"/>'
        f'<rect x="{g.paper_x:.1f}" y="{g.margin:.1f}" width="{g.paper_w:.1f}" '
        f'height="{height - 2 * g.margin:.1f}" rx="{20 * s:.1f}" '
        f'fill="{theme.paper}" stroke="{theme.paper_edge}" '
        f'stroke-width="{1 * s:.2f}" filter="url(#cardShadow)"/>'
        f'<rect x="{g.paper_x:.1f}" y="{g.margin:.1f}" width="{g.paper_w:.1f}" '
        f'height="{min(160 * s, height / 3):.1f}" rx="{20 * s:.1f}" '
        'fill="url(#sheen)" opacity="0.5"/>'
        + _paper_pattern(paper, g, theme, height)
        + "".join(b.body)
        + footer
        + "</svg>"
    )


def render_entry_svg(
    entry: Entry,
    template: JournalTemplate,
    *,
    theme: str | None = None,
    width: int = 1080,
    min_height: int | None = None,
    paper: PaperStyle = "ruled",
) -> str:
    if theme:
        entry = entry.model_copy(update={"theme": theme})
    doc = build_document(entry, template)
    return render_document_svg(
        doc, width=width, min_height=min_height, paper=paper
    )
