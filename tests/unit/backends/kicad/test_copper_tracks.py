# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Tracks and vias from intents (capability manual-copper: "Copper module", "Tracks from intents", "Nets of
script copper", "Single vias", "Copper uuids and ids"; change c0028). Hermetic."""

from __future__ import annotations

import dataclasses

import pytest
from _copper import at, built_blink, end, routed_intents, step, track, via
from _placed import Part, design_of, mm, pt

import fenolite.backends.kicad as kicad
from fenolite.backends.kicad import copper
from fenolite.backends.kicad.copper import copper_uuid, is_copper_uuid, resolve_copper
from fenolite.backends.kicad.frame import find_pads
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model import canonical
from fenolite.model.circuit import NetClass
from fenolite.model.design import Design


def _resolve(design: Design, *intents: object, unplaced: tuple[str, ...] = ()) -> tuple[Design, list[Issue]]:
    found: list[Issue] = []
    result = resolve_copper(design, intents, unplaced=unplaced, issues=found)  # type: ignore[arg-type]
    return result, found


def _net(design: Design, name: str) -> str:
    return next(net.id for net in design.circuit.nets if net.name == name)


def _copper(design: Design) -> tuple[list, list]:  # type: ignore[type-arg]
    assert design.board is not None
    return list(design.board.tracks), list(design.board.vias)


def _refused(design: Design, intent: object, code: str, *words: str) -> Issue:
    result, found = _resolve(design, intent)
    assert _copper(result) == ([], []), "an intent with an error creates nothing"
    (issue,) = found
    assert issue.code == code and all(word in issue.message for word in words), issue
    return issue


# -- paths


def test_pad_to_pad_path_through_a_via_step() -> None:
    blink = built_blink()
    p, q = at(36, 9), at(36, 14)
    intent = track("led_a", end("R1", 2), p, step(36, 14), end("D1", 2))
    result, found = _resolve(blink, intent)
    tracks, vias = _copper(result)
    assert found == []
    r1, d1 = find_pads(blink, "R1", 2)[0].position, find_pads(blink, "D1", 2)[0].position
    assert [(t.start, t.end, t.layer) for t in tracks] == [(r1, p, "F.Cu"), (p, q, "F.Cu"), (q, d1, "B.Cu")]
    assert [t.native_ids["kicad"] for t in tracks] == [copper_uuid("led_a", f"seg[{i}]") for i in range(3)]
    (through,) = vias
    assert (through.position, through.layers, through.via_type) == (q, ("F.Cu", "B.Cu"), "through")
    assert through.native_ids["kicad"] == copper_uuid("led_a", "via[2]")
    assert (through.diameter, through.drill) == (mm(0.6), mm(0.3))
    led_a = _net(blink, "LED_A")
    assert {item.net_id for item in (*tracks, through)} == {led_a} and all(t.width == mm(0.3) for t in tracks)
    for item in (*tracks, through):
        prefix = "via" if item is through else "trk"
        assert item.id == derived_id(prefix, "kicad", item.native_ids["kicad"]) and item.provenance is None


def test_path_shape_errors() -> None:
    blink = built_blink()
    _refused(blink, track("k", end("R1", 1)), "kicad.copper.bad-intent", "two elements")
    _refused(blink, track("k", step(1, 1), end("R1", 1)), "kicad.copper.bad-intent", "via step")


def test_repeated_key_and_later_intents_still_resolve() -> None:
    blink = built_blink()
    first = track("k", end("R1", 2), at(36, 9))
    again = track("k", end("R1", 2), at(35, 9))
    other = track("m", end("R1", 1), at(30, 9))
    result, found = _resolve(blink, first, again, other)
    assert [i.code for i in found] == ["kicad.copper.bad-intent"] and "earlier intent" in found[0].message
    assert [t.native_ids["kicad"] for t in _copper(result)[0]] == [
        copper_uuid("k", "seg[0]"),
        copper_uuid("m", "seg[0]"),
    ]


def test_zero_length_segment_keeps_its_locator_unused() -> None:
    blink = built_blink()
    r1 = find_pads(blink, "R1", 2)[0].position
    result, found = _resolve(blink, track("k", end("R1", 2), r1, at(36, 9)))
    (only,) = _copper(result)[0]
    assert found == [] and only.native_ids["kicad"] == copper_uuid("k", "seg[1]") and only.start == r1


def test_path_ending_in_a_via_step_and_points_only() -> None:
    blink = built_blink()
    result, found = _resolve(blink, track("k", at(5, 5), at(6, 5), step(7, 5), net="GND"))
    tracks, vias = _copper(result)
    assert found == [] and len(tracks) == 2 and vias[0].native_ids["kicad"] == copper_uuid("k", "via[2]")
    assert {t.net_id for t in tracks} == {_net(blink, "GND")}


# -- nearest pads


def _edge_cases(**nets: str) -> Design:
    return design_of(Part("J1", "Mini_Edge_Cases", 0, 0, nets={"1": "GND", **nets}), extra_nets=("VIN",))


