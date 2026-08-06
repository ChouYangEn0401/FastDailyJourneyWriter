"""Personal setup: pen palette and remembered defaults."""

from __future__ import annotations

from fastapi import APIRouter

from backend import preferences
from backend.models import Preferences

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("", response_model=Preferences)
def read_preferences() -> Preferences:
    return preferences.load()


@router.put("", response_model=Preferences)
def write_preferences(prefs: Preferences) -> Preferences:
    return preferences.save(prefs)


@router.post("/palette/reset", response_model=Preferences)
def reset_palette() -> Preferences:
    return preferences.reset_palette()
