# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

from dataclasses import replace

import pytest
from _searchbench import MM, bench, point

from fenolite.backends.base import DesignRules
from fenolite.cli.placement_probes import probe_placement_intents
from fenolite.core.coords import Point
from fenolite.model.circuit import Net, NetClass
from fenolite.placement.intent import PlacementIntent
from fenolite.placement.topology import PadIdentity
from fenolite.routing.protocol import JobAttach

from .test_place_optimization_escape import LAYER, physical


@pytest.mark.parametrize("crossing", [False, True])
def test_gate_loop_requires_both_exact_connections_to_coexist(crossing):
    job, drive, _ = bench(start=Point(80_000, 5 * MM), end=Point(12 * MM - 80_000, 5 * MM), allowed=LAYER)
    a, b = (point(6, 2), point(6, 8)) if crossing else (point(2, 3), point(10, 3))
    pads = (
        physical(drive.a, "A", "net_sig"),
        physical(drive.b, "B", "net_sig"),
        physical(JobAttach("pad", "RETURN", a, LAYER, "C-1"), "C", "net_return"),
        physical(JobAttach("pad", "RETURN", b, LAYER, "D-1"), "D", "net_return"),
    )
    circuit = job.design.circuit
    default = NetClass(id="class_default", name="Default", track_width=100_000, clearance=100_000)
    design = replace(
        job.design,
        circuit=replace(
            circuit, nets=(*circuit.nets, Net(id="net_return", name="RETURN")), netclasses=(default,)
        ),
    )
    intent = PlacementIntent(
        "gate",
        "gate-loop",
        tuple(PadIdentity(pad.footprint_id, pad.pad_id) for pad in pads),
        "declared",
        "authored fixture",
        "v0",
        "check drive and return together",
        True,
        40 * MM,
    )
    before = design
    results = probe_placement_intents(
        design,
        DesignRules(design),
        pads,
        job.extra["outline"],
        (intent,),
        max_states=2000,
        pitch=MM,
    )
    assert tuple(row.key for row in results) == ("gate:drive", "gate:return")
    if crossing:
        assert results[0].status == "group-failed"
        assert results[1].status in ("no-room", "state-limit")
        assert all(row.length_nm is None for row in results)
    else:
        assert all(row.status == "found" and row.length_nm for row in results)
    assert design == before and not design.board.tracks
