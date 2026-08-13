// Port of backend/render/themes.py — visual themes shared by the HTML artifact
// and the SVG card.
//
// Each theme is a small, deliberately constrained token set: two surfaces, one
// ink, one muted ink, a hairline, one accent, and a type pairing. Constraining
// it this way is what keeps every export looking like it came from the same
// journal rather than from five different generators.
//
// Keys stay snake_case on purpose. `content/layouts/*.j2` reads them directly
// as `t.paper_edge`, `t.display_font`, and those files are shared verbatim with
// the Python renderer — renaming here would fork the layouts.

const SERIF =
  '"Noto Serif TC", "Songti TC", "Source Han Serif TC", ' +
  '"PingFang TC", Georgia, "Times New Roman", serif';
const SANS =
  '"Noto Sans TC", "PingFang TC", "Microsoft JhengHei", ' +
  '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
const HAND =
  '"LXGW WenKai TC", "Kaiti TC", "DFKai-SB", STKaiti, ' +
  '"Noto Serif TC", serif';

/** Dark-mode counterparts a theme inherits unless it overrides them. */
const DARK_DEFAULTS = {
  dark_backdrop: "#14161a",
  dark_paper: "#1c1f24",
  dark_ink: "#e9e6df",
  dark_ink_muted: "#9aa0a8",
  dark_hairline: "#2f343b",
};

const theme = (t) => Object.freeze({ ...DARK_DEFAULTS, ...t });

export const THEMES = Object.freeze({
  letterpress: theme({
    id: "letterpress",
    name: "信箋 Letterpress",
    backdrop: "#efeae1",
    paper: "#fdfbf6",
    paper_edge: "#e6dfd2",
    ink: "#23262b",
    ink_muted: "#7b7468",
    hairline: "#e2dacb",
    accent: "#b5623c",
    rule: "#e8e0d0",
    margin_rule: "#e2b9ab",
    display_font: SERIF,
    body_font: SERIF,
    tags: ["溫暖", "書信感"],
  }),
  notebook: theme({
    id: "notebook",
    name: "筆記本 Notebook",
    backdrop: "#e8ebee",
    paper: "#ffffff",
    paper_edge: "#dfe3e8",
    ink: "#22252a",
    ink_muted: "#767d86",
    hairline: "#e3e7ec",
    accent: "#2456b8",
    rule: "#d9e4f2",
    margin_rule: "#efb1ac",
    display_font: HAND,
    body_font: HAND,
    tags: ["手寫", "橫線稿"],
  }),
  linen: theme({
    id: "linen",
    name: "亞麻 Linen",
    backdrop: "#e7e3da",
    paper: "#f7f4ec",
    paper_edge: "#ddd7c9",
    ink: "#2b2b28",
    ink_muted: "#7d7869",
    hairline: "#e0dacb",
    accent: "#5d7a5a",
    rule: "#e4dfd0",
    margin_rule: "#c8bba0",
    display_font: SERIF,
    body_font: SANS,
    tags: ["素雅", "自然"],
  }),
  dawn: theme({
    id: "dawn",
    name: "晨光 Dawn",
    backdrop: "#f3ecec",
    paper: "#fffaf7",
    paper_edge: "#f0dfd8",
    ink: "#2a2124",
    ink_muted: "#8a7076",
    hairline: "#f0dfd8",
    accent: "#c9705f",
    rule: "#f4e2dc",
    margin_rule: "#e9b7a8",
    display_font: SERIF,
    body_font: SANS,
    tags: ["柔和", "清晨"],
  }),
  midnight: theme({
    id: "midnight",
    name: "夜禱 Midnight",
    backdrop: "#14161c",
    paper: "#1e222b",
    paper_edge: "#2b3140",
    ink: "#e8e6e1",
    ink_muted: "#98a0ad",
    hairline: "#2e3540",
    accent: "#c8a86b",
    rule: "#2a313c",
    margin_rule: "#3d4756",
    display_font: SERIF,
    body_font: SANS,
    dark_backdrop: "#0f1116",
    dark_paper: "#1a1e26",
    dark_ink: "#e8e6e1",
    dark_ink_muted: "#98a0ad",
    dark_hairline: "#2a313c",
    tags: ["深色", "安靜"],
  }),
});

export const DEFAULT_THEME = "letterpress";

export function getTheme(themeId) {
  return THEMES[themeId || DEFAULT_THEME] ?? THEMES[DEFAULT_THEME];
}

export function themeSummaries() {
  return Object.values(THEMES).map((t) => ({
    id: t.id,
    name: t.name,
    tags: t.tags,
    swatch: [t.paper, t.ink, t.accent, t.backdrop],
  }));
}
