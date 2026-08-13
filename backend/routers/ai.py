"""AI endpoints: drawing prompt and title suggestion."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.ai.artifact import suggest_title
from backend.ai.client import AIRefused, AIUnavailable, is_available
from backend.ai.image_prompt import STYLES, build_image_prompt
from backend.models import ImagePromptRequest, ImagePromptResponse
from backend.render.document import build_document
from backend.services import require_entry

router = APIRouter(prefix="/api/ai", tags=["ai"])


class TitleRequest(BaseModel):
    entry_id: int


class TitleResult(BaseModel):
    title: str


@router.get("/status")
def status() -> dict[str, object]:
    """Which optional features are switched on. Exports never depend on this."""
    from backend.config import settings

    return {"available": is_available(), "model": settings.model}


@router.get("/styles")
def list_styles() -> list[dict[str, str]]:
    return [{"id": k, "label": v[0], "hint": v[1]} for k, v in STYLES.items()]


@router.post("/image-prompt", response_model=ImagePromptResponse)
def image_prompt(req: ImagePromptRequest) -> ImagePromptResponse:
    entry, template = require_entry(req.entry_id)
    doc = build_document(entry, template)
    return build_image_prompt(doc, style=req.style)


@router.post("/title", response_model=TitleResult)
def title(req: TitleRequest) -> TitleResult:
    if not is_available():
        raise HTTPException(400, "尚未設定 ANTHROPIC_API_KEY，無法使用標題建議。")
    entry, template = require_entry(req.entry_id)
    doc = build_document(entry, template)
    try:
        return TitleResult(title=suggest_title(doc))
    except (AIUnavailable, AIRefused) as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"標題產生失敗：{exc}") from exc
