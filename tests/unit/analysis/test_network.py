# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper network of a power path and its active part (capability board-analyses, "Power path
network")."""

from __future__ import annotations

import dataclasses
import math
import random
from fractions import Fraction

from _analysis import MM, at, box
from _coppercheck import Copper, disc_entry, ident
from _power import branch, strip, two_strips, via_array

from fenolite.analysis.copper import net_copper
from fenolite.analysis.network import PathNetwork, net_pieces, path_network
from fenolite.analysis.views import arc_length
from fenolite.core.coords import Point
from fenolite.model.board import Graphic


def codes(network: PathNetwork) -> list[str]:
    return [found.code for found in network.issues]


def by_where(network: PathNetwork) -> dict[str, tuple[bool, bool]]:
    return {element.where: (element.active, element.series) for element in network.elements}


def test_branch_splits_the_track_and_leaves_the_branch_out() -> None:
    """Scenario "A branch to a capacitor is off the path"."""
    design, pads = branch()
    network = path_network(design, pads=pads, start=("J1-1",), end=("U1-1",))
    assert network.net == "VBUS" and not network.issues
    assert by_where(network) == {"/main[0]": (True, True), "/main[1]": (True, True), "/side": (False, False)}
    lengths = {element.where: element.length_nm for element in network.elements}
    assert lengths == {"/main[0]": 10 * MM, "/main[1]": 10 * MM, "/side": 5 * MM}
    assert all(element.kind == "track" and element.layer == "F.Cu" for element in network.elements)
    assert not network.regions and not network.groups


def test_two_layers_in_parallel_joins_both_regions() -> None:
    """Scenario "Two layers in parallel"."""
    design, pads = two_strips()
    network = path_network(design, pads=pads, start=("J1-1",), end=("U1-1",))
    assert not network.issues
    fills = [element for element in network.elements if element.kind == "fill"]
    assert [(e.layer, e.active, e.series) for e in fills] == [("F.Cu", True, False), ("B.Cu", True, False)]
    assert [len(use.active_ports) for use in network.regions] == [2, 2]
    assert [sorted(port.where for port in use.ports) for use in network.regions] == [["J1-1", "U1-1"]] * 2


def test_a_via_array_groups_its_vias() -> None:
    """Scenario "A via array is one group"."""
    design, pads = via_array()
    network = path_network(design, pads=pads, start=("J1-1",), end=("U1-1",))
    assert not network.issues
    (group,) = network.groups
    assert (
        len(group.vias) == 8 and group.layers == ("F.Cu", "B.Cu") and group.pieces == ("/bottom#0", "/top#0")
    )
    (element,) = [item for item in network.elements if item.kind == "via-group"]
    assert element.active and element.series and element.layer == "F.Cu/B.Cu" and element.where == "/via[0]+7"
    top, bottom = network.regions
    assert len(top.ports) == 4 and len(bottom.ports) == 2
    active = sorted(top.ports[index].where for index in top.active_ports)
    assert len(active) == 2 and "J1-1" in active and "C1-1" not in active and "C2-1" not in active
    assert all(e.active and e.series for e in network.elements if e.kind == "fill")


def test_unknown_pad_and_pads_of_two_nets() -> None:
    """Scenario "Unknown pad"."""
    design, pads = branch()
    network = path_network(design, pads=pads, start=("J1-1",), end=("U9-1",))
    assert not network.elements and codes(network) == ["analysis.path-unmatched"]
    assert "U9-1" in network.issues[0].message
    assert codes(path_network(design, pads=None, start=("J1-1",), end=("U1-1",))) == [
        "analysis.path-unmatched"
    ]
    made = Copper()
    made.pad("J1", "1", "A", disc_entry(0, 0, MM))
    made.pad("U1", "1", "B", disc_entry(5 * MM, 0, MM))
    made.pad("U2", "1", None, disc_entry(9 * MM, 0, MM))
    two = path_network(made.build(), pads=tuple(made.pads), start=("J1-1",), end=("U1-1",))
    assert codes(two) == ["analysis.path-unmatched"] and "2 net(s)" in two.issues[0].message
    none = path_network(made.build(), pads=tuple(made.pads), start=("U2-1",), end=("U2-1",))
    assert codes(none) == ["analysis.path-unmatched"]


