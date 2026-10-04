# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Script zones across a rebuild, at the function level (capability layout-lens, "Zones declared in the
script" and the MODIFIED "Zone fills and the staleness digest"; change c0031)."""

from __future__ import annotations

import dataclasses

from _build_preserve_variants import without_r1
from _buildhelp import blink, pour_variant
from _layout_edit import ZONE_UUID, add_filled_zone
from _preserve_help import fresh, merged, rebuild

from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse, tree_equal
from fenolite.backends.kicad.zones import MERGE_ISSUE_CODES
from fenolite.dsl import Net, mm
from fenolite.lens.build import BUILD_ISSUE_CODES, BuildOutput
from fenolite.lens.preserve import (
    PRESERVE_ISSUE_CODES,
    ExistingProject,
    drop_stale_fills,
    zone_digest,
)
from fenolite.model.board import Zone, ZoneHatch
from fenolite.model.design import Design

BOARD = "blink.kicad_pcb"
RULES = "(version 1)\n"
SAME = ExistingProject(project="{}", rules=RULES)
FILLS = (
    '(filled_polygon (layer "B.Cu") (pts (xy 101.5 101.5) (xy 148.5 101.5) (xy 148.5 128.5)'
    " (xy 101.5 128.5)))",
    '(filled_polygon (layer "B.Cu") (pts (xy 120 120) (xy 122 120) (xy 122 122) (xy 120 122)))',
)
NINE_FORM = "(fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5))"


def pour_text(target: int = 10, **zone: object) -> str:
    return fresh(target, pour_variant(**zone)).files[BOARD].decode("utf-8")


def zone_node(text: str, name: str = "GND") -> Node:
    wanted = parse(f'(name "{name}")')
    (found,) = [z for z in parse(text).nodes("zone") if z.find("name") == wanted]
    return found


def replace_zone(text: str, old: Node, new: Node) -> str:
    root = parse(text)
    assert old in root.children
    return dumps(root.with_children([new if c == old else c for c in root.children]))


def edit_zone(text: str, old: str, new: str, name: str = "GND") -> str:
    """``text`` with ``old`` replaced by ``new`` inside the zone ``name`` (compact fragments)."""
    target = zone_node(text, name)
    compact = dumps(target, style="compact")
    assert old in compact, old
    return replace_zone(text, target, parse(compact.replace(old, new, 1)))


def with_clearance(text: str, value: str = "0.5") -> str:
    return edit_zone(text, "(clearance 0.3)", f"(clearance {value})")


def filled(text: str) -> str:
    """The script's zone as KiCad leaves it after a fill: ``(fill yes …)`` and two fill polygons."""
    flagged = edit_zone(text, "(fill (", "(fill yes (")
    node = zone_node(flagged)
    return replace_zone(flagged, node, node.with_children([*node.children, *(parse(f) for f in FILLS)]))


def kicad_codes(issues: object) -> list[str]:
    return [i.code for i in issues if i.code.startswith("kicad.zone.")]  # type: ignore[attr-defined]


def zones(design: Design) -> tuple[Zone, ...]:
    assert design.board is not None
    return design.board.zones


def written(output: BuildOutput) -> str:
    return output.files[BOARD].decode("utf-8")


def test_fresh_builds_report_no_zone_code() -> None:
    for target in (9, 10):
        assert kicad_codes(fresh(target, pour_variant()).issues) == []


def test_unchanged_rebuild_keeps_the_zone_and_its_bytes() -> None:
    text = pour_text()
    again = rebuild(pour_variant(), text)
    assert kicad_codes(again.issues) == [] and written(again) == text


def test_clearance_edited_in_kicad_wins() -> None:
    edited = with_clearance(pour_text())
    again = rebuild(pour_variant(), edited)
    (issue,) = [i for i in again.issues if i.code.startswith("kicad.zone.")]
    assert (issue.code, issue.severity) == ("kicad.zone.overridden", "info")
    assert "GND" in issue.message and "settings" in issue.message and "--discard-layout" in issue.hint
    assert tree_equal(zone_node(written(again)), zone_node(edited))
    assert not [i for i in again.issues if i.severity == "error"]


def test_a_locked_zone_wins() -> None:
    edited = with_clearance(pour_text())
    again = rebuild(pour_variant(locked=True), edited)
    assert kicad_codes(again.issues) == ["kicad.zone.forced"]
    node = zone_node(written(again))
    assert node.find("connect_pads") == parse("(connect_pads yes (clearance 0.3))")
    assert node.find("locked") == parse("(locked yes)")
    # the next build finds the board equal to the script
    assert kicad_codes(rebuild(pour_variant(locked=True), written(again)).issues) == []


def test_zone_added_to_the_script() -> None:
    design = pour_variant()
    design.zone(design.nets["VIN"], layers=("F.Cu",), name="VIN_TOP")
    again = rebuild(design, pour_text())
    assert kicad_codes(again.issues) == []
    assert [z.name for z in zones(read_board(written(again)))] == ["GND", "VIN_TOP"]


def test_zone_removed_from_the_script() -> None:
    both = pour_variant()
    both.zone(both.nets["VIN"], layers=("F.Cu",), name="VIN_TOP")
    text = fresh(10, both).files[BOARD].decode("utf-8")
    again = rebuild(pour_variant(), text)
    (issue,) = [i for i in again.issues if i.code.startswith("kicad.zone.")]
    assert issue.code == "kicad.zone.orphan" and "VIN_TOP" in issue.message
    assert [z.name for z in zones(read_board(written(again)))] == ["GND"]


