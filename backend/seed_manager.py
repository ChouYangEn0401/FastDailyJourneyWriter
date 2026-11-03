"""Install the shipped defaults into the data directory on first run.

Nothing the app renders is hard-coded in Python. Question sets live in
``data/templates/*.json`` and page designs live in ``data/layouts/``. This
module copies the shipped defaults from ``content/`` there once, so a fresh
install is usable immediately and every default is then an ordinary editable
file.

A manifest records what has already been installed, so deleting or editing a
default sticks — it will not silently come back on the next boot.

When a shipped default is improved, copies nobody has touched are brought up
to date (:func:`upgrade_untouched`): ``content/superseded.json`` lists the
fingerprints of every earlier shipped version, and a data copy that still
matches one of them was never edited. An edited copy is never replaced, a
deleted one never comes back, and before anything is replaced the database is
snapshotted and the old copies are kept under ``backups/`` (no backup, no
upgrade). Journal entries are never touched here: they live in the database,
the defaults are files next to it.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from pathlib import Path

from backend.config import PROJECT_ROOT, settings

log = logging.getLogger(__name__)

#: The shipped question sets and page designs. They live outside ``backend/``
#: because they are plain content, not Python — nothing in them is specific to
#: this backend, so any future client can ship the same files.
SEED_DIR = PROJECT_ROOT / "content"

#: ``{"templates/<file>": [sha256 of an earlier shipped version, ...]}``.
#: Add the old fingerprint here whenever a shipped default changes, or
#: existing installs keep the old copy (still usable, just not improved).
SUPERSEDED = SEED_DIR / "superseded.json"


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
    upgrade_untouched()
    return added


def fingerprint(path: Path) -> str:
    """sha256 of a file with line endings normalised.

    A checkout on Windows writes CRLF and the data copy was copied byte for
    byte from that, so the same file must hash the same on every platform.
    """
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _superseded() -> dict[str, list[str]]:
    try:
        raw = json.loads(SUPERSEDED.read_text("utf-8"))
    except FileNotFoundError:
        return {}
    except Exception as exc:  # noqa: BLE001 - a bad table only means "upgrade nothing"
        log.warning("Ignoring %s: %s", SUPERSEDED.name, exc)
        return {}
    return {
        str(k): [str(h) for h in v]
        for k, v in raw.items()
        if isinstance(v, list) and not str(k).startswith("_")
    }


def _backup_before_upgrade(due: list[tuple[str, Path, Path]]) -> Path:
    """Keep what is about to be replaced, before anything is.

    The files being replaced are byte-for-byte an earlier shipped version, so
    nothing personal is at stake in them — but this is the one place where a
    new release rewrites files in the owner's data folder on its own, so it
    leaves the same trail a restore or an import does: a snapshot of the
    database (``backups/journal-…-before-template-upgrade.sqlite3``) and a
    copy of every replaced file (``backups/defaults-…-before-upgrade/``).
    Raises if either cannot be made; the caller then upgrades nothing.
    """
    from datetime import datetime

    from backend import backup

    backup.snapshot("before-template-upgrade")
    folder = settings.backups_dir / f"defaults-{datetime.now().strftime('%Y%m%d-%H%M%S')}-before-upgrade"
    for key, _src, dst in due:
        target = folder / key
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(dst, target)
    return folder


def upgrade_untouched() -> list[str]:
    """Replace data copies that are still an earlier shipped version."""
    due: list[tuple[str, Path, Path]] = []
    for key, old in _superseded().items():
        kind, _, name = key.partition("/")
        if kind not in ("templates", "layouts") or not name or "/" in name or ".." in name:
            continue
        src = SEED_DIR / kind / name
        dst = (settings.templates_dir if kind == "templates" else settings.layouts_dir) / name
        # A default the user deleted stays deleted: only an existing copy is upgraded.
        if not src.is_file() or not dst.is_file():
            continue
        current = fingerprint(dst)
        if current in old and current != fingerprint(src):
            due.append((key, src, dst))
    if not due:
        return []
    try:
        kept = _backup_before_upgrade(due)
    except Exception as exc:  # noqa: BLE001 - no backup, no upgrade: the old copies still work
        log.warning("Not upgrading defaults, the backup failed: %s", exc)
        return []
    for _key, src, dst in due:
        shutil.copyfile(src, dst)
    upgraded = [key for key, _src, _dst in due]
    log.info("Brought untouched defaults up to date: %s (previous copies in %s)", ", ".join(upgraded), kept.name)
    return upgraded


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
