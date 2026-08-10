# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the desktop build.

One spec for both desktop targets — nothing in here is OS-specific. Run it on
Windows to get an .exe, run it on a Mac to get an .app. That is possible
because ``backend/`` is the same code on both; see ../README.md.

    python -m PyInstaller --noconfirm --clean platforms/desktop/journal.spec

Or use the wrapper in the repo root: build_desktop.bat / build_desktop.sh
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent.parent  # noqa: F821 (PyInstaller global)

# The shipped defaults and the front end are ordinary files the app reads at
# runtime, so they have to travel with the executable. seed_manager copies
# content/ into the user's data directory on first run.
datas = [
    (str(ROOT / "content"), "content"),
    (str(ROOT / "web"), "web"),
]

# uvicorn picks these up by string name at runtime, so static analysis cannot
# see them and they would otherwise be left out of the bundle.
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
]

a = Analysis(  # noqa: F821
    [str(ROOT / "platforms" / "desktop" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # anthropic is optional at runtime; excluding it here would break the
    # opt-in AI features, so it stays in.
    excludes=["tkinter", "matplotlib", "numpy", "PIL", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FastDailyJourneyWriter",
    debug=False,
    strip=False,
    upx=False,
    # A console window is deliberate: it is where the "日記存放在：..." line
    # and any error appears, and closing it is how you stop the server.
    console=True,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="FastDailyJourneyWriter",
)

# On macOS, wrap the collected folder as a .app so it can be double-clicked.
if sys.platform == "darwin":
    app = BUNDLE(  # noqa: F821
        coll,
        name="FastDailyJourneyWriter.app",
        bundle_identifier="com.chouyangen.fastdailyjourneywriter",
    )