def test_shared_number_nearest_pad_and_index() -> None:
    design = _edge_cases()
    near, found = _resolve(design, track("k", end("J1", 1), pt(5, 0)))
    assert found == [] and _copper(near)[0][0].start == pt(2, 0)
    indexed, _ = _resolve(design, track("k", end("J1", 1, index=0), pt(5, 0)))
    assert _copper(indexed)[0][0].start == pt(-2, 0)
    after_point, _ = _resolve(design, track("k", pt(-5, 0), end("J1", 1)))
    assert _copper(after_point)[0][0].end == pt(
        -2, 0
    )  # a later end takes the pad nearest to the element before


def test_nearest_pair_between_two_pad_ends() -> None:
    design = design_of(
        Part("J1", "Mini_Edge_Cases", 0, 0, nets={"1": "GND"}),
        Part("J2", "Mini_Edge_Cases", 10, 0, nets={"1": "GND"}),
    )
    result, found = _resolve(design, track("k", end("J1", 1), end("J2", 1)))
    (only,) = _copper(result)[0]
    assert found == [] and (only.start, only.end) == (pt(2, 0), pt(8, 0))
    # a tie goes to the earlier pads
    stacked = design_of(
        Part("J1", "Mini_Edge_Cases", 0, 0, nets={"1": "GND"}),
        Part("J2", "Mini_Edge_Cases", 0, 10, nets={"1": "GND"}),
    )
    tied, _ = _resolve(stacked, track("k", end("J1", 1), end("J2", 1)))
    assert (_copper(tied)[0][0].start, _copper(tied)[0][0].end) == (pt(-2, 0), pt(-2, 10))


def test_index_beyond_the_matches_and_unknown_pads() -> None:
    design = _edge_cases()
    _refused(design, track("k", end("J1", 1, index=2), pt(5, 0)), "kicad.copper.pad-not-found", "index 2")
    _refused(design, track("k", end("J1", 9), pt(5, 0)), "kicad.copper.pad-not-found", "J1", "'9'")
    _refused(design, track("k", end("J9", 1), pt(5, 0)), "kicad.copper.pad-not-found", "J9")


def test_component_paths_come_before_references() -> None:
    design = design_of(Part("J1", "Mini_Edge_Cases", 0, 0, nets={"1": "GND"}, path="io/J1"))
    by_path, found = _resolve(design, track("k", end("io/J1", 1), pt(5, 0)))
    by_ref, _ = _resolve(design, track("k", end("J1", 1), pt(5, 0)))
    assert found == [] and by_path == by_ref


# -- layers


def test_pad_without_copper_on_the_layer() -> None:
    issue = _refused(
        built_blink(),
        track("k", end("R1", 1), at(30, 9), layer="B.Cu"),
        "kicad.copper.layer-mismatch",
        "R1",
        "'1'",
    )
    assert "B.Cu" in issue.message and issue.where == "k" and issue.severity == "error"


def test_bad_layers() -> None:
    blink = built_blink()
    _refused(blink, track("k", end("R1", 1), at(30, 9), layer="In1.Cu"), "kicad.copper.bad-layer", "In1.Cu")
    stay = track("k", end("R1", 1), at(30, 9), step(30, 12, "F.Cu"), at(30, 14))
    _refused(blink, stay, "kicad.copper.bad-layer", "stays on F.Cu")
    _refused(blink, track("k", end("R1", 1), step(30, 9, "Edge.Cuts"), at(1, 1)), "kicad.copper.bad-layer")


def test_through_hole_pads_join_on_both_layers() -> None:
    result, found = _resolve(built_blink(), track("k", at(30, 26), end("D1", 1), layer="B.Cu", width=mm(0.5)))
    assert found == [] and _copper(result)[0][0].layer == "B.Cu"
    front, found = _resolve(built_blink(), track("k", at(30, 26), end("D1", 1), layer="F.Cu", width=mm(0.5)))
    assert found == [] and _copper(front)[0][0].layer == "F.Cu"


# -- sizes


def test_width_from_the_net_class() -> None:
    blink = built_blink()
    gnd = track("gnd", end("U1", 10), at(12, 26), width=None)
    led = track("led", end("R1", 2), at(36, 9), width=None)
    result, found = _resolve(blink, gnd, led)
    tracks, _ = _copper(result)
    assert [t.width for t in tracks] == [mm(0.5)] and tracks[0].net_id == _net(blink, "GND")
    (issue,) = found
    assert issue.code == "kicad.copper.size-missing" and "led" in issue.message and issue.where == "led"


def test_via_sizes_from_the_class_or_missing() -> None:
    cls = NetClass(id="ncl_00000000-0000-4000-8000-000000000001", name="VIAS", track_width=mm(0.25),
                   via_diameter=mm(0.8), via_drill=mm(0.4))  # fmt: skip
    design = design_of(
        Part("J1", "Mini_Edge_Cases", 0, 0, nets={"1": "GND"}), classes=(cls,), class_of={"GND": "VIAS"}
    )
    bare = track("k", end("J1", 1), pt(5, 0), step(0, 0, diameter=None, drill=None), width=None)
    bare = dataclasses.replace(bare, path=(*bare.path[:2], dataclasses.replace(bare.path[2], at=pt(6, 0))))  # type: ignore[arg-type]
    result, found = _resolve(design, bare)
    tracks, vias = _copper(result)
    assert (
        found == []
        and tracks[0].width == mm(0.25)
        and (vias[0].diameter, vias[0].drill) == (mm(0.8), mm(0.4))
    )
    _refused(built_blink(), via("v", at(20, 20), diameter=None), "kicad.copper.size-missing", "diameter")
    _refused(built_blink(), via("v", at(20, 20), drill=None), "kicad.copper.size-missing", "drill")


