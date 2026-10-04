# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Zone settings are written (capability kicad-file-backend, "Zone settings are written"; change
c0031): created zones in KiCad's new-zone form per target, read zones only where the model changed."""

from __future__ import annotations

import dataclasses

import pytest
from _boards import (
    CREATED_HATCH_SETTINGS,
    FIXTURE,
    SQUARE,
    ZONE_SETTINGS,
    board,
    created_board,
    mm,
    square,
    zone,
)

from fenolite.backends.kicad import zones
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import (
    CANONICAL_ORDER,
    FLOOR_HEADS,
    POSITIONAL,
    read_board,
    write_board,
)
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, load, parse, tree_equal, walk
from fenolite.backends.kicad.versions import FileKind, LossyWriteError, check_emittable
from fenolite.core.errors import Issue
from fenolite.model.board import Zone, ZoneFill, ZoneSettings
from fenolite.model.circuit import Circuit, Net
from fenolite.model.design import Design

ZONE_ID = "zon_00000000-0000-4000-8000-000000000001"
NET_ID = "net_00000000-0000-4000-8000-000000000001"
POUR = ZoneSettings(clearance=300_000, connection="solid", thermal_gap=400_000, thermal_spoke_width=350_000)
ZONE_NAMES = (
    "mode", "smoothing", "radius", "island_removal_mode", "island_area_min", "hatch_thickness", "hatch_gap",
    "hatch_orientation", "hatch_smoothing_level", "hatch_smoothing_value", "hatch_border_algorithm",
    "hatch_min_hole_area",
)  # fmt: skip


def created(zone: Zone) -> Design:
    design = Design.new("zones", seed=1)
    assert design.board is not None
    board = dataclasses.replace(design.board, layers=created_layers(2), zones=(zone,))
    return dataclasses.replace(design, circuit=Circuit(nets=(Net(id=NET_ID, name="GND"),)), board=board)


def pour(**changes: object) -> Zone:
    base = Zone(id=ZONE_ID, outline=square(0, 0, 10, 10), layers=("F.Cu",), net_id=NET_ID, settings=POUR)
    return dataclasses.replace(base, **changes)  # type: ignore[arg-type]


def written_zone(design: Design, target: int, index: int = 0) -> Node:
    return parse(write_board(design, target=target).text).nodes("zone")[index]


def between(zone: Node, first: str, last: str) -> str:
    """The children of ``zone`` after its ``first`` child and before its ``last`` child, as text."""
    names = [c.name if isinstance(c, Node) else "" for c in zone.children]
    start, end = names.index(first) + 1, names.index(last)
    return " ".join(dumps(c, style="compact") for c in zone.children[start:end])


def heads(node: Node) -> list[str]:
    return [c.name for c in node.children if isinstance(c, Node)]


# -- created zones


def test_created_zone_for_target_10() -> None:
    zone = written_zone(created(pour()), 10)
    assert between(zone, "uuid", "polygon") == (
        "(hatch edge 0.5) (connect_pads yes (clearance 0.3)) (min_thickness 0.25)"
        " (fill (thermal_gap 0.4) (thermal_bridge_width 0.35) (island_removal_mode 0))"
    )


def test_created_zone_for_target_9() -> None:
    zone = written_zone(created(pour()), 9)
    assert between(zone, "uuid", "polygon") == (
        "(hatch edge 0.5) (connect_pads yes (clearance 0.3)) (min_thickness 0.25)"
        " (filled_areas_thickness no) (fill (thermal_gap 0.4) (thermal_bridge_width 0.35))"
    )


def test_created_zone_order_and_lock() -> None:
    zone = pour(
        name="GND", priority=2, locked=True, fills=(ZoneFill("F.Cu", square(1, 1, 9, 9)),), filled=True
    )
    for target in (9, 10):
        node = written_zone(created(zone), target)
        order = [h for h in CANONICAL_ORDER["zone"] if h in heads(node)]
        assert heads(node) == order
        net_heads = ["net", "net_name"] if target == 9 else ["net"]
        assert heads(node)[: len(net_heads) + 2] == [*net_heads, "locked", "layer"]
        assert node.find("locked") == parse("(locked yes)")
        tail = ["fill", "polygon", "filled_polygon"]
        assert heads(node)[-len(tail) :] == tail
        assert heads(node)[-len(tail) - 1] == ("filled_areas_thickness" if target == 9 else "min_thickness")
        assert (node.find("filled_areas_thickness") is not None) == (target == 9)


def test_created_fill_flag_follows_the_model() -> None:
    filled = pour(fills=(ZoneFill("F.Cu", square(1, 1, 9, 9)),), filled=True)
    fill = written_zone(created(filled), 9).find("fill")
    assert fill is not None and fill.children[0] == Atom.symbol("yes")
    # fill polygons alone do not set the flag: it is the model's own value
    unflagged = written_zone(created(dataclasses.replace(filled, filled=False)), 9).find("fill")
    assert unflagged is not None and unflagged.children[0] != Atom.symbol("yes")