def test_an_open_path_warns() -> None:
    made = Copper()
    made.track("P", at(0, 0), at(8, 0), width=MM)
    made.track("P", at(12, 0), at(20, 0), width=MM)
    made.pad("J1", "1", "P", disc_entry(0, 0, MM))
    made.pad("U1", "1", "P", disc_entry(20 * MM, 0, MM))
    network = path_network(made.build(), pads=tuple(made.pads), start=("J1-1",), end=("U1-1",))
    assert codes(network) == ["analysis.path-open"] and "J1-1" in network.issues[0].message
    assert not any(element.active for element in network.elements)


def test_shapes_are_those_of_net_copper() -> None:
    for design, pads in (branch(), via_array(), strip()):
        shapes = net_copper(design, pads=pads).by_net["VBUS"]
        pieces = net_pieces(shapes)
        assert [shape for shape in shapes if shape.kind != "fill"] == list(pieces)
        network = path_network(design, pads=pads, start=("J1-1",), end=("U1-1",))
        used = {entity for element in network.elements for entity in element.entity_ids}
        used |= {via for group in network.groups for via in group.vias}
        assert {shape.entity_id for shape in pieces if shape.kind in ("track", "arc", "via")} <= used
        named = {name for use in network.regions for port in use.ports for name in port.where.split("+")}
        if network.regions:
            assert {shape.where for shape in pieces if shape.kind == "pad"} <= named


def test_a_copper_graphic_is_counted_not_used() -> None:
    design, pads = branch()
    assert design.board is not None
    line = Graphic(id=ident("gra", 1), kind="line", layer="F.Cu", points=(at(0, 1), at(20, 1)), width=MM)
    silk = Graphic(id=ident("gra", 2), kind="line", layer="F.SilkS", points=(at(0, 2), at(20, 2)), width=MM)
    drawn = dataclasses.replace(design, board=dataclasses.replace(design.board, graphics=(line, silk)))
    network = path_network(drawn, pads=pads, start=("J1-1",), end=("U1-1",))
    (found,) = network.issues
    assert (
        found.code == "analysis.item-unsupported"
        and found.where == "graphic"
        and "1 graphic" in found.message
    )


def test_crossing_tracks_join_and_split_each_other() -> None:
    made = Copper()
    made.track("P", at(0, 0), at(10, 0), width=MM, locator="/h")
    made.track("P", at(5, -5), at(5, 5), width=MM, locator="/v")
    made.pad("J1", "1", "P", disc_entry(0, 0, MM))
    made.pad("U1", "1", "P", disc_entry(5 * MM, 5 * MM, MM))
    network = path_network(made.build(), pads=tuple(made.pads), start=("J1-1",), end=("U1-1",))
    assert not network.issues
    assert by_where(network) == {
        "/h[0]": (True, True), "/h[1]": (False, False), "/v[0]": (False, False), "/v[1]": (True, True),
    }  # fmt: skip


def test_two_tracks_in_parallel_are_active_and_not_in_series() -> None:
    made = Copper()
    made.track("P", at(0, 0), at(10, 0), width=MM, locator="/a")
    made.track("P", at(0, 0), at(5, 4), width=MM, locator="/b")
    made.track("P", at(5, 4), at(10, 0), width=MM, locator="/c")
    made.track("P", at(10, 0), at(15, 0), width=MM, locator="/d")
    made.pad("J1", "1", "P", disc_entry(0, 0, MM))
    made.pad("U1", "1", "P", disc_entry(15 * MM, 0, MM))
    network = path_network(made.build(), pads=tuple(made.pads), start=("J1-1",), end=("U1-1",))
    assert by_where(network) == {
        "/a": (True, False),
        "/b": (True, False),
        "/c": (True, False),
        "/d": (True, True),
    }
    assert {e.where: e.length_nm for e in network.elements}["/b"] == 6_403_124


