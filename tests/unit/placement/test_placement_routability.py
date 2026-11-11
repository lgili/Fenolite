# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

from fenolite.geometry import BBox
from fenolite.placement.routability import ChannelCut, ChannelDemand, estimate_channels


def test_wide_pair_cannot_use_two_disjoint_fragments_as_one_corridor():
    cut = ChannelCut("throat", "F.Cu", "x", 10, (0, 100))
    walls = {"F.Cu": (BBox(5, 35, 15, 65), BBox(8, 34, 12, 63))}
    group = ChannelDemand("DP/DN", ("throat", "throat"), 38, 2)
    wire = ChannelDemand("control", ("throat",), 20, 2)
    (measure,) = estimate_channels((cut,), walls, (group, wire), known_layers=frozenset({"F.Cu"}))
    assert measure.intervals == ((0, 34), (65, 100))
    assert measure.capacity_nm == 69 and measure.demand_nm == 62
    assert measure.unserved == ("DP/DN",) and measure.overflow_nm == 40


def test_direction_layer_and_zero_capacity_are_distinct_from_unknown():
    cuts = (
        ChannelCut("blocked", "F.Cu", "y", 5, (0, 20)),
        ChannelCut("other-face", "B.Cu", "y", 5, (0, 20)),
        ChannelCut("stackup", "In1.Cu", "y", 5, (0, 20)),
    )
    walls = {"F.Cu": (BBox(0, 4, 20, 6),)}
    requests = (
        ChannelDemand("known", ("blocked", "stackup"), 6, 2),
        ChannelDemand("unknown-width", ("other-face",), None, 2),
    )
    first, second, third = estimate_channels(cuts, walls, requests, known_layers=frozenset({"F.Cu", "B.Cu"}))
    assert first.capacity_nm == 0 and first.overflow_nm == 8
    assert second.capacity_nm == 20 and second.overflow_nm is None
    assert second.unknown == ("unknown-width",)
    assert third.capacity_nm is None and third.unknown == ("layer:In1.Cu",)
