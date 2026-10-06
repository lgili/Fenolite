# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A blink variant with one ``design.rules.rule()`` call per rule kind of change c0071, shared by the
hermetic build test and the KiCad oracle. The values are round numbers chosen for Fenolite's tests, not
requirements of any standard."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLINK_DIR = ROOT / "examples" / "blink_2layer"
BOARD_RULES = (
    "from fenolite.dsl import select\n"
    'design.rules.rule("pitch", "hole_to_hole", min=mm(0.3))\n'
    'design.rules.rule("hole gap", "hole_clearance", where=select.netclass("PWR"), min=mm(0.3))\n'
    'design.rules.rule("ring", "annular_width", where=select.item("via"), min=mm(0.12))\n'
    'both = select.ref("U1") | select.ref("R1")\n'
    'design.rules.rule("court", "courtyard_clearance", where=both, min=mm(0))\n'
    'design.rules.rule("silk", "silk_clearance", min=mm(0.05), severity="warning")\n'
)
"""Five rules that both majors check."""
CREEPAGE_RULE = (
    'design.rules.rule("mains", "creepage", where=select.net("VIN"), between=select.net("GND"), min=mm(1))\n'
)
"""The rule that only KiCad 10 checks."""
NEW_KIND_NAMES = ("pitch", "hole_gap", "ring", "court", "silk", "mains")
"""The slugs of the six rules, as the lowered names end."""


def script(tmp_path: Path, append: str) -> Path:
    """A copy of the blink example under ``tmp_path`` whose script ends with ``append``."""
    root = tmp_path / "repo"
    shutil.copytree(BLINK_DIR, root / "examples" / "blink_2layer")
    shutil.copytree(ROOT / "tests" / "data" / "libs", root / "tests" / "data" / "libs")
    path = root / "examples" / "blink_2layer" / "design.py"
    path.write_text(path.read_text(encoding="utf-8") + append, encoding="utf-8")
    return path


__all__ = ["BOARD_RULES", "CREEPAGE_RULE", "NEW_KIND_NAMES", "script"]