def test_created_zone_reads_back() -> None:
    zone = pour(name="GND", locked=True, settings=CREATED_HATCH_SETTINGS)
    for target in (9, 10):
        design = read_board(write_board(created(zone), target=target).text)
        assert design.board is not None
        (found,) = design.board.zones
        assert found.settings == CREATED_HATCH_SETTINGS and found.locked is True and found.filled is False
        assert (found.name, found.outline, found.layers) == (zone.name, zone.outline, zone.layers)


def test_created_canonical_order_matches_the_emitter() -> None:
    emitted = zones.emit_settings(CREATED_HATCH_SETTINGS, filled=True, locked=True, major=10)
    for head in ("connect_pads", "fill"):
        positional = POSITIONAL[head]
        order = [h for h in CANONICAL_ORDER[head] if h not in positional]
        found = heads(emitted[head])
        assert found == [h for h in order if h in found]
    assert set(heads(emitted["fill"])) == set(CANONICAL_ORDER["fill"]) - {"filled"}
    assert heads(emitted["connect_pads"]) == ["clearance"]


def test_created_floor_names_are_written_for_target_9() -> None:
    assert set(ZONE_NAMES) <= set(FLOOR_HEADS)
    root = parse(write_board(created_board(), target=9).text)
    assert set(ZONE_NAMES) <= {n.name for _, n in walk(root)}


def test_created_board_is_emittable_for_both_targets() -> None:
    for target in (9, 10):
        root = parse(write_board(created_board(), target=target).text)
        assert check_emittable(root, FileKind.BOARD, target) == ()


def test_created_rule_area_is_written_as_before() -> None:
    root = parse(write_board(created_board(), target=9).text)
    rule = root.nodes("zone")[-1]
    assert heads(rule) == ["net", "net_name", "layer", "uuid", "keepout", "polygon"]


def test_created_zone_without_a_net() -> None:
    zone = written_zone(created(pour(net_id=None, settings=ZoneSettings())), 10)
    assert between(zone, "uuid", "polygon") == (
        "(hatch edge 0.5) (connect_pads (clearance 0.5)) (min_thickness 0.25)"
        " (fill (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 0))"
    )
    assert mm(0, 0) == pour().outline[0]


# -- read zones


def authored() -> tuple[Design, Zone]:
    design = read_board(FIXTURE)
    assert design.board is not None
    (found,) = design.board.zones
    assert found.name == "GND_B"
    return design, found


def source_zone() -> Node:
    return load(FIXTURE).nodes("zone")[0]


def with_zone(design: Design, zone_: Zone) -> Design:
    return design.replace_entity(zone_)


def read_text(text: str) -> tuple[Design, Zone]:
    design = read_board(text)
    assert design.board is not None
    (found,) = design.board.zones
    return design, found


def read_only(design: Design, target: int) -> list[Issue]:
    with pytest.raises(LossyWriteError) as info:
        write_board(design, target=target)
    assert info.value.droppable is False
    assert {i.code for i in info.value.issues} == {"kicad.board.projection-read-only"}
    return list(info.value.issues)


def test_unchanged_read_zone_is_written_as_read() -> None:
    design, _ = authored()
    assert tree_equal(written_zone(design, 9), source_zone())


def test_read_fill_flag_follows_the_model() -> None:
    design, found = authored()
    cleared = with_zone(design, dataclasses.replace(found, filled=False, fills=()))
    node = written_zone(cleared, 9)
    assert node.find("fill") == parse("(fill (thermal_gap 0.5) (thermal_bridge_width 0.5))")
    assert node.nodes("filled_polygon") == ()
    source = source_zone()
    rest = [h for h in heads(source) if h != "filled_polygon"]
    assert heads(node) == rest  # the fill child stays at its source position


def test_clearance_edited_on_a_read_zone() -> None:
    design, found = authored()
    edited = dataclasses.replace(found, settings=dataclasses.replace(found.settings, clearance=300_000))
    node, source = written_zone(with_zone(design, edited), 9), source_zone()
    assert heads(node) == heads(source)
    at = heads(source).index("connect_pads")
    nodes, sources = node.nodes(), source.nodes()
    assert nodes[at] == parse("(connect_pads (clearance 0.3))")
    assert all(a == b for k, (a, b) in enumerate(zip(nodes, sources, strict=True)) if k != at)


def test_a_zone_without_settings_stays_without_them() -> None:
    text = board(zone(1, inner=SQUARE, settings=""))
    design, found = read_text(text)
    unchanged = written_zone(design, 9)
    for head in ("connect_pads", "min_thickness", "fill"):
        assert unchanged.find(head) is None
    assert tree_equal(unchanged, parse(text).nodes("zone")[0])
    edited = dataclasses.replace(found, settings=dataclasses.replace(found.settings, clearance=300_000))
    node = written_zone(with_zone(design, edited), 9)
    assert node.find("connect_pads") == parse("(connect_pads (clearance 0.3))")
    assert heads(node).index("connect_pads") < heads(node).index("polygon")
    assert node.find("min_thickness") is None and node.find("fill") is None


