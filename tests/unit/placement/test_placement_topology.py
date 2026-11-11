# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored repeated-sheet and ambiguous physical binding fixtures for c0477."""

from dataclasses import replace

from fenolite.core.coords import Point, Size
from fenolite.model.board import FootprintInstance, Pad
from fenolite.model.circuit import Bus, BusMember, Circuit, Component, Net, Pin, PinRef
from fenolite.placement.topology import PadIdentity, resolved_incidences


def fixture():
    components = []
    nets = []
    footprints = []
    for side in ("left", "right"):
        component = Component(
            id=f"u-{side}",
            ref="U1",
            path=f"/{side}/U1",
            pins=(Pin(id=f"pin-{side}", number="V"),),
            pin_pad_map=(("V", "1"), ("V", "2")),
        )
        net = Net(id=f"rail-{side}", name="VCC", members=(PinRef(component.id, "V"),))
        pads = tuple(
            Pad(
                id=f"pad-{index}",
                number=number,
                shape="rect",
                size=Size(10, 10),
                position=Point(index * 20, 0),
                net_id=net.id,
            )
            for index, number in enumerate(("1", "1", "2"))
        )
        components.append(component)
        nets.append(net)
        footprints.append(
            FootprintInstance(
                id=f"fp-{side}",
                component_id=component.id,
                lib_ref="authored",
                position=Point(0, 0),
                pads=pads,
                net_ties=(("1", "2"),),
            )
        )
    return Circuit(components=tuple(components), nets=tuple(nets)), tuple(footprints)


def test_equal_labels_never_merge_instances_and_duplicate_pad_numbers_remain_distinct():
    circuit, footprints = fixture()
    rows = resolved_incidences(circuit, footprints)
    assert len(rows) == 2
    for side, row in zip(("left", "right"), rows, strict=True):
        assert row.net_id == f"rail-{side}"
        assert row.terminal == PinRef(f"u-{side}", "V")
        assert row.problem is None
        assert row.pads == tuple(PadIdentity(f"fp-{side}", f"pad-{i}") for i in range(3))
    reordered = replace(circuit, components=circuit.components[::-1], nets=circuit.nets[::-1])
    assert resolved_incidences(reordered, footprints[::-1]) == rows


def test_wrong_net_on_one_duplicate_pad_disqualifies_binding():
    circuit, (left, right) = fixture()
    left = replace(left, pads=(replace(left.pads[0], net_id="rail-right"), *left.pads[1:]))
    first, second = resolved_incidences(circuit, (left, right))
    assert first.problem == "pad_net_mismatch" and first.pads == ()
    assert second.problem is None and second.pads


def test_missing_mapped_pad_and_conflicting_net_membership_are_explicit():
    circuit, (left, right) = fixture()
    left = replace(left, pads=left.pads[:2])
    first, _ = resolved_incidences(circuit, (left, right))
    assert first.problem == "missing_pad"
    shared = replace(circuit.nets[1], members=(*circuit.nets[1].members, first.terminal))
    conflicted = replace(circuit, nets=(circuit.nets[0], shared))
    assert [r.problem for r in resolved_incidences(conflicted, (left, right))] == [
        "multiple_nets",
        "multiple_nets",
        None,
    ]


def test_board_positions_and_bus_metadata_do_not_replace_net_members():
    circuit, footprints = fixture()
    changed = replace(
        circuit,
        buses=(Bus(id="bus", name="TEST", members=(BusMember(0, "rail-left"), BusMember(1, "rail-right"))),),
    )
    moved = tuple(replace(f, position=Point(10, -20), rotation=90_000_000) for f in footprints)
    assert resolved_incidences(changed, moved) == resolved_incidences(circuit, footprints)
