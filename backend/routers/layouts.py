"""Page designs: list, inspect, edit, delete, and (optionally) generate one."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.ai.client import AIRefused, AIUnavailable, is_available
from backend.ai.layout_designer import design_layout
from backend.models import Layout, LayoutDesignRequest
from backend.render.layout_registry import (
    delete_layout,
    get_layout,
    read_layout_html,
    save_layout,
)
from backend.seed_manager import restore_default

router = APIRouter(prefix="/api/layouts", tags=["layouts"])


class LayoutSource(BaseModel):
    layout: Layout
    html: str


class LayoutSave(BaseModel):
    layout: Layout
    html: str


class DesignResult(BaseModel):
    layout: Layout


@router.get("", response_model=list[Layout])
def list_layouts() -> list[Layout]:
    from backend.render.layout_registry import all_layouts

    return all_layouts()


@router.get("/{layout_id}", response_model=LayoutSource)
def read_layout(layout_id: str) -> LayoutSource:
    layout = get_layout(layout_id)
    if layout is None or layout.id != layout_id:
        raise HTTPException(404, f"找不到版型：{layout_id}")
    return LayoutSource(layout=layout, html=read_layout_html(layout_id))


@router.put("/{layout_id}", response_model=Layout)
def write_layout(layout_id: str, payload: LayoutSave) -> Layout:
    """Save an edited design. Layouts are just files — editing them is normal."""
    layout = payload.layout.model_copy(update={"id": layout_id})
    return save_layout(layout, payload.html)


@router.delete("/{layout_id}", status_code=204)
def remove_layout(layout_id: str) -> None:
    if not delete_layout(layout_id):
        raise HTTPException(404, f"找不到版型：{layout_id}")


@router.post("/{layout_id}/restore", response_model=Layout)
def restore_layout(layout_id: str) -> Layout:
    """Put a shipped design back the way it came."""
    ok = restore_default(f"layouts/{layout_id}.html.j2")
    restore_default(f"layouts/{layout_id}.json")
    if not ok:
        raise HTTPException(404, f"{layout_id} 不是內建版型，沒有可還原的版本。")
    layout = get_layout(layout_id)
    assert layout is not None
    return layout


@router.post("/design", response_model=DesignResult, status_code=201)
def design(req: LayoutDesignRequest) -> DesignResult:
    """Generate a new design and keep it forever.

    This is the only endpoint that needs an API key, and it is a one-off:
    once the design exists it renders like any other, offline and instantly,
    for anyone using the app.
    """
    if not is_available():
        raise HTTPException(
            400,
            "設計新版型需要 ANTHROPIC_API_KEY。內建的版型不需要，照常可用。",
        )
    try:
        layout, _ = design_layout(
            name=req.name, brief=req.brief, base_layout=req.base_layout
        )
        return DesignResult(layout=layout)
    except (AIUnavailable, AIRefused, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"版型設計失敗：{exc}") from exc
