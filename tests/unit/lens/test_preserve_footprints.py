# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Kept, re-placed, orphan and board-only footprints at the function level (capability layout-lens;
change c0019)."""

from __future__ import annotations

import dataclasses

from _buildhelp import blink, build
from _layout_edit import edit_blink
from _preserve_help import board_text, merged

from fenolite.backends.kicad.embed import PATH_PROPERTY, placement_uuid
from fenolite.backends.kicad.pcb import field_value, read_board, write_board
from fenolite.backends.kicad.slots import from_ext
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.lens.preserve import Merged, _apply_user_properties, footprint_uuid
from fenolite.model.board import FootprintInstance


def test_matched_footprints_keep_their_nodes() -> None:
    result, board = merged(blink(), board_text(edit=edit_blink))
    assert result.summary["kept"] == ["D1", "R1", "U1"] and result.summary["replaced"] == []
    assert board.board is not None and result.design.board is not None
    before = {fp.id: from_ext(fp.ext["kicad"]) for fp in board.board.footprints}
    after = {fp.id: from_ext(fp.ext["kicad"]) for fp in result.design.board.footprints}
    assert after == before
    components = {c.id for c in result.design.circuit.components}
    assert all(fp.component_id in components for fp in result.design.board.footprints)


def test_kept_pads_take_the_built_nets() -> None:
    result, _ = merged(blink(), board_text(edit=edit_blink))
    assert result.design.board is not None
    nets = {n.id: n.name for n in result.design.circuit.nets}
    refs = {c.id: c.ref for c in result.design.circuit.components}
    (r1,) = [fp for fp in result.design.board.footprints if refs[fp.component_id] == "R1"]
    assert {p.number: nets.get(p.net_id or "") for p in r1.pads} == {"1": "LED_DRV", "2": "LED_A"}


def _r1(result: Merged) -> FootprintInstance:
    assert result.design.board is not None
    refs = {c.id: c.ref for c in result.design.circuit.components}
    (r1,) = [fp for fp in result.design.board.footprints if refs[fp.component_id] == "R1"]
    return r1


def test_user_property_appended_with_a_name_derived_uuid() -> None:
    """c0019's rule on fields (c0030 Decision 17): a missing user property is added after the kept
    footprint's last field, as the built copy's field, with a name-derived uuid."""
    d = blink()
    d.parts["R1"].properties = {"Part number": "PN-330"}
    result, board = merged(d, board_text())
    assert result.summary["kept"] == ["D1", "R1", "U1"]
    r1 = _r1(result)
    assert board.board is not None
    (kept,) = [fp for fp in board.board.footprints if fp.id == r1.id]
    assert r1.fields[:-1] == kept.fields and from_ext(r1.ext["kicad"]) == from_ext(kept.ext["kicad"])
    pn = r1.fields[-1]
    assert pn.name == "Part number" and field_value(pn) == "PN-330"
    assert pn.native_ids == {"kicad": placement_uuid("R1", "/footprint/property:Part number")}
    assert pn.id == derived_id("fld", "kicad", f"{r1.native_ids['kicad']}:field:Part number")
    assert pn.provenance is None and not pn.visible and pn.layer == "F.Fab"
    (component,) = [c for c in result.design.circuit.components if c.ref == "R1"]
    assert component.properties["Part number"] == "PN-330"
    # the written board holds the node after the last field node, and reads back as that field
    text = write_board(result.design, target=10).text
    (again,) = [
        fp
        for fp in read_board(text).board.footprints
        if fp.native_ids == r1.native_ids  # type: ignore[union-attr]
    ]
    assert [f.name for f in again.fields] == [f.name for f in r1.fields]
    assert (again.fields[-1].id, again.fields[-1].native_ids) == (pn.id, pn.native_ids)


def test_user_property_field_takes_the_scripts_value_only() -> None:
    d = blink()
    d.parts["R1"].properties = {"Part number": "PN-330"}
    text = build(d, 10).files["blink.kicad_pcb"].decode("utf-8")
    assert '(property "Part number" "PN-330"' in text
    marker = '(property "Part number" "PN-330"\n\t\t\t(at 0 0 0)\n\t\t\t(layer "F.Fab")\n\t\t\t(hide yes)'
    assert text.count(marker) == 1
    edited = text.replace(marker, '(property "part number" "PN-330"\n\t\t\t(at 1 2 0)\n\t\t\t(layer "F.Fab")')
    changed = blink()
    changed.parts["R1"].properties = {"Part number": "PN-470", "Supplier code": "S-1"}
    result, board = merged(changed, edited)
    r1 = _r1(result)
    assert board.board is not None
    (kept,) = [fp for fp in board.board.footprints if fp.id == r1.id]
    old = next(f for f in kept.fields if f.name == "part number")
    new = next(f for f in r1.fields if f.name == "Part number")
    assert field_value(old) == "PN-330" and field_value(new) == "PN-470"
    same = (
        "position",
        "rotation",
        "layer",
        "size",
        "thickness",
        "visible",
        "h_justify",
        "v_justify",
        "mirrored",
    )
    assert all(getattr(new, a) == getattr(old, a) for a in same)
    assert new.visible and new.position == Point(1_000_000, 2_000_000)
    assert (new.id, new.native_ids) == (old.id, old.native_ids)
    assert [f.name for f in r1.fields][-1] == "Supplier code"
    (component,) = [c for c in result.design.circuit.components if c.ref == "R1"]
    assert component.properties["Part number"] == "PN-470" and "part number" not in component.properties
    assert component.properties["Supplier code"] == "S-1"
    write_board(result.design, target=10)  # "Projected fields on write" passes


def test_kept_footprint_without_a_path_field_keeps_its_properties() -> None:
    d = blink()
    d.parts["R1"].properties = {"Part number": "PN-330"}
    built_fp = _r1(merged(d, board_text())[0])
    plain = dataclasses.replace(built_fp, fields=tuple(f for f in built_fp.fields if f.name != PATH_PROPERTY))
    built_copy = next(
        fp
        for fp in build(d, 10).design.board.footprints
        if fp.native_ids == built_fp.native_ids  # type: ignore[union-attr]
    )
    same, written = _apply_user_properties(plain, built_copy, "R1")
    assert same is plain and written == {}


def test_alias_re_places_under_the_new_path() -> None:
    d = blink()
    part = d.parts.pop("R1")
    part.ref = "R7"
    d.parts["R7"] = part
    d.moved("R1", "R7")
    result, _ = merged(d, board_text())
    assert result.summary["replaced"] == ["R7"] and "layout.alias-used" in [i.code for i in result.issues]
    assert result.design.board is not None
    assert footprint_uuid("R7") in {fp.native_ids["kicad"] for fp in result.design.board.footprints}


def test_orphan_removed() -> None:
    d = blink()
    from _build_preserve_variants import without_r1

    result, _ = merged(without_r1(d), board_text(edit=edit_blink))
    assert result.summary["orphans"] == ["R1"]
    (orphan,) = [i for i in result.issues if i.code == "layout.orphan"]
    assert orphan.severity == "warning" and "uuid" in orphan.message and "mm" in orphan.message
