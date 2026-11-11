# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

from fenolite.geometry import BBox
from fenolite.placement.floorplan import BlockPort, BoundBlock, plan_block_regions
from fenolite.placement.regions import Region

REGIONS = (Region("left", BBox(0, 0, 10, 10)), Region("right", BBox(10, 0, 20, 10)))


def block(name, *connections):
    return BoundBlock(
        name,
        (),
        (),
        tuple(BlockPort(net, "", net, direction, kind, ()) for net, direction, kind in connections),
        True,
    )


def test_repeated_channels_coarsen_separately_despite_a_shared_power_rail():
    rail = ("pwr", "inout", "power")
    blocks = (
        block("A-drive", ("lane1", "out", "net"), rail),
        block("B-drive", ("lane2", "out", "net"), rail),
        block("C-receiver", ("lane2", "in", "net"), rail),
        block("D-receiver", ("lane1", "in", "net"), rail),
    )
    areas = {row.instance: 50 for row in blocks}
    plans = plan_block_regions(blocks, REGIONS, areas, {})
    assert plans.best == plans.coarsened
    assert not plans.coarsened.unplaced
    mapped = plans.coarsened.assignments
    assert mapped["A-drive"] == mapped["D-receiver"] != mapped["B-drive"] == mapped["C-receiver"]
    assert plans.coarsened.cut_weight == 1024 // 12
    assert plans.coarsened.cut_weight < plans.hierarchy.cut_weight
    assert plans == plan_block_regions(tuple(reversed(blocks)), tuple(reversed(REGIONS)), areas, {})


def test_feedback_is_condensed_but_directed_external_ports_preserve_orientation():
    feedback = (
        block("a", ("feedback", "in", "net"), ("next", "out", "net")),
        block("b", ("next", "in", "net"), ("feedback", "out", "net"), ("external", "out", "net")),
        block("c", ("external", "in", "net")),
    )
    areas = {"a": 40, "b": 40, "c": 40}
    planned = plan_block_regions(feedback, REGIONS, areas, {"c": frozenset({"right"})})
    assert planned.best.assignments == {"a": "left", "b": "left", "c": "right"}
    assert planned.best.reversed_direction_nm == 0 and planned.best.cut_weight == 1024
    forced = plan_block_regions(
        feedback,
        REGIONS,
        areas,
        {"a": frozenset({"right"}), "b": frozenset({"right"}), "c": frozenset({"left"})},
    )
    assert forced.best.reversed_direction_nm == 10


def test_overflow_is_explicit_when_a_region_is_full():
    blocks = (block("one"), block("two"))
    planned = plan_block_regions(
        blocks,
        REGIONS,
        {"one": 100, "two": 60},
        {"one": frozenset({"left"}), "two": frozenset({"left"})},
    )
    assert planned.best.assignments == {"one": "left"} and planned.best.unplaced == ("two",)
