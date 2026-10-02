# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Template tests import ``_specs`` (here) and the drawing-sheet oracle's ``_expected``
(``tests/kicad/sheets``)."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for folder in (HERE, HERE.parents[1] / "kicad" / "sheets", HERE.parents[1] / "kicad"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
