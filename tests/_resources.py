# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Where optional external resources live on this machine (KiCad, its libraries, the corpus)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

MACOS_KICAD = Path("/Applications/KiCad/KiCad.app/Contents")
LIB_ENV = ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD10_3DMODEL_DIR")
CORPUS_HINT = "run: uv run python tools/corpus_fetch.py"


def corpus_cache_dir() -> Path:
    override = os.environ.get("FENOLITE_CORPUS_CACHE")
    return Path(override) if override else Path.home() / ".cache" / "fenolite" / "corpus"


def kicad_library_dirs() -> list[Path]:
    """Official KiCad library folders available here: env overrides first, then the macOS app."""
    dirs = [Path(os.environ[v]) for v in LIB_ENV if os.environ.get(v)]
    if not dirs:
        support = MACOS_KICAD / "SharedSupport"
        dirs = [support / "footprints", support / "symbols", support / "3dmodels"]
    return [d for d in dirs if d.is_dir()]


def kicad_cli() -> str | None:
    override = os.environ.get("FENOLITE_KICAD_CLI")
    if override and Path(override).is_file():
        return override
    found = shutil.which("kicad-cli")
    bundled = MACOS_KICAD / "MacOS" / "kicad-cli"
    return found or (str(bundled) if bundled.is_file() else None)