def test_a_track_into_a_pour_is_cut_and_its_inner_part_is_a_port() -> None:
    made = Copper()
    pour = box(10, -5, 30, 5)
    made.zone("P", pour, fills=(pour,), locator="/pour")
    made.track("P", at(0, 0), at(15, 0), width=MM, locator="/feed")
    made.via("P", at(25, 0), locator="/via")
    made.track("P", at(25, 0), at(25, 10), width=MM, layer="B.Cu", locator="/back")
    made.pad("J1", "1", "P", disc_entry(0, 0, MM))
    made.pad("U1", "1", "P", disc_entry(25 * MM, 10 * MM, MM, "B.Cu"), layers=("B.Cu",))
    network = path_network(made.build(), pads=tuple(made.pads), start=("J1-1",), end=("U1-1",))
    assert not network.issues
    feed = next(element for element in network.elements if element.where == "/feed")
    assert feed.length_nm == 10 * MM and feed.active and feed.series
    (use,) = network.regions
    assert sorted(port.where for port in use.ports) == ["/feed", "/via"] and len(use.active_ports) == 2
    (group,) = network.groups
    assert group.vias and group.layers == ("F.Cu", "B.Cu") and group.pieces == ("/back", "/pour#0")
    assert all(element.active and element.series for element in network.elements)


def test_an_arc_is_one_piece_with_a_length_band() -> None:
    made = Copper()
    made.arc("P", at(0, 0), at(5, 5), at(10, 0), width=MM)
    made.pad("J1", "1", "P", disc_entry(0, 0, MM))
    made.pad("U1", "1", "P", disc_entry(10 * MM, 0, MM))
    network = path_network(made.build(), pads=tuple(made.pads), start=("J1-1",), end=("U1-1",))
    (arc,) = network.elements
    assert arc.kind == "arc" and arc.active and arc.series and arc.length_nm is not None
    half_circle = 15_707_963  # π · 5 mm
    assert arc.length_nm <= half_circle <= arc.length_nm + arc.length_band
    assert arc.length_band < 200_000


def test_arc_length_bound_on_a_sweep_and_on_generated_arcs() -> None:
    """``H-G-AN-ARCLEN``: a chord ``c`` with sagitta ``s`` spans an arc of at most ``c + 4·s²/c``.

    With ``u`` a quarter of the chord's angle and ``R`` the radius, ``c = 2R·sin 2u``, ``s = R·(1 − cos 2u)``
    and the arc is ``4R·u``, so the claim is ``2u/sin 2u − 1 ≤ tan² u``, that is ``u ≤ tan u`` after
    ``sin 2u·(1 + tan² u) = 2·tan u``. The sweep checks it up to a quarter turn with rational bounds: a
    partial sum of the series of the tangent, all of whose terms are positive, is below the tangent."""
    for step in range(1, 786):  # u = step / 1000, up to π/4
        u = Fraction(step, 1000)
        below_tan = u + u**3 / 3 + 2 * u**5 / 15 + 17 * u**7 / 315
        assert u <= below_tan, step
        value = step / 1000
        assert 2 * value / math.sin(2 * value) - 1 <= math.tan(value) ** 2 * (1 + 1e-12), step
    rng = random.Random(20261008)
    checked = 0
    while checked < 300:
        radius = rng.randint(300_000, 40 * MM)
        first, sweep = rng.uniform(0, 2 * math.pi), rng.uniform(0.05, 1.9 * math.pi)
        points = [
            Point(
                round(radius * math.cos(first + part * sweep)), round(radius * math.sin(first + part * sweep))
            )
            for part in (0, 0.5, 1)
        ]
        made = Copper()
        try:
            arc = made.arc("P", points[0], points[1], points[2], width=250_000)
        except Exception:
            continue
        made.pad("J1", "1", "P", disc_entry(points[0].x, points[0].y, 300_000))
        made.pad("U1", "1", "P", disc_entry(points[2].x, points[2].y, 300_000))
        network = path_network(made.build(), pads=tuple(made.pads), start=("J1-1",), end=("U1-1",))
        parts = [element for element in network.elements if element.kind == "arc"]
        if not parts:
            continue
        low = sum(element.length_nm or 0 for element in parts)
        high = low + sum(element.length_band for element in parts)
        exact = arc_length(arc)
        assert low - 1 <= exact <= high + 1, (radius, sweep, low, exact, high)
        assert high - low <= max(2_000, exact // 100), (radius, sweep, high - low)
        checked += 1