def test_each_absent_child_appears_only_with_its_own_part() -> None:
    design, found = read_text(board(zone(1, inner=SQUARE, settings="")))
    changes: dict[str, Zone] = {
        "min_thickness": dataclasses.replace(found, settings=ZoneSettings(min_thickness=200_000)),
        "fill": dataclasses.replace(found, filled=True),
        "locked": dataclasses.replace(found, locked=True),
    }
    for head, changed in changes.items():
        node = written_zone(with_zone(design, changed), 9)
        gained = set(heads(node)) - {"net", "net_name", "layer", "uuid", "hatch", "polygon"}
        assert gained == {head}, head
    locked = written_zone(with_zone(design, changes["locked"]), 9)
    order = heads(locked)
    assert order.index("net") < order.index("locked") < order.index("layer")
    filled = written_zone(with_zone(design, changes["fill"]), 9)
    assert filled.find("fill") == parse("(fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5))")
    # a read zone never gains the flag of created zones: its fills mean what its writer meant
    assert filled.find("filled_areas_thickness") is None


def test_projected_settings_are_read_only() -> None:
    settings = (
        "(connect_pads (clearance 0.5)) (min_thickness 0.25)"
        " (fill yes (thermal_gap 0.6) (thermal_bridge_width 0.5) (frobnicate 1))"
    )
    text = board(zone(1, inner=SQUARE, settings=settings), version=20260206, nets=None).replace(
        '(net 1) (net_name "A")', '(net "A")'
    )
    design, found = read_text(text)
    assert tree_equal(written_zone(design, 10), parse(text).nodes("zone")[0])  # kept verbatim
    edited = dataclasses.replace(found, settings=dataclasses.replace(found.settings, thermal_gap=700_000))
    (issue,) = read_only(with_zone(design, edited), 10)
    assert "'settings'" in issue.message and issue.where == "/kicad_pcb/zone[0]/fill[0]"
    # the fill flag alone is set in place, and the rest of the opaque child stays as written
    cleared = written_zone(with_zone(design, dataclasses.replace(found, filled=False)), 10)
    assert cleared.find("fill") == parse("(fill (thermal_gap 0.6) (thermal_bridge_width 0.5) (frobnicate 1))")
    # a change to a part held by a modelled child is written
    other = dataclasses.replace(found, settings=dataclasses.replace(found.settings, clearance=300_000))
    assert written_zone(with_zone(design, other), 10).find("connect_pads") == parse(
        "(connect_pads (clearance 0.3))"
    )


def test_fill_flag_with_an_unknown_atom_is_read_only() -> None:
    settings = "(connect_pads (clearance 0.5)) (min_thickness 0.25) (fill maybe (thermal_gap 0.5))"
    design, found = read_text(board(zone(1, inner=SQUARE, settings=settings)))
    assert found.filled is False
    (issue,) = read_only(with_zone(design, dataclasses.replace(found, filled=True)), 9)
    assert "'filled'" in issue.message and issue.where == "/kicad_pcb/zone[0]/fill[0]"


def test_fill_flag_is_set_on_an_opaque_fill_child() -> None:
    # a nine-form fill in a ten-format board is not what KiCad 10 writes, so the child is opaque
    settings = f"{ZONE_SETTINGS} (fill (thermal_gap 0.5) (thermal_bridge_width 0.5))"
    text = board(zone(1, inner=SQUARE, settings=settings), version=20260206, nets=None).replace(
        '(net 1) (net_name "A")', '(net "A")'
    )
    design, found = read_text(text)
    assert found.filled is False
    node = written_zone(with_zone(design, dataclasses.replace(found, filled=True)), 10)
    assert node.find("fill") == parse("(fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5))")


def test_projected_lock_is_read_only() -> None:
    text = board(zone(1, inner=SQUARE, head="(locked no)"))
    design, found = read_text(text)
    assert tree_equal(written_zone(design, 9), parse(text).nodes("zone")[0])
    (issue,) = read_only(with_zone(design, dataclasses.replace(found, locked=True)), 9)
    assert "'locked'" in issue.message and issue.where == "/kicad_pcb/zone[0]/locked[0]"


def test_unlocking_a_read_zone_removes_the_child() -> None:
    text = board(zone(1, inner=SQUARE, head="(locked yes)"))
    design, found = read_text(text)
    assert written_zone(design, 9).find("locked") == parse("(locked yes)")
    node = written_zone(with_zone(design, dataclasses.replace(found, locked=False)), 9)
    assert node.find("locked") is None


def test_upgrade_to_target_10_writes_the_island_mode() -> None:
    design, _ = authored()
    node = written_zone(design, 10)
    assert node.find("fill") == parse(
        "(fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 0))"
    )
    assert node.find("filled_areas_thickness") is None


def test_written_settings_read_back_on_both_targets() -> None:
    design, found = authored()
    settings = dataclasses.replace(
        CREATED_HATCH_SETTINGS,
        clearance=300_000,
        connection="thru_hole_only",
        min_island_area=2_500_000_000_000,
    )
    edited = with_zone(design, dataclasses.replace(found, settings=settings, locked=True))
    for target in (9, 10):
        again, reread = read_text(write_board(edited, target=target).text)
        assert reread.settings == settings and reread.locked is True and reread.filled is True
        assert write_board(again, target=target).text == write_board(edited, target=target).text
