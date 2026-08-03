"""Question sets and colour themes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models import JournalTemplate
from app.render.themes import theme_summaries
from app.seed_manager import restore_default
from app.services import entries_using_template, require_template
from app.template_registry import all_templates, delete_template, save_template

router = APIRouter(prefix="/api", tags=["templates"])


@router.get("/templates", response_model=list[JournalTemplate])
def list_templates() -> list[JournalTemplate]:
    return all_templates()


@router.get("/templates/{template_id}", response_model=JournalTemplate)
def read_template(template_id: str) -> JournalTemplate:
    return require_template(template_id)


@router.put("/templates/{template_id}", response_model=JournalTemplate)
def write_template(template_id: str, template: JournalTemplate) -> JournalTemplate:
    """Create or edit a question set. Defaults are editable like any other."""
    if not template_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(400, "範本 id 只能使用英數字、- 與 _。")
    return save_template(template.model_copy(update={"id": template_id}))


@router.delete("/templates/{template_id}", status_code=204)
def remove_template(template_id: str, force: bool = False) -> None:
    """Delete a question set.

    Entries written with it keep every word either way — they fall back to a
    read-only recovery view. But losing the questions makes an old entry much
    harder to read, so deleting one that is still in use needs ``force``.
    """
    in_use = entries_using_template(template_id)
    if in_use and not force:
        raise HTTPException(
            409,
            f"有 {in_use} 篇日記還在用這個題組。內容不會不見，"
            f"但刪掉之後那些日記只會看到純文字。確定要刪就再按一次。",
        )
    if not delete_template(template_id):
        raise HTTPException(404, f"找不到範本：{template_id}")


@router.post("/templates/{template_id}/restore", response_model=JournalTemplate)
def restore_template(template_id: str) -> JournalTemplate:
    if not restore_default(f"templates/{template_id}.json"):
        raise HTTPException(404, f"{template_id} 不是內建範本，沒有可還原的版本。")
    return require_template(template_id)


@router.get("/themes")
def list_themes() -> list[dict[str, object]]:
    return theme_summaries()
