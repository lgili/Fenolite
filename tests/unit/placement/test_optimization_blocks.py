# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

from dataclasses import replace
from functools import partial

import pytest

from fenolite.core.coords import Point
from fenolite.model.circuit import Module, Pin, PinRef, Port
from fenolite.placement.floorplan import BlockOrigin, BlockRequest, bind_blocks, search_block_placements
from fenolite.placement.optimization_contract import OptimizationBudget
from fenolite.placement.optimize import SearchJudgment
from fenolite.placement.topology import PadIdentity
from fenolite.reuse.blocklayout import BlockLayout, LayoutPart, apply_block_layout, nets_digest, parts_digest

from ._constrained_fixture import board, part


def bench():
    design = board(part("A", 10, 10), part("B", 18, 10))
    components = tuple(
        replace(
            component,
            path=f"filter/{component.ref}",
            lib_footprint_ref="authored",
            pins=(Pin(id=f"pin_{component.ref}", number="1"),),
        )
        for component in design.circuit.components
    )
    module = Module(id="module_filter", path="filter", block="test.filter", block_version="1.0.0")
    external = Port(
        id="port_input", name="input", owner=module.id, kind="net", direction="in", members={"signal": "a"}
    )
    first, second = design.circuit.nets
    design = replace(
        design,
        circuit=replace(
            design.circuit,
            components=components,
            modules=(module,),
            ports=(external,),
            nets=(
                replace(first, members=tuple(PinRef(component.id, "1") for component in components)),
                second,
            ),
        ),
    )
    layout = BlockLayout(
        module.block,
        module.block_version,
        parts_digest(design, "filter"),
        nets_digest(design, "filter"),
        "Apache-2.0",
        "INFERRED",
        {
            "A": LayoutPart(Point(0, 0), 0, "top", "authored"),
            "B": LayoutPart(Point(8, 0), 0, "top", "authored"),
        },
    )
    return (
        design,
        BlockRequest(
            "filter",
            partial(apply_block_layout, layout),
            (BlockOrigin(Point(10, 10)), BlockOrigin(Point(20, 10))),
        ),
        layout,
    )


def test_rigid_and_flexible_domains_preserve_physical_port_identity():
    design, request, _ = bench()
    (rigid,) = bind_blocks(design, (request,))
    (port,) = rigid.ports
    assert port.direction == "in" and port.net_id == "a"
    assert port.pads == (PadIdentity("A", "p_A"), PadIdentity("B", "p_B"))

    def prefer_mixed(poses, _complete):
        goal = {"A": 10, "B": 28}
        return SearchJudgment((sum(abs(pose.position.x - goal[pose.footprint_id]) for pose in poses),))

    options = {"input_sha256": "authored", "budget": OptimizationBudget(16, 4), "judge": prefer_mixed}
    first = search_block_placements((rigid,), {}, **options)
    second = search_block_placements(bind_blocks(design, (replace(request, rigid=False),)), {}, **options)
    assert first.candidates and first.candidates[0].score == (10,)
    assert all(row.candidate.poses in rigid.alternatives for row in first.candidates)
    assert (
        second.candidates[0].score == (0,) and second.candidates[0].candidate.poses not in rigid.alternatives
    )


def test_stale_and_shared_block_members_fail_before_search():
    design, request, layout = bench()
    stale = partial(apply_block_layout, replace(layout, parts_digest="sha256:old"))
    with pytest.raises(ValueError, match="stale"):
        bind_blocks(design, (replace(request, layout=stale),))
    with pytest.raises(ValueError, match="shared"):
        bind_blocks(design, (request, request))
    (fixed,) = bind_blocks(design, (request,), fixed=frozenset({"A"}))
    assert fixed.footprints == ("B",)
    assert len(fixed.alternatives) == 1 and fixed.alternatives[0][0].position == Point(18, 10)
    with pytest.raises(ValueError, match="conflict with fixed poses"):
        bind_blocks(design, (replace(request, origins=request.origins[1:]),), fixed=frozenset({"A"}))
