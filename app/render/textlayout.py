"""Word wrapping for mixed CJK / Latin text, for the SVG card renderer.

SVG has no automatic line breaking, so we do it ourselves. Widths are
estimated rather than measured — a full-width CJK glyph is 1em, Latin glyphs
get a small per-character table. That is accurate enough for a fixed-width
card, and it avoids depending on a font-metrics library (or a working Cairo
install) on Windows.

Also handles the two CJK typesetting rules that are most visible when they're
broken: a line must not *start* with closing punctuation, and must not *end*
with opening punctuation.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.richtext import Run

#: Punctuation that may not begin a line — it hangs past the right edge instead.
CLOSING = set("、。，．：；！？）】》〉」』〞”’%,.!?;:)]}…〜～ー–—")
#: Punctuation that may not end a line — it moves down with the word after it.
OPENING = set("（【《〈「『〝“‘([{#$@")

_NARROW = set("iljtfIr.,;:'\"!|()[]{}`")
_WIDE_LATIN = set("mwMW@%&")


def char_width(ch: str) -> float:
    """Advance width in ``em``."""
    o = ord(ch)
    if ch == "\t":
        return 2.0
    if ch == " ":
        return 0.30
    if (
        0x1100 <= o <= 0x115F
        or 0x2E80 <= o <= 0xA4CF
        or 0xA960 <= o <= 0xA97F
        or 0xAC00 <= o <= 0xD7A3
        or 0xF900 <= o <= 0xFAFF
        or 0xFE10 <= o <= 0xFE19
        or 0xFE30 <= o <= 0xFE6F
        or 0xFF00 <= o <= 0xFF60
        or 0xFFE0 <= o <= 0xFFE6
        or 0x20000 <= o <= 0x3FFFD
    ):
        return 1.0
    if ch in _NARROW:
        return 0.30
    if ch in _WIDE_LATIN:
        return 0.72
    if ch.isupper():
        return 0.66
    if ch.isdigit():
        return 0.55
    return 0.52


def text_width(text: str) -> float:
    return sum(char_width(c) for c in text)


def is_wide(ch: str) -> bool:
    return char_width(ch) >= 0.95


@dataclass
class Piece:
    """A stretch of text on one line sharing a single visual style."""

    text: str
    color: str | None = None
    bold: bool = False
    italic: bool = False


@dataclass
class _Unit:
    text: str
    width: float
    color: str | None
    bold: bool
    italic: bool
    is_space: bool = False
    is_break: bool = False


def _tokenize(runs: list[Run]) -> list[_Unit]:
    units: list[_Unit] = []
    for run in runs:
        buf = ""
        for ch in run.text:
            if ch == "\n":
                if buf:
                    units.append(
                        _Unit(buf, text_width(buf), run.color, run.bold, run.italic)
                    )
                    buf = ""
                units.append(_Unit("", 0.0, run.color, run.bold, run.italic, is_break=True))
                continue
            if ch == " " or is_wide(ch):
                if buf:
                    units.append(
                        _Unit(buf, text_width(buf), run.color, run.bold, run.italic)
                    )
                    buf = ""
                units.append(
                    _Unit(
                        ch,
                        char_width(ch),
                        run.color,
                        run.bold,
                        run.italic,
                        is_space=(ch == " "),
                    )
                )
                continue
            buf += ch
        if buf:
            units.append(_Unit(buf, text_width(buf), run.color, run.bold, run.italic))
    return units


def _to_pieces(units: list[_Unit]) -> list[Piece]:
    pieces: list[Piece] = []
    for u in units:
        if (
            pieces
            and pieces[-1].color == u.color
            and pieces[-1].bold == u.bold
            and pieces[-1].italic == u.italic
        ):
            pieces[-1].text += u.text
        else:
            pieces.append(Piece(u.text, u.color, u.bold, u.italic))
    return [p for p in pieces if p.text]


def wrap_runs(runs: list[Run], max_width_em: float) -> list[list[Piece]]:
    """Break ``runs`` into lines no wider than ``max_width_em``."""
    if max_width_em <= 0:
        return []
    units = _tokenize(runs)
    lines: list[list[_Unit]] = [[]]
    width = 0.0

    for i, unit in enumerate(units):
        if unit.is_break:
            lines.append([])
            width = 0.0
            continue

        if unit.is_space and not lines[-1]:
            continue  # never start a line with a space

        overflow = width + unit.width > max_width_em + 1e-9
        hangs = len(unit.text) == 1 and unit.text in CLOSING

        if overflow and lines[-1] and not hangs:
            lines.append([])
            width = 0.0
            if unit.is_space:
                continue

        # An opening bracket must not be stranded at the end of a line.
        if (
            len(unit.text) == 1
            and unit.text in OPENING
            and i + 1 < len(units)
            and width + unit.width + units[i + 1].width > max_width_em + 1e-9
            and lines[-1]
        ):
            lines.append([])
            width = 0.0

        lines[-1].append(unit)
        width += unit.width

    return [_to_pieces(line) for line in lines if line] or [[]]


def wrap_plain(
    text: str, max_width_em: float, color: str | None = None
) -> list[list[Piece]]:
    return wrap_runs([Run(text, color)], max_width_em)