def test_zone_drawn_in_kicad() -> None:
    text = pour_text()
    node = zone_node(text)
    uuid = dumps(node.find("uuid"), style="compact")  # type: ignore[arg-type]
    drawn = dumps(node, style="compact").replace(uuid, '(uuid "00000000-0000-4000-8000-0000000000a1")')
    root = parse(text)
    both = dumps(root.with_children([*root.children, parse(drawn)]))
    again = rebuild(pour_variant(), both)
    assert kicad_codes(again.issues) == []
    assert [z.name for z in zones(read_board(written(again)))] == ["GND", "GND"]


def test_other_zones_still_follow_their_nets() -> None:
    text = add_filled_zone(pour_text(), net="GND", layer="F.Cu")
    result, _ = merged(pour_variant(), text)
    assert {z.native_ids["kicad"] for z in zones(result.design)} >= {ZONE_UUID}
    # a zone drawn in KiCad on a net that the design loses is dropped by the net rule, as before
    design = blink()
    design.zone(Net("AUX"), layers=("B.Cu",), name="AUX")
    aux_text = add_filled_zone(fresh(10, design).files[BOARD].decode("utf-8"), net="AUX", layer="F.Cu")
    gone, _ = merged(blink(), aux_text)
    assert zones(gone.design) == ()
    codes = [i.code for i in gone.issues]
    assert "layout.net-removed" in codes and "kicad.zone.orphan" in codes


def test_zone_codes_pass_through_the_closed_tables() -> None:
    assert set(MERGE_ISSUE_CODES).isdisjoint(PRESERVE_ISSUE_CODES)
    assert set(MERGE_ISSUE_CODES).isdisjoint(BUILD_ISSUE_CODES)
    assert all(code.startswith("kicad.zone.") for code in MERGE_ISSUE_CODES)


# -- the digest and stale fills


def test_digest_covers_effective_settings_only() -> None:
    design = read_board(pour_text())
    (zone,) = zones(design)
    base = zone_digest(design, zone)

    def changed(**changes: object) -> str:
        return zone_digest(design, dataclasses.replace(zone, **changes))  # type: ignore[arg-type]

    settings = zone.settings
    assert changed(settings=dataclasses.replace(settings, clearance=400_000)) != base
    assert changed(settings=dataclasses.replace(settings, connection="thermal")) != base
    assert changed(settings=dataclasses.replace(settings, hatch=ZoneHatch(gap=2_000_000))) == base
    assert changed(settings=dataclasses.replace(settings, smoothing_radius=1_000_000)) == base
    assert changed(settings=dataclasses.replace(settings, min_island_area=1)) == base
    assert changed(filled=True) == base and changed(locked=True) == base
    assert changed(priority=1) != base


def test_digest_ignores_the_fill_flag_of_an_opaque_fill_child() -> None:
    text = add_filled_zone(pour_text(), net="GND", layer="F.Cu")  # a nine-form fill in a ten-format board
    design = read_board(text)
    (zone,) = [z for z in zones(design) if z.native_ids["kicad"] == ZONE_UUID]
    drawn = next(z for z in parse(text).nodes("zone") if ZONE_UUID in dumps(z, style="compact"))
    unflagged = dumps(drawn, style="compact").replace(NINE_FORM, NINE_FORM.replace(" yes", ""), 1)
    cleared = read_board(replace_zone(text, drawn, parse(unflagged)))
    (other,) = [z for z in zones(cleared) if z.native_ids["kicad"] == ZONE_UUID]
    assert zone.filled and not other.filled
    assert zone_digest(design, zone) == zone_digest(cleared, other)


def test_digests_ignore_formats_for_script_zones() -> None:
    nine = read_board(filled(pour_text(9)))
    ten = read_board(filled(pour_text(10)))
    assert zone_digest(nine, zones(nine)[0]) == zone_digest(ten, zones(ten)[0])


def test_unchanged_rebuild_keeps_the_fills_of_a_script_zone() -> None:
    text = filled(pour_text())
    result, board = merged(pour_variant(), text)
    kept, issues = drop_stale_fills(board, result.design, existing=SAME, project="{}", rules=RULES)
    assert issues == () and len(zones(kept)[0].fills) == 2 and zones(kept)[0].filled is True


def test_a_zone_setting_change_drops_fills() -> None:
    text = filled(pour_text(locked=True))
    again = rebuild(pour_variant(locked=True, clearance=mm(0.4)), text)
    codes = [i.code for i in again.issues]
    assert "zone.fill-stale" in codes and "kicad.zone.forced" in codes
    node = zone_node(written(again))
    assert node.find("connect_pads") == parse("(connect_pads yes (clearance 0.4))")
    assert node.nodes("filled_polygon") == ()
    fill = node.find("fill")
    assert fill is not None and fill.atoms() == ()
    (zone,) = zones(read_board(written(again)))
    assert zone.filled is False and zone.fills == ()


def test_stale_fills_clear_the_fill_flag() -> None:
    text = filled(pour_text())
    result, board = merged(without_r1(pour_variant()), text)  # a removed part changes the fill inputs
    stale, issues = drop_stale_fills(board, result.design, existing=SAME, project="{}", rules=RULES)
    assert [i.code for i in issues] == ["zone.fill-stale"]
    assert zones(stale)[0].fills == () and zones(stale)[0].filled is False


def test_a_filled_zone_without_polygons_is_cleared_too() -> None:
    text = edit_zone(pour_text(), "(fill (", "(fill yes (")
    result, board = merged(without_r1(pour_variant()), text)
    assert zones(board)[0].filled is True and zones(board)[0].fills == ()
    stale, issues = drop_stale_fills(board, result.design, existing=SAME, project="{}", rules=RULES)
    assert [i.code for i in issues] == ["zone.fill-stale"] and zones(stale)[0].filled is False
