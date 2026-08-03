"""Runtime configuration.

Everything private (the DB, exports, user-defined templates, the API key) lives
under paths that are gitignored. Nothing here reads or embeds journal content.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path
    exports_dir: Path
    templates_dir: Path
    layouts_dir: Path
    backups_dir: Path
    seed_manifest: Path
    anthropic_api_key: str | None
    model: str

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


def _load() -> Settings:
    data_dir = Path(os.getenv("JOURNAL_DATA_DIR", "data"))
    if not data_dir.is_absolute():
        data_dir = PROJECT_ROOT / data_dir

    settings = Settings(
        data_dir=data_dir,
        db_path=data_dir / "journal.sqlite3",
        exports_dir=data_dir / "exports",
        templates_dir=data_dir / "templates",
        layouts_dir=data_dir / "layouts",
        backups_dir=data_dir / "backups",
        seed_manifest=data_dir / ".seeded.json",
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        model=os.getenv("JOURNAL_MODEL", "claude-opus-5"),
    )
    for directory in (
        settings.data_dir,
        settings.exports_dir,
        settings.templates_dir,
        settings.layouts_dir,
        settings.backups_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    return settings


settings = _load()
