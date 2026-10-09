# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pair bench of the feasibility gate of change c0110 (design, Context, "pair bench"; Decision 1).

Authored for Fenolite with round values. A 50 mm by 30 mm board of four copper layers with two headers of
1 by 8 positions at 1.27 mm, 40 mm apart; the pairs ``USB_P``/``USB_N`` and ``LV0_P``/``LV0_N`` and the four
single nets ``S1`` to ``S4`` cross between them. The pair nets are in the class ``DP`` (0.2 mm width, 0.15 mm
clearance, pair width 0.2 mm and gap 0.15 mm), the single nets in ``SIG`` (the same sizes). Each pair has
c0104's limits (``pair(gap_min=0.13mm, gap_max=0.17mm, uncoupled_max=6mm, skew_max=0.1mm)``), and the board
minimum width is 0.15 mm, below the pair width (Context, measurement 3).

The task list of c0110 names this file ``_pairbench.py``; that name is taken by the rules bench of c0104
(``tests/kicad/rules/_pairbench.py``), which shares the import path of a whole run, so this one is
``_routepairbench.py``.
"""

from __future__ import annotations

from _gateparts import header, symbol_for

from fenolite.dsl import Design, DiffPair, Net, Part, connect, mm

NAME = "pairbench"
PAIRS = (("USB_P", "USB_N"), ("LV0_P", "LV0_N"))
SINGLES = ("S1", "S2", "S3", "S4")
NETS = (*(name for pair in PAIRS for name in pair), *SINGLES)
WIDTH = 200_000
GAP = 150_000
CLEARANCE = 150_000
VIA = (600_000, 300_000)
LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def bench_design() -> Design:
    """The pair bench as a design script gives it."""
    design = Design(NAME)
    design.board(mm(50), mm(30), copper=4)
    fp = header(1, 8)
    design.add_footprint(fp)
    symbol = symbol_for(fp, [str(n) for n in range(1, 9)], "J")
    nets = {name: Net(name) for name in NETS}
    j1 = Part("J1", symbol.lib_id, footprint=fp.lib_id, value="LEFT")
    j2 = Part("J2", symbol.lib_id, footprint=fp.lib_id, value="RIGHT")
    design.add(symbol, j1, j2)
    for index, name in enumerate(NETS, start=1):
        connect(nets[name], j1[index], j2[index])
    pair_nets = tuple(nets[name] for pair in PAIRS for name in pair)
    design.rules.netclass(
        "DP", clearance=mm(0.15), track_width=mm(0.2), via_diameter=mm(0.6), via_drill=mm(0.3),
        diff_pair_width=mm(0.2), diff_pair_gap=mm(0.15), nets=pair_nets,
    )  # fmt: skip
    design.rules.netclass(
        "SIG", clearance=mm(0.15), track_width=mm(0.2), via_diameter=mm(0.6), via_drill=mm(0.3),
        nets=tuple(nets[name] for name in SINGLES),
    )  # fmt: skip
    design.rules.minimum(track_width=mm(0.15), clearance=mm(0.15))
    for positive, negative in PAIRS:
        pair = DiffPair(nets[positive], nets[negative], name=positive[:-2])
        design.rules.pair(pair, gap_min=mm(0.13), gap_max=mm(0.17), uncoupled_max=mm(6), skew_max=mm(0.1))
    j1.place(mm(5), mm(15))
    j2.place(mm(45), mm(15))
    return design


__all__ = ["CLEARANCE", "GAP", "LAYERS", "NAME", "NETS", "PAIRS", "SINGLES", "VIA", "WIDTH", "bench_design"]
