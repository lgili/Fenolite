# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Executable authored regions design for the Part S catalogue (c0168).

This reproduces the Fenolite-authored c0167 slot fixture and c0168 drilled slots
using only the DSL. Evaluation creates a Design; it neither writes CAD files nor
changes the writer gate. The formal kit loader reads its separately pinned
regions/clearance/gate-off CAD inputs without executing or regenerating them.
See PROVENANCE.md for the historical writer inputs and criteria.md for S1–S8.
"""

from fenolite.dsl import Design, mm, shape

design = Design("slots")
design.board(mm(60), mm(40))
design.slot(mm(15), mm(10), length=mm(12), width=mm(2), rot=30, name="S1")
design.slot(mm(40), mm(10), length=mm(12), width=mm(2), name="S2")
design.slot(mm(45), mm(15), length=mm(12), width=mm(2), rot=90, name="S3")
design.hole("H1", mm(52), mm(32), drill=mm("3.2"))
design.cutout(shape.rect(mm(8), mm(24), mm(12), mm(8), radius=mm(1)))
design.hole("D1", mm(27), mm(33), drill=mm(2), length=mm(12), rot=30)
design.hole("D2", mm(38), mm(27), drill=mm(2), length=mm(10))
design.hole("D3", mm(43), mm(32), drill=mm(2), length=mm(10), rot=90)
