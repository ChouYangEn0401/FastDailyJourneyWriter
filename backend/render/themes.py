"""Visual themes shared by the HTML artifact and the SVG card.

Each theme is a small, deliberately constrained token set: two surfaces, one
ink, one muted ink, a hairline, one accent, and a type pairing. Constraining it
this way is what keeps every export looking like it came from the same journal
rather than from five different generators.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Theme:
    id: str
    name: str
    #: Page behind the card.
    backdrop: str
    #: The card / paper itself.
    paper: str
    paper_edge: str
    ink: str
    ink_muted: str
    hairline: str
    accent: str
    #: Ruled-line colour for notebook paper.
    rule: str
    #: Left margin line on notebook paper.
    margin_rule: str
    display_font: str
    body_font: str
    #: Dark-mode counterparts for the HTML artifact.
    dark_backdrop: str = "#14161a"
    dark_paper: str = "#1c1f24"
    dark_ink: str = "#e9e6df"
    dark_ink_muted: str = "#9aa0a8"
    dark_hairline: str = "#2f343b"
    tags: list[str] = field(default_factory=list)


_SERIF = (
    '"Noto Serif TC", "Songti TC", "Source Han Serif TC", '
    '"PingFang TC", Georgia, "Times New Roman", serif'
)
_SANS = (
    '"Noto Sans TC", "PingFang TC", "Microsoft JhengHei", '
    '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
)
_HAND = (
    '"LXGW WenKai TC", "Kaiti TC", "DFKai-SB", STKaiti, '
    '"Noto Serif TC", serif'
)


THEMES: dict[str, Theme] = {
    "letterpress": Theme(
        id="letterpress",
        name="信箋 Letterpress",
        backdrop="#efeae1",
        paper="#fdfbf6",
        paper_edge="#e6dfd2",
        ink="#23262b",
        ink_muted="#7b7468",
        hairline="#e2dacb",
        accent="#b5623c",
        rule="#e8e0d0",
        margin_rule="#e2b9ab",
        display_font=_SERIF,
        body_font=_SERIF,
        tags=["溫暖", "書信感"],
    ),
    "notebook": Theme(
        id="notebook",
        name="筆記本 Notebook",
        backdrop="#e8ebee",
        paper="#ffffff",
        paper_edge="#dfe3e8",
        ink="#22252a",
        ink_muted="#767d86",
        hairline="#e3e7ec",
        accent="#2456b8",
        rule="#d9e4f2",
        margin_rule="#efb1ac",
        display_font=_HAND,
        body_font=_HAND,
        tags=["手寫", "橫線稿"],
    ),
    "linen": Theme(
        id="linen",
        name="亞麻 Linen",
        backdrop="#e7e3da",
        paper="#f7f4ec",
        paper_edge="#ddd7c9",
        ink="#2b2b28",
        ink_muted="#7d7869",
        hairline="#e0dacb",
        accent="#5d7a5a",
        rule="#e4dfd0",
        margin_rule="#c8bba0",
        display_font=_SERIF,
        body_font=_SANS,
        tags=["素雅", "自然"],
    ),
    "dawn": Theme(
        id="dawn",
        name="晨光 Dawn",
        backdrop="#f3ecec",
        paper="#fffaf7",
        paper_edge="#f0dfd8",
        ink="#2a2124",
        ink_muted="#8a7076",
        hairline="#f0dfd8",
        accent="#c9705f",
        rule="#f4e2dc",
        margin_rule="#e9b7a8",
        display_font=_SERIF,
        body_font=_SANS,
        tags=["柔和", "清晨"],
    ),
    "midnight": Theme(
        id="midnight",
        name="夜禱 Midnight",
        backdrop="#14161c",
        paper="#1e222b",
        paper_edge="#2b3140",
        ink="#e8e6e1",
        ink_muted="#98a0ad",
        hairline="#2e3540",
        accent="#c8a86b",
        rule="#2a313c",
        margin_rule="#3d4756",
        display_font=_SERIF,
        body_font=_SANS,
        dark_backdrop="#0f1116",
        dark_paper="#1a1e26",
        dark_ink="#e8e6e1",
        dark_ink_muted="#98a0ad",
        dark_hairline="#2a313c",
        tags=["深色", "安靜"],
    ),
}

DEFAULT_THEME = "letterpress"


def get_theme(theme_id: str | None) -> Theme:
    return THEMES.get(theme_id or DEFAULT_THEME, THEMES[DEFAULT_THEME])


def theme_summaries() -> list[dict[str, object]]:
    return [
        {
            "id": t.id,
            "name": t.name,
            "tags": t.tags,
            "swatch": [t.paper, t.ink, t.accent, t.backdrop],
        }
        for t in THEMES.values()
    ]
