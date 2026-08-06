"""Sanitising and parsing the colour-annotated rich text the editor produces.

The editor is a ``contenteditable`` region, so anything could arrive. We accept
a deliberately tiny subset — enough for "write this sentence in red, that one
in green", nothing more:

    <b> <strong> <i> <em> <u> <s> <br>
    <span style="color: #hex">
    <div> <p>          (treated as line breaks)

Everything else is dropped, attributes included. The same module also converts
that HTML into flat *runs* — ``(text, colour, bold, italic)`` — which is what
the SVG card renderer needs, since SVG has no inline markup.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser

INLINE_TAGS = {"b", "strong", "i", "em", "u", "s", "strike", "span"}
BLOCK_TAGS = {"div", "p", "li"}
VOID_TAGS = {"br"}
#: Tags whose *contents* must be discarded too, not just the tags themselves —
#: otherwise pasting a page fragment leaks script bodies into the journal text.
DROP_CONTENT_TAGS = {
    "script",
    "style",
    "title",
    "textarea",
    "noscript",
    "iframe",
    "object",
    "embed",
    "template",
    "head",
    "svg",
    "math",
}

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_RGB = re.compile(
    r"^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,[^)]*)?\)$"
)
_COLOR_DECL = re.compile(r"(?:^|;)\s*color\s*:\s*([^;]+)", re.IGNORECASE)


def normalize_color(value: str | None) -> str | None:
    """Return a ``#rrggbb`` string, or ``None`` if the value isn't a plain colour."""
    if not value:
        return None
    value = value.strip()
    if _HEX.match(value):
        if len(value) == 4:  # #abc -> #aabbcc
            return "#" + "".join(ch * 2 for ch in value[1:]).lower()
        return value.lower()
    m = _RGB.match(value)
    if m:
        r, g, b = (min(255, int(p)) for p in m.groups())
        return f"#{r:02x}{g:02x}{b:02x}"
    return None


def _extract_color(style: str | None) -> str | None:
    if not style:
        return None
    m = _COLOR_DECL.search(style)
    return normalize_color(m.group(1)) if m else None


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._open: list[str] = []
        self._muted = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in DROP_CONTENT_TAGS:
            self._muted += 1
            return
        if self._muted:
            return
        if tag in VOID_TAGS:
            self.out.append("<br>")
            return
        if tag in BLOCK_TAGS:
            # Blocks become line breaks; the first one shouldn't add a leading
            # blank line.
            if self.out and self.out[-1] != "<br>":
                self.out.append("<br>")
            self._open.append("")  # placeholder, nothing to close
            return
        if tag not in INLINE_TAGS:
            return
        if tag == "span":
            color = _extract_color(dict(attrs).get("style"))
            if color is None:
                self._open.append("")
                return
            self.out.append(f'<span style="color:{color}">')
            self._open.append("span")
            return
        canonical = {"strong": "b", "em": "i", "strike": "s"}.get(tag, tag)
        self.out.append(f"<{canonical}>")
        self._open.append(canonical)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in DROP_CONTENT_TAGS:
            self._muted = max(0, self._muted - 1)
            return
        if self._muted:
            return
        if tag in VOID_TAGS:
            return
        if tag not in INLINE_TAGS | BLOCK_TAGS:
            return
        if not self._open:
            return
        opened = self._open.pop()
        if opened:
            self.out.append(f"</{opened}>")

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if not self._muted and tag.lower() in VOID_TAGS:
            self.out.append("<br>")

    def handle_data(self, data: str) -> None:
        if self._muted:
            return
        self.out.append(html.escape(data, quote=False))

    def result(self) -> str:
        # Close anything the input left dangling.
        tail = "".join(f"</{t}>" for t in reversed(self._open) if t)
        text = "".join(self.out) + tail
        text = re.sub(r"^(?:<br>)+", "", text)
        text = re.sub(r"(?:<br>)+$", "", text)
        return text


def sanitize(raw: str | None) -> str:
    if not raw:
        return ""
    parser = _Sanitizer()
    parser.feed(raw)
    parser.close()
    return parser.result()


# --------------------------------------------------------------------------
# HTML -> runs
# --------------------------------------------------------------------------


@dataclass
class Run:
    text: str
    color: str | None = None
    bold: bool = False
    italic: bool = False


class _RunParser(HTMLParser):
    def __init__(self, default_color: str | None) -> None:
        super().__init__(convert_charrefs=True)
        self.runs: list[Run] = []
        self._colors: list[str] = []
        self._bold = 0
        self._italic = 0
        self._default = default_color

    @property
    def _color(self) -> str | None:
        return self._colors[-1] if self._colors else self._default

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "br":
            self.runs.append(Run("\n", self._color, bool(self._bold), bool(self._italic)))
        elif tag == "span":
            color = _extract_color(dict(attrs).get("style"))
            self._colors.append(color or (self._color or ""))
        elif tag in ("b", "strong"):
            self._bold += 1
        elif tag in ("i", "em"):
            self._italic += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "br":
            self.runs.append(Run("\n", self._color, bool(self._bold), bool(self._italic)))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "span" and self._colors:
            self._colors.pop()
        elif tag in ("b", "strong"):
            self._bold = max(0, self._bold - 1)
        elif tag in ("i", "em"):
            self._italic = max(0, self._italic - 1)

    def handle_data(self, data: str) -> None:
        if data:
            self.runs.append(
                Run(data, self._color, bool(self._bold), bool(self._italic))
            )


def to_runs(raw: str | None, default_color: str | None = None) -> list[Run]:
    """Flatten sanitized rich text into colour/weight runs for SVG output."""
    if not raw:
        return []
    parser = _RunParser(default_color)
    parser.feed(sanitize(raw))
    parser.close()
    merged: list[Run] = []
    for run in parser.runs:
        if (
            merged
            and merged[-1].color == run.color
            and merged[-1].bold == run.bold
            and merged[-1].italic == run.italic
            and "\n" not in merged[-1].text
            and "\n" not in run.text
        ):
            merged[-1].text += run.text
        else:
            merged.append(run)
    return merged


def to_plain(raw: str | None) -> str:
    """Plain text, used for AI prompts and search."""
    return "".join(r.text for r in to_runs(raw)).strip()
