# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The open-connections bench for hermetic tests (change c0108): ``ob`` is
``tests/kicad/copper/_openbench.py`` and ``rb`` the builder ``tests/kicad/rules/_rulebench.py``, whose
folders are on the import path of the oracle tests only."""

from __future__ import annotations

import sys
from pathlib import Path

KICAD_TESTS = Path(__file__).resolve().parent / "kicad"
for _folder in (KICAD_TESTS, KICAD_TESTS / "rules", KICAD_TESTS / "copper"):
    if str(_folder) not in sys.path:
        sys.path.insert(0, str(_folder))

import _openbench as ob  # noqa: E402  # pyright: ignore[reportMissingImports]
import _rulebench as rb  # noqa: E402  # pyright: ignore[reportMissingImports]

__all__ = ["ob", "rb"]