def test_bad_sizes() -> None:
    blink = built_blink()
    _refused(blink, track("k", end("R1", 1), at(30, 9), width=0), "kicad.copper.bad-size", "width")
    _refused(blink, via("v", at(20, 20), drill=mm(0.6)), "kicad.copper.bad-size", "not smaller")
    _refused(blink, via("v", at(20, 20), diameter=-1), "kicad.copper.bad-size")
    _refused(blink, via("v", at(20, 20), drill=0), "kicad.copper.bad-size")


# -- nets


def test_net_inferred() -> None:
    blink = built_blink()
    result, found = _resolve(blink, track("k", end("R1", 2), end("D1", 2), layer="F.Cu"))
    assert found == [] and {t.net_id for t in _copper(result)[0]} == {_net(blink, "LED_A")}


def test_two_nets_joined() -> None:
    issue = _refused(
        built_blink(), track("k", end("R1", 1), end("D1", 2)), "kicad.copper.net-conflict", "R1.1", "D1.2"
    )
    assert "LED_DRV" in issue.message and "LED_A" in issue.message


def test_pad_without_a_net_and_named_nets() -> None:
    blink = built_blink()
    _refused(blink, track("k", end("U1", 2), at(1, 1)), "kicad.copper.net-conflict", "U1.2", "no net")
    _refused(blink, track("k", end("R1", 1), at(30, 9), net="GND"), "kicad.copper.net-conflict", "GND")
    _refused(blink, track("k", end("R1", 1), at(30, 9), net="NOPE"), "kicad.copper.unknown-net", "NOPE")
    _refused(blink, track("k", at(1, 1), at(2, 1)), "kicad.copper.no-net")
    same, found = _resolve(blink, track("k", end("R1", 1), at(30, 9), net="LED_DRV"))
    assert found == [] and len(_copper(same)[0]) == 1


def test_end_at_a_staged_part() -> None:
    blink = built_blink()
    result, found = _resolve(blink, track("k", end("R1", 2), end("D1", 2)), unplaced=("D1",))
    assert _copper(result) == ([], [])
    (issue,) = found
    assert (issue.code, issue.severity) == ("kicad.copper.end-unplaced", "warning") and "D1" in issue.message


# -- single vias


def test_via_at_a_point() -> None:
    blink = built_blink()
    result, found = _resolve(blink, via("gnd_tie", pt(120, 110)))
    (only,) = _copper(result)[1]
    assert found == [] and only.position == pt(120, 110) and only.layers == ("F.Cu", "B.Cu")
    assert only.net_id == _net(blink, "GND") and only.native_ids["kicad"] == copper_uuid("gnd_tie", "via")


def test_via_net_rules() -> None:
    blink = built_blink()
    _refused(blink, via("v", at(20, 20), net=None), "kicad.copper.no-net", "via")
    _refused(blink, via("v", at(20, 20), net="NOPE"), "kicad.copper.unknown-net")


# -- the whole example


def test_pure_resolution() -> None:
    blink = built_blink()
    before = canonical.dump_texts(blink)
    one, two = resolve_copper(blink, routed_intents()), resolve_copper(blink, routed_intents())
    assert one == two and canonical.dump_texts(blink) == before
    tracks, vias = _copper(one)
    assert (len(tracks), len(vias)) == (11, 7)
    assert all(is_copper_uuid(item.native_ids["kicad"]) for item in (*tracks, *vias))


def test_idempotent() -> None:
    once = resolve_copper(built_blink(), routed_intents())
    found: list[Issue] = []
    assert resolve_copper(once, routed_intents(), issues=found) == once and found == []


@pytest.mark.parametrize("target", [9, 10])
def test_ids_survive_a_write_and_a_read(target: int) -> None:
    resolved = resolve_copper(built_blink(target), routed_intents())
    read = read_board(write_board(resolved, target=target).text, file="board.kicad_pcb")
    assert read.board is not None and resolved.board is not None
    for kind in ("tracks", "vias"):
        created = [(i.id, i.native_ids["kicad"]) for i in getattr(resolved.board, kind)]
        assert [(i.id, i.native_ids["kicad"]) for i in getattr(read.board, kind)] == created


def test_design_without_a_board_and_reexport() -> None:
    empty = Design.new("none", seed=0)
    bare = dataclasses.replace(empty, board=None)
    found: list[Issue] = []
    assert resolve_copper(bare, [via("v", at(1, 1))], issues=found) is bare
    assert [i.code for i in found] == ["kicad.copper.bad-intent"]
    assert kicad.resolve_copper is copper.resolve_copper and "resolve_copper" in kicad.__all__
