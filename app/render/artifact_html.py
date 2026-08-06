"""Entry -> a single self-contained HTML page.

The design work happened *before* anyone wrote a word: layouts under
``data/layouts/`` are finished pages with a hole where the content goes. So
exporting is pure filling-in — no API key, no network, no waiting, and the
same entry always produces the same page.

Adding a design means dropping two files into ``data/layouts/``. That is also
how the optional layout designer in ``app/ai/layout_designer.py`` works: it
writes a new design there once, and from then on it costs nothing to use.
"""

from __future__ import annotations

import html

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from app.config import PROJECT_ROOT, settings
from app.models import Entry, JournalTemplate
from app.render.document import RenderedDoc, build_document
from app.render.layout_registry import (
    FALLBACK_LAYOUT,
    get_layout,
    template_filename,
)
from app.render.themes import get_theme
from app.richtext import Run

#: Shipped partials (cover markup, shared tokens) live next to the seeds so a
#: user layout can include them even if they deleted their copy.
SEED_LAYOUT_DIR = PROJECT_ROOT / "content" / "layouts"


def runs_to_html(runs: list[Run]) -> Markup:
    """Render colour runs as inline markup.

    The writer's colour goes into a ``--ink`` custom property as well as
    ``color``, so a layout's stylesheet can lighten every hand-picked colour
    in dark mode without knowing in advance which colours were used.
    """
    out: list[str] = []
    for run in runs:
        text = html.escape(run.text).replace("  ", " &nbsp;")
        if not text:
            continue
        if run.bold:
            text = f"<strong>{text}</strong>"
        if run.italic:
            text = f"<em>{text}</em>"
        if run.color:
            ink = html.escape(run.color, quote=True)
            text = f'<span style="--ink:{ink};color:var(--ink)">{text}</span>'
        out.append(text)
    return Markup("".join(out) or "&nbsp;")


def _env() -> Environment:
    # Not cached: layouts are editable files, and picking up an edit on the
    # next export is worth more here than shaving a few milliseconds.
    env = Environment(
        loader=FileSystemLoader([settings.layouts_dir, SEED_LAYOUT_DIR]),
        autoescape=select_autoescape(["html", "xml", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["runs"] = runs_to_html
    return env


def render_document(
    doc: RenderedDoc,
    *,
    layout: str | None = None,
    gift_cover: bool = False,
    gift_message: str = "",
) -> str:
    chosen = get_layout(layout or doc.layout)
    layout_id = chosen.id if chosen else FALLBACK_LAYOUT
    return _env().get_template(template_filename(layout_id)).render(
        doc=doc,
        t=get_theme(doc.theme),
        layout=chosen,
        gift_cover=gift_cover,
        gift_message=gift_message.strip(),
    )


def render_entry(
    entry: Entry,
    template: JournalTemplate,
    *,
    theme: str | None = None,
    layout: str | None = None,
    gift_cover: bool = False,
    gift_message: str = "",
) -> str:
    updates: dict[str, str] = {}
    if theme:
        updates["theme"] = theme
    if layout:
        updates["layout"] = layout
    if updates:
        entry = entry.model_copy(update=updates)
    doc = build_document(entry, template)
    return render_document(
        doc, gift_cover=gift_cover, gift_message=gift_message
    )
