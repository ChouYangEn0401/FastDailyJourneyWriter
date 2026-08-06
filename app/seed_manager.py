"""Install the shipped defaults into the data directory on first run.

Nothing the app renders is hard-coded in Python. Question sets live in
``data/templates/*.json`` and page designs live in ``data/layouts/``. This
module copies the shipped defaults from ``content/`` there once, so a fresh
install is usable immediately and every default is then an ordinary editable
file.

A manifest records what has already been installed, so deleting or editing a
default sticks — it will not silently come back on the next boot.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from app.config import PROJECT_ROOT, settings

log = logging.getLogger(__name__)

#: The shipped question sets and page designs. They live outside ``app/``
#: because they are plain content, not Python — nothing in them is specific to
#: this backend, so any future client can ship the same files.
SEED_DIR = PROJECT_ROOT / "content"


def _load_manifest() -> set[str]:
    if not settings.seed_manifest.exists():
        return set()
    try:
        return set(json.loads(settings.seed_manifest.read_text("utf-8")))
    except Exception:  # noqa: BLE001 - a corrupt manifest just means "reinstall"
        return set()


def _save_manifest(installed: set[str]) -> None:
    settings.seed_manifest.write_text(
        json.dumps(sorted(installed), ensure_ascii=False, indent=2), "utf-8"
    )


def install_seeds(*, force: bool = False) -> list[str]:
    """Copy any not-yet-installed defaults into the data directory."""
    installed = set() if force else _load_manifest()
    added: list[str] = []

    pairs = (
        (SEED_DIR / "templates", settings.templates_dir),
        (SEED_DIR / "layouts", settings.layouts_dir),
    )
    for src_dir, dst_dir in pairs:
        if not src_dir.exists():
            continue
        dst_dir.mkdir(parents=True, exist_ok=True)
        for src in sorted(src_dir.iterdir()):
            if not src.is_file():
                continue
            key = f"{src_dir.name}/{src.name}"
            if key in installed and not force:
                continue
            dst = dst_dir / src.name
            if dst.exists() and not force:
                installed.add(key)
                continue
            shutil.copyfile(src, dst)
            installed.add(key)
            added.append(key)

    if added or not settings.seed_manifest.exists():
        _save_manifest(installed)
    if added:
        log.info("Installed defaults: %s", ", ".join(added))
    return added


def restore_default(key: str) -> bool:
    """Put one shipped default back, overwriting whatever is there now."""
    src = SEED_DIR / key
    if not src.is_file():
        return False
    dst_dir = (
        settings.templates_dir
        if key.startswith("templates/")
        else settings.layouts_dir
    )
    shutil.copyfile(src, dst_dir / src.name)
    installed = _load_manifest()
    installed.add(key)
    _save_manifest(installed)
    return True
