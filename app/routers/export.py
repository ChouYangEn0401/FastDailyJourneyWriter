"""Rendering endpoints: artifact HTML and notebook-card SVG.

Neither of these calls a model or the network. The designs were finished
before the app shipped, so exporting is deterministic and works for everyone.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from app.config import settings
from app.models import ArtifactRequest, CardRequest
from app.render.artifact_html import render_document
from app.render.card_svg import render_document_svg
from app.render.document import build_document
from app.render.layout_registry import get_layout
from app.services import require_entry

router = APIRouter(prefix="/api/export", tags=["export"])

_SAFE = re.compile(r"[^0-9A-Za-z一-鿿._-]+")


class HtmlResult(BaseModel):
    html: str
    layout: str


class SvgResult(BaseModel):
    svg: str
    width: int
    height: int


class SaveRequest(BaseModel):
    entry_id: int
    kind: str            # "html" | "svg"
    content: str


class SaveResult(BaseModel):
    path: str


def _doc(entry_id: int, theme: str | None, layout: str | None):
    entry, template = require_entry(entry_id)
    updates: dict[str, str] = {}
    if theme:
        updates["theme"] = theme
    if layout:
        updates["layout"] = layout
    if updates:
        entry = entry.model_copy(update=updates)
    return build_document(entry, template)


@router.post("/html", response_model=HtmlResult)
def export_html(req: ArtifactRequest) -> HtmlResult:
    doc = _doc(req.entry_id, req.theme, req.layout)
    chosen = get_layout(doc.layout)
    html = render_document(
        doc, gift_cover=req.gift_cover, gift_message=req.gift_message
    )
    return HtmlResult(html=html, layout=chosen.id if chosen else "letter")


@router.get("/html/{entry_id}", response_class=HTMLResponse)
def view_html(
    entry_id: int,
    theme: str | None = None,
    layout: str | None = None,
    gift_cover: bool = False,
    gift_message: str = "",
) -> HTMLResponse:
    """Open the finished page directly in a browser tab."""
    doc = _doc(entry_id, theme, layout)
    return HTMLResponse(
        render_document(doc, gift_cover=gift_cover, gift_message=gift_message)
    )


@router.post("/card", response_model=SvgResult)
def export_card(req: CardRequest) -> SvgResult:
    doc = _doc(req.entry_id, req.theme, req.layout)
    chosen = get_layout(doc.layout)
    paper = req.paper or (chosen.card_paper if chosen else "ruled")
    width = max(480, min(2400, req.width))
    min_height = None if req.height == "auto" else max(480, int(req.height))
    svg = render_document_svg(doc, width=width, min_height=min_height, paper=paper)
    m = re.search(r'height="(\d+)"', svg)
    return SvgResult(svg=svg, width=width, height=int(m.group(1)) if m else 0)


@router.get("/card/{entry_id}.svg")
def view_card(
    entry_id: int,
    theme: str | None = None,
    layout: str | None = None,
    width: int = Query(1080, ge=480, le=2400),
    paper: str | None = None,
) -> Response:
    doc = _doc(entry_id, theme, layout)
    chosen = get_layout(doc.layout)
    svg = render_document_svg(
        doc, width=width, paper=paper or (chosen.card_paper if chosen else "ruled")
    )
    return Response(content=svg, media_type="image/svg+xml")


@router.post("/save", response_model=SaveResult)
def save_export(req: SaveRequest) -> SaveResult:
    if req.kind not in ("html", "svg"):
        raise HTTPException(400, "kind 只能是 html 或 svg。")
    entry, _ = require_entry(req.entry_id)
    stem = _SAFE.sub("-", f"{entry.entry_date.isoformat()}-{entry.title or 'journal'}")
    path = settings.exports_dir / f"{stem[:80]}.{req.kind}"
    path.write_text(req.content, encoding="utf-8")
    return SaveResult(path=str(path))
