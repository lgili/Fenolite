# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The shared fixture of board slots (change c0167; c0168 to c0170 add their own items to copies of it).
Authored for Fenolite: no file, value, name or layout comes from any other project.

A 60 × 40 mm board without parts but one hole: a lone milled slot ``S1`` of 12 × 2 mm turned 30°; two
milled slots ``S2`` and ``S3`` of 12 × 2 mm that overlap in an L, sharing the round end about (45, 10) mm;
a round free hole ``H1`` of 3.2 mm (a drilled hole, a locked part of ``design.hole``); and one drawn
cut-out with four rounded corners (``cut-out 1``). The L is written as one merged ring with its arcs.
"""

from fenolite.dsl import Design, mm, shape

design = Design("slots")
design.board(mm(60), mm(40))
design.slot(mm(15), mm(10), length=mm(12), width=mm(2), rot=30, name="S1")
design.slot(mm(40), mm(10), length=mm(12), width=mm(2), name="S2")
design.slot(mm(45), mm(15), length=mm(12), width=mm(2), rot=90, name="S3")
design.hole("H1", mm(52), mm(32), drill=mm(3.2))
design.cutout(shape.rect(mm(8), mm(24), mm(12), mm(8), radius=mm(1)))
