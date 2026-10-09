# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``checks.placement.measure`` (capability placement, "Placement measures"; change c0113): lengths and
congestion computed by hand on authored layouts, and the cost on a synthetic layout of 600 parts. Every
value is round and invented for these tests."""

from __future__ import annotations

import json
import time

import pytest
from _placecheck import MM, Layout, at
from hypothesis import given, settings
from hypothesis import strategies as st

from fenolite.checks.placement import PlacementRules, judge, measure, spanning_tree
from fenolite.core.coords import Point
from fenolite.geometry import floor_sqrt
from fenolite.model.rules import PadSelection, ProximityRule


def by_hand() -> Layout:
    """A 20 mm × 10 mm board: three measured nets, a zone net, a one-pad net and a part off the board."""
    layout = Layout(20, 10)
    layout.part("P1", ("1", 2, 2, "A"), ("2", 1, 8, "B"), ("3", 0, 0, "C"), ("4", 4, 4, "GND"))
    layout.part("P2", ("1", 6, 2, "A"), ("2", 19, 8, "B"), ("3", 3, 4, "C"), ("4", 8, 4, "GND"))
    layout.part("P3", ("1", 6, 5, "A"), ("2", 9, 9, "N1"), ("3", 12, 4, "GND"), ("4", 15, 5, None))
    layout.part("P4", ("1", 30, 5, "A"))  # off the board, with a pad on A
    layout.zone("GND")
    return layout


def test_lengths_by_hand() -> None:
    design, pads = by_hand().build()
    found = measure(design, pads=pads)
    assert found.hpwl == 32 * MM and found.ratsnest == 30 * MM and found.nets == 3
    assert found.left_out == {"zone_nets": 1, "one_pad_nets": 1, "off_board": 1}
    assert [entry["net"] for entry in found.longest] == ["B", "A", "C"]  # 18, then 7 and 7 by name
    assert found.longest[0] == {"net": "B", "pads": 2, "hpwl": 18 * MM, "ratsnest": 18 * MM}
    assert found.longest[2] == {"net": "C", "pads": 2, "hpwl": 7 * MM, "ratsnest": 5 * MM}


def test_json_form_holds_integers_only() -> None:
    design, pads = by_hand().build()
    data = measure(design, pads=pads, pitch=400_000).to_json()
    assert list(data) == ["nets", "hpwl", "ratsnest", "longest", "left_out", "congestion"]
    assert isinstance(data["congestion"], dict)
    assert list(data["congestion"]) == ["cell", "pitch", "tracks_per_layer", "busiest", "layers_needed"]

    def walk(value: object) -> None:
        assert not isinstance(value, float), value
        if isinstance(value, dict):
            for key, item in value.items():
                assert isinstance(key, str)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(data)
    assert json.loads(json.dumps(data)) == data


def test_equal_inputs_give_equal_outputs_whatever_the_pad_order() -> None:
    design, pads = by_hand().build()
    assert measure(design, pads=pads, pitch=400_000) == measure(
        design, pads=tuple(reversed(pads)), pitch=400_000
    )


def test_the_reply_lists_five_nets_and_five_cells() -> None:
    layout = Layout(40, 40)
    for n in range(12):
        layout.part(f"A{n}", ("1", 1, 1 + 3 * n, f"N{n:02d}"))
        layout.part(f"B{n}", ("1", 39 - n, 1 + 3 * n, f"N{n:02d}"))
    design, pads = layout.build()
    found = measure(design, pads=pads, pitch=400_000)
    assert found.nets == 12 and len(found.longest) == 5
    assert [entry["net"] for entry in found.longest] == ["N00", "N01", "N02", "N03", "N04"]
    assert found.congestion is not None and len(found.congestion.busiest) == 5


def test_a_tie_between_two_spanning_trees_of_equal_length() -> None:
    """The corners of a 3 mm square: every spanning tree of three sides is a minimum one."""
    square = [at(0, 0), at(3, 0), at(3, 3), at(0, 3)]
    assert spanning_tree(square) == 9 * MM
    assert spanning_tree(list(reversed(square))) == 9 * MM
    assert spanning_tree([square[2], square[0], square[3], square[1]]) == 9 * MM
    assert spanning_tree([at(0, 0)]) == 0 and spanning_tree([]) == 0
    assert spanning_tree([at(1, 1), at(1, 1), at(4, 5)]) == 5 * MM  # a repeated position adds nothing


def test_each_edge_is_floored_to_the_nanometre() -> None:
    assert spanning_tree([Point(0, 0), Point(1, 1)]) == 1  # √2 nm
    assert spanning_tree([Point(0, 0), Point(1, 1), Point(2, 2)]) == 2


@settings(max_examples=60, deadline=None)
@given(st.lists(st.tuples(st.integers(0, 40_000), st.integers(0, 40_000)), min_size=2, max_size=9))
def test_the_tree_never_exceeds_a_chain_through_the_pads(raw: list[tuple[int, int]]) -> None:
    """The spanning tree is no longer than the path that joins the pads in the order given: both floor
    each of their edges, and a minimum tree is no longer than any path, edge by edge in sorted order."""
    points = [Point(x * 1_000, y * 1_000) for x, y in raw]
    chain = sum(
        floor_sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2) for a, b in zip(points, points[1:], strict=False)
    )
    assert spanning_tree(points) <= chain


# --- congestion -----------------------------------------------------------------------------------------


def two_cells() -> Layout:
    layout = Layout(4, 2)
    for n in range(10):
        layout.part(f"L{n}", ("1", 0.5, 1, f"N{n}"))
        layout.part(f"R{n}", ("1", 3.5, 1, f"N{n}"))
    return layout


def test_congestion_of_two_cells() -> None:
    design, pads = two_cells().build()
    found = measure(design, pads=pads, pitch=400_000).congestion
    assert found is not None
    assert found.cell == 2 * MM and found.pitch == 400_000 and found.tracks_per_layer == 5
    assert found.busiest == (
        {"x": 1 * MM, "y": 1 * MM, "tracks": 7},
        {"x": 3 * MM, "y": 1 * MM, "tracks": 7},
    )
    assert found.layers_needed == {2: 2}
    assert found.to_json()["layers_needed"] == {"2": 2}


def test_congestion_without_a_pitch() -> None:
    design, pads = two_cells().build()
    with_pitch = measure(design, pads=pads, pitch=400_000).congestion
    found = measure(design, pads=pads).congestion
    assert found is not None and with_pitch is not None
    assert found.tracks_per_layer is None and found.layers_needed is None and found.pitch is None
    assert found.busiest == with_pitch.busiest
    wide = measure(design, pads=pads, pitch=3 * MM).congestion  # a pitch larger than the cell
    assert wide is not None and wide.tracks_per_layer is None and wide.layers_needed is None


def test_congestion_is_none_without_a_board_box() -> None:
    layout = Layout(width=None)
    layout.part("A", ("1", 0, 0, "N"))
    layout.part("B", ("1", 9, 0, "N"))
    design, pads = layout.build()
    found = measure(design, pads=pads, pitch=400_000)
    assert found.congestion is None and found.hpwl == 9 * MM
    assert found.to_json()["congestion"] is None


def test_congestion_cell_of_a_board_longer_than_256_mm() -> None:
    layout = Layout(300, 100)
    layout.part("A", ("1", 10, 50, "N"))
    layout.part("B", ("1", 290, 50, "N"))
    design, pads = layout.build()
    found = measure(design, pads=pads, pitch=400_000).congestion
    assert found is not None
    assert found.cell == 2_344 * 1_000  # 300 mm / 128 = 2.34375 mm, rounded up to a whole micrometre
    assert found.cell * 128 >= 300 * MM > (found.cell - 1_000) * 128
    assert found.tracks_per_layer == found.cell // 400_000 == 5
    long_side = measure(Layout(100, 256).build()[0], pads=()).congestion
    assert long_side is not None and long_side.cell == 2 * MM  # exactly 128 cells of 2 mm


def test_congestion_of_a_net_whose_box_is_a_point() -> None:
    layout = Layout(10, 10)
    layout.part("A", ("1", 5, 5, "N"))
    layout.part("B", ("1", 5, 5, "N"))
    design, pads = layout.build()
    found = measure(design, pads=pads, pitch=400_000)
    assert found.nets == 1 and found.hpwl == 0 and found.ratsnest == 0
    assert found.congestion is not None and found.congestion.busiest == ()
    assert found.congestion.layers_needed == {}


def test_congestion_shares_follow_the_area_in_each_cell() -> None:
    """One net across three cells of a 6 mm × 2 mm board: its 5 mm of wire is spread over a box of 5 mm ×
    2 mm (grown to one cell in height), of which the cells hold 1.5, 2 and 1.5 mm: no cell reaches a
    track of 2 mm. Eight such nets give 12, 16 and 12 mm: 6, 8 and 6 tracks."""
    layout = Layout(6, 2)
    for n in range(8):
        layout.part(f"L{n}", ("1", 0.5, 1, f"N{n}"))
        layout.part(f"R{n}", ("1", 5.5, 1, f"N{n}"))
    design, pads = layout.build()
    found = measure(design, pads=pads, pitch=MM).congestion
    assert found is not None
    assert [(c["x"], c["tracks"]) for c in found.busiest] == [(3 * MM, 8), (1 * MM, 6), (5 * MM, 6)]
    assert found.tracks_per_layer == 2 and found.layers_needed == {3: 2, 4: 1}


# --- cost -----------------------------------------------------------------------------------------------


def test_synthetic_600_parts(capsys: pytest.CaptureFixture[str]) -> None:
    """The cost of ``judge`` and ``measure`` on a layout of 600 parts and 1 650 pads written here: 150
    four-pad parts, 150 three-pad parts and 300 two-pad parts on a 30 × 20 grid of 5 mm, 400 signal nets,
    two zone nets and 150 decoupling rules. The times are printed, not asserted: the yardstick board owns
    the budgets."""
    layout = Layout(160, 110)
    rules: list[ProximityRule] = []
    serial = 0
    for index in range(600):
        column, row = index % 30, index // 30
        x, y = 5 + 5 * column, 5 + 5 * row
        if index % 4 == 0:
            nets = [f"S{(serial + k) % 400:03d}" for k in range(2)]
            serial += 2
            layout.part(
                f"U{index}",
                ("1", x, y, nets[0]),
                ("2", x + 1, y, nets[1]),
                ("3", x + 1, y + 1, "VDD"),
                ("4", x, y + 1, "GND"),
                path=f"U{index}",
            )
        else:
            net = f"S{(serial * 7 + index) % 400:03d}"
            other = "VDD" if index % 4 == 1 else f"S{(index * 3) % 400:03d}"
            third = (("3", x, y + 1, "GND"),) if index % 4 == 3 else ()
            layout.part(f"C{index}", ("1", x, y, other), ("2", x + 1, y, net), *third, path=f"C{index}")
            if index % 4 == 1:
                rules.append(
                    ProximityRule(
                        f"dec{index}",
                        (PadSelection(f"C{index}", "1"),),
                        (PadSelection(f"U{index - 1}", "3"),),
                        3 * MM,
                    )
                )
    layout.zone("VDD")
    layout.zone("GND")
    design, pads = layout.build()
    assert len(design.board.footprints) == 600 and len(pads) == 1_650  # type: ignore[union-attr]
    start = time.perf_counter()
    report = judge(design, PlacementRules(tuple(rules)), pads=pads)
    judged = time.perf_counter() - start
    start = time.perf_counter()
    found = measure(design, pads=pads, pitch=400_000)
    measured = time.perf_counter() - start
    assert report.counts["near"]["judged"] == 150 and found.left_out["zone_nets"] == 2
    assert found.nets > 300 and found.congestion is not None
    with capsys.disabled():
        print(
            f"\nsynthetic_600: 600 parts, 1650 pads, 150 rules, {found.nets} measured nets: "
            f"judge {judged * 1000:.0f} ms, measure {measured * 1000:.0f} ms"
        )
