# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Kept, re-placed, orphan and board-only footprints at the function level (capability layout-lens;
change c0019)."""

from __future__ import annotations

from _buildhelp import blink
from _layout_edit import edit_blink
from _preserve_help import board_text, merged

from fenolite.backends.kicad.embed import placement_uuid
from fenolite.backends.kicad.slots import from_ext
from fenolite.lens.preserve import footprint_uuid


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


def test_user_property_appended_with_a_name_derived_uuid() -> None:
    d = blink()
    d.parts["R1"].properties = {"Part number": "PN-330"}
    result, _ = merged(d, board_text())
    assert result.design.board is not None
    refs = {c.id: c.ref for c in result.design.circuit.components}
    (r1,) = [fp for fp in result.design.board.footprints if refs[fp.component_id] == "R1"]
    fragments = [
        s.fragment for s in from_ext(r1.ext["kicad"]) if getattr(s, "fragment", "").startswith("(property")
    ]
    (pn,) = [f for f in fragments if '"Part number"' in f]
    assert placement_uuid("R1", "/footprint/property:Part number") in pn and fragments[-1] == pn
    (component,) = [c for c in result.design.circuit.components if c.ref == "R1"]
    assert component.properties["Part number"] == "PN-330"


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
