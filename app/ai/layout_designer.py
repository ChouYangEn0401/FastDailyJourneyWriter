"""Optional: design a *new* page layout and save it as a permanent file.

This is the only place Claude touches the look of an export, and it runs at
design time, not export time. It produces a layout file under
``data/layouts/``; from then on that design renders like every other one —
instantly, offline, for anyone using the app, with no API key involved.

That is the whole point of the split: one person with a key can design a
layout and hand the two files to anyone.
"""

from __future__ import annotations

import hashlib
import re

from app.ai.client import complete
from app.models import Layout
from app.render.layout_registry import read_layout_html, save_layout

_FENCE = re.compile(r"^\s*```(?:html|jinja|jinja2|j2)?\s*|\s*```\s*$", re.IGNORECASE)
_SLUG = re.compile(r"[^a-z0-9-]+")

SYSTEM = """\
You design page layouts for a devotional-journal app. You are given a working \
Jinja2 layout and a brief, and you return one new Jinja2 layout.

Return ONLY the template source. No prose, no code fences.

## The contract you must satisfy

The template is rendered with these variables:

- `doc.date_display` (str, e.g. "2026．07．30"), `doc.weekday` (str, e.g. "四"),
  `doc.entry_date` (a Python date: `.year` `.month` `.day`),
  `doc.title` (str, may be empty), `doc.template_name` (str),
  `doc.word_count` (int), `doc.palette` (list of hex strings),
  `doc.has_closing` (bool), `doc.closing_lines`.
- `doc.sections` — each has `.id .title .color .icon` (icon may be None) and
  `.fields`.
- each field has `.label`, `.chips`, `.numbered`, `.lines`.
  - `.chips` is non-empty for tick-box style answers; each chip has `.label`
    and `.selected`. Render unselected chips too, visibly dimmer — seeing what
    was *not* ticked is part of the point.
  - otherwise `.lines` holds the text; `.numbered` means render them as an
    ordered list.
- `doc.closing_lines` — same shape as `.lines`.
- `t` — theme colours: `t.paper t.backdrop t.ink t.ink_muted t.hairline
  t.accent t.rule t.paper_edge t.display_font t.body_font` plus
  `t.dark_paper t.dark_backdrop t.dark_ink t.dark_ink_muted t.dark_hairline`.
- `gift_cover` (bool) and `gift_message` (str).

Rules that make the output actually work:

1. Every line of text MUST go through the `runs` filter: `{{ line | runs }}`.
   It is what preserves the colours the writer chose. Never print `.lines`
   any other way. It is already safe HTML — do not add `| safe` or `| e`.
2. Start with `{% include "_tokens.css.j2" %}` inside your `<style>`. It
   defines the CSS variables, the reset, the gift-cover behaviour and the
   dark-mode handling for the writer's ink colours.
3. Keep the gift cover working: wrap everything in
   `<div class="stage{% if not gift_cover %} open{% endif %}" id="stage">`,
   put `{% include "_cover.html.j2" %}` first, wrap the page itself in
   `<article class="journal">`, and end with `{% include "_cover.js.j2" %}`.
4. Fully self-contained: one `<style>` block, no external stylesheets, fonts,
   scripts or images. No `<link>`, no `@import`, no CDN.
5. Responsive to 360px. The page body must never scroll sideways; long words
   wrap with `overflow-wrap:anywhere`.
6. Section colour: put it on a CSS custom property —
   `<section style="--sec:{{ s.color }}">` — and style from `var(--sec)`.
7. Add a `@media print` block that removes shadows and any fixed positioning.

## Design direction

This is a quiet, personal, handwritten-feeling document. Not a dashboard, not \
a landing page. No hero sections, no KPI cards, no call-to-action buttons, no \
emoji you did not find in the data.

Make it *structurally* different from the layout you were given — a different \
column structure, a different place for the date, a different rhythm — not a \
recolour. Typography and spacing do the work; reach for those before borders, \
shadows and background fills. Set `line-height` at least 1.8 for the Chinese \
text and keep the measure around 32-40 characters.

Avoid the generic AI look: no Inter/Roboto/system-only stacks, no \
purple-to-blue gradients, no evenly-spaced rounded card grids.
"""


def design_layout(
    *, name: str, brief: str = "", base_layout: str = "letter"
) -> tuple[Layout, str]:
    """Generate a layout and persist it. Returns the metadata and its HTML."""
    try:
        base_html = read_layout_html(base_layout)
    except FileNotFoundError:
        base_html = read_layout_html("letter")

    direction = brief.strip() or "換一種結構，但保持安靜、耐看。"
    user = f"""\
請以下面這個版型為基礎，設計一個結構明顯不同的新版型。

新版型的名字：{name}
設計方向：{direction}

--- 參考版型開始 ---
{base_html}
--- 參考版型結束 ---

請直接輸出新的 Jinja2 版型原始碼。"""

    raw = complete(system=SYSTEM, user=user, max_tokens=64000, effort="high")
    html = _FENCE.sub("", raw).strip()

    if "<html" not in html.lower():
        raise ValueError("模型沒有回傳完整的版型檔。")
    if "| runs" not in html and "|runs" not in html:
        raise ValueError("產生的版型沒有使用 runs 過濾器，顏色會遺失，已捨棄。")

    layout = Layout(
        id=unique_id(slugify(name)),
        name=name.strip() or "自訂版型",
        description=brief.strip()[:200] or "由 AI 設計的版型。",
        tags=["自訂"],
        origin="custom",
    )
    save_layout(layout, html)
    return layout, html


def slugify(name: str) -> str:
    """Layout ids become filenames, so they have to be ASCII and safe.

    A purely Chinese name slugs to nothing, so fall back to a stable short
    hash of the name rather than dumping every such layout into one id.
    """
    slug = _SLUG.sub("-", name.strip().lower()).strip("-")
    if slug:
        return slug[:48]
    digest = hashlib.sha1(name.strip().encode("utf-8")).hexdigest()[:8]
    return f"layout-{digest}"


def unique_id(base: str) -> str:
    from app.render.layout_registry import all_layouts

    taken = {x.id for x in all_layouts()}
    if base not in taken:
        return base
    for n in range(2, 100):
        candidate = f"{base}-{n}"
        if candidate not in taken:
            return candidate
    return f"{base}-{hashlib.sha1(base.encode()).hexdigest()[:6]}"
