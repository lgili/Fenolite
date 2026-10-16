# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The shared fixture of board slots with a drilled slot, for the conversions of change c0170. Authored for
Fenolite: no file, value, name or layout comes from any other project.

``design.py`` (c0167) unchanged, then one drilled slot ``D1`` of 1 × 3 mm turned 30° about (27, 33) mm, a
part of ``design.hole`` with a ``length``: KiCad drills it (the NPTH file) where the milled slots and the
cut-out reach no drill file. Converted to Altium and back to KiCad it must stay so (``H-K-CONV-SLOTS``).
"""

import runpy
from pathlib import Path

from fenolite.dsl import Design, mm

design = runpy.run_path(str(Path(__file__).with_name("design.py")))["design"]
assert isinstance(design, Design)
design.hole("D1", mm(27), mm(33), drill=mm(1), length=mm(3), rot=30)
