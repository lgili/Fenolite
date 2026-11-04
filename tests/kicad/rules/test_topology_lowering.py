# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Dedicated topology conversion oracle, owed on KiCad 9.0.9 and 10.0.6 CI runners.

The existing length rule kind has its own evidence; this test checks the topology conversion and
carries the scoped clearance canary in both the passing and failing budget cases. KiCad 10.0.6 names
the net's two pads, not its track, in ``length_out_of_range`` (as ``_lengthbench.net_uuids`` expects),
so the timed items are every track and pad of CLK, and the violation must name the lowered rule.
"""

from dataclasses import replace

import _rulebench as rb
import _rulecases as rc
import pytest
from _topologybench import MM, bench

from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.lowering import lower_rules
from fenolite.backends.kicad.pcb import kicad_uuid
from fenolite.core.coords import Point

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("budget_fs,violates", [(118_000, False), (100_000, True)])
def test_topology_length_budget(budget_fs: int, violates: bool) -> None:
    canary = rb.builder().build()
    design = bench(max_fs=budget_fs)
    assert design.board is not None and design.rules is not None and canary.design.board is not None
    track = replace(design.board.tracks[0], end=Point(20 * MM, 0))
    fp = design.board.footprints[1]
    fp = replace(fp, position=track.end, pads=(replace(fp.pads[0], layers=("F.Cu",)),))
    footprints = (design.board.footprints[0], fp)
    design = replace(
        design,
        circuit=replace(design.circuit, nets=(*design.circuit.nets, *canary.design.circuit.nets)),
        board=replace(
            design.board,
            outline=canary.design.board.outline,
            layers=created_layers(2),
            tracks=(track, *canary.design.board.tracks),
            vias=(),
            footprints=footprints,
        ),
    )
    lowered = lower_rules(design.rules, target=rc.major(), design=design)
    assert not lowered.issues and "(constraint length" in lowered.text
    timed = (kicad_uuid(track), *(kicad_uuid(pad) for part in footprints for pad in part.pads))
    tested = rb.Bench(design, {**canary.items, "timed": timed})
    report = rb.require_canary(
        rb.drc(rc.runner(), tested, rb.with_scoped_canary(lowered.text), rc.major()), tested
    )
    found = [
        row
        for row in rb.violations_of(report, tested.uuids("timed"))
        if row.type == "length_out_of_range" and "'fenolite_0_topology_clk_delay'" in row.description
    ]
    assert bool(found) is violates, [(row.type, row.description) for row in report.violations]
