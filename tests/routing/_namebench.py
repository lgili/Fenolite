# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The name bench of the feasibility gate of change c0110 (design, Context, "name bench"; measurement 4).

Authored for Fenolite with round values. A 40 mm by 25 mm board of four copper layers with two headers
of 1 by 10 positions at 1.27 mm, 30 mm apart, joined by five pairs whose names KiCad pairs (c0104):
``A_P``/``A_N``, ``B+``/``B-``, ``C_P0``/``C_N0``, ``DP1``/``DN1`` and ``E_DP``/``E_DN``, all in the class
``DP`` with a pair width of 0.25 mm and a gap of 0.2 mm. The gate records which of them KiCadRoutingTools
routes coupled (``krt-pair-names``, ``H-K-KRT-PAIRNAMES``).
"""

from __future__ import annotations

from _gateparts import header, symbol_for

from fenolite.dsl import Design, Net, Part, connect, mm

NAME = "namebench"
PAIRS = (("A_P", "A_N"), ("B+", "B-"), ("C_P0", "C_N0"), ("DP1", "DN1"), ("E_DP", "E_DN"))
NETS = tuple(name for pair in PAIRS for name in pair)
WIDTH = 250_000
GAP = 200_000
CLEARANCE = 200_000
VIA = (600_000, 300_000)
LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def bench_design() -> Design:
    """The name bench as a design script gives it."""
    design = Design(NAME)
    design.board(mm(40), mm(25), copper=4)
    fp = header(1, 10)
    design.add_footprint(fp)
    symbol = symbol_for(fp, [str(n) for n in range(1, 11)], "J")
    j1 = Part("J1", symbol.lib_id, footprint=fp.lib_id, value="LEFT")
    j2 = Part("J2", symbol.lib_id, footprint=fp.lib_id, value="RIGHT")
    design.add(symbol, j1, j2)
    nets = {name: Net(name) for name in NETS}
    for index, name in enumerate(NETS, start=1):
        connect(nets[name], j1[index], j2[index])
    design.rules.netclass(
        "DP", clearance=mm(0.2), track_width=mm(0.25), via_diameter=mm(0.6), via_drill=mm(0.3),
        diff_pair_width=mm(0.25), diff_pair_gap=mm(0.2), nets=tuple(nets.values()),
    )  # fmt: skip
    design.rules.minimum(track_width=mm(0.15), clearance=mm(0.15))
    j1.place(mm(5), mm(12.5))
    j2.place(mm(35), mm(12.5))
    return design


__all__ = ["CLEARANCE", "GAP", "LAYERS", "NAME", "NETS", "PAIRS", "VIA", "WIDTH", "bench_design"]
