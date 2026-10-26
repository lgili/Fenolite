# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The shared fixture of board slots with the drilled slots of change c0168, for the Altium document.
Authored for Fenolite: no file, value, name or layout comes from any other project.

``design.py`` (c0167) unchanged, then three drilled slots, parts of ``design.hole`` with a ``length`` that
the Altium document holds as free slot pads: a lone ``D1`` of 12 × 2 mm turned 30° about (27, 33) mm, and
``D2`` (10 × 2 mm about (38, 27) mm) and ``D3`` (10 × 2 mm turned 90° about (43, 32) mm), whose round ends
overlap in an L. The milled slots and the cut-out become board cut-out regions; the drilled slots stay
pads (``docs/altium.md``, "Outlines with arcs, and holes").
"""

import runpy
from pathlib import Path

from fenolite.dsl import Design, mm

design = runpy.run_path(str(Path(__file__).with_name("design.py")))["design"]
assert isinstance(design, Design)
design.hole("D1", mm(27), mm(33), drill=mm(2), length=mm(12), rot=30)
design.hole("D2", mm(38), mm(27), drill=mm(2), length=mm(10))
design.hole("D3", mm(43), mm(32), drill=mm(2), length=mm(10), rot=90)
