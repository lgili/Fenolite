# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placement of built parts (capability design-dsl, "Placement of built parts"; change c0011)."""

from __future__ import annotations

from _buildhelp import blink, build, codes

from fenolite.backends.kicad.embed import footprint_extent, placement_uuid
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.dsl import Design, DiffPair, Net, Part
from fenolite.dsl.convert import BOARD_ORIGIN

MM = 1_000_000


def test_placed_parts() -> None:
    out = build(blink())
    fps = {fp.lib_ref: fp for fp in out.design.board.footprints}  # type: ignore[union-attr]
    u1, d1 = fps["Mini:Mini_QFP-32_7x7mm_P0.8mm"], fps["Mini:Mini_LED_THT_3mm"]
    assert u1.position == Point(BOARD_ORIGIN.x + 14 * MM, BOARD_ORIGIN.y + 15 * MM) and u1.locked
    assert d1.side == "bottom"
    assert u1.native_ids["kicad"] == placement_uuid("U1", "/footprint")


def unplaced(*refs: str) -> Design:
    script = blink()
    d = Design("blink")
    d.board("50mm", "30mm")
    for path, part in script.parts.items():
        fresh = Part(part.ref, part.lib_id, footprint=part.footprint, value=part.value)
        if path not in refs:
            assert part.request is not None
            r = part.request
            fresh.place(f"{r.x}nm", f"{r.y}nm", rot=r.rotation // 1_000_000, side=r.side, locked=r.locked)
        d.add(fresh)
    return d


def test_staging_row() -> None:
    out = build(unplaced("D1", "R1"))
    assert codes(out).count("layout.unplaced") == 2 and out.files
    fps = {fp.lib_ref.split(":")[1]: fp for fp in out.design.board.footprints}  # type: ignore[union-attr]
    from _buildhelp import LIBS

    from fenolite.backends.kicad.mod import read_footprint

    led = footprint_extent(read_footprint(LIBS / "Mini_v9.pretty" / "Mini_LED_THT_3mm.kicad_mod"))
    res = footprint_extent(read_footprint(LIBS / "Mini_v9.pretty" / "Mini_R_0603.kicad_mod"))
    d1, r1 = fps["Mini_LED_THT_3mm"], fps["Mini_R_0603"]
    assert d1.position.x + led.x0 == 155 * MM and d1.position.y + led.y0 == 100 * MM
    assert r1.position.x + res.x0 == d1.position.x + led.x1 + 2 * MM and r1.position.y + res.y0 == 100 * MM
    assert d1.side == "top" and d1.rotation == 0 and not d1.locked


def test_no_board() -> None:
    d = Design("t")
    d.add(Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603"))
    out = build(d)
    assert "build.no-board" in codes(out) and out.files == {}


def test_write_accepts_the_built_properties() -> None:
    for target in (9, 10):
        out = build(blink(), target)
        assert out.files and not any(i.code == "kicad.board.projection-read-only" for i in out.issues)
        for c in out.design.circuit.components:
            assert c.path == "" and c.properties["fenolite.path"] == c.ref


def test_four_layer_build() -> None:
    script = blink()
    script.copper = 4
    out = build(script, 10)
    d1 = next(fp for fp in out.design.board.footprints if fp.lib_ref.endswith("LED_THT_3mm"))  # type: ignore[union-attr]
    pad = next(p for p in d1.pads if p.number == "1")
    assert pad.layers[:4] == ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
    back = read_board(out.files["blink.kicad_pcb"].decode("utf-8"))
    d1b = next(fp for fp in back.board.footprints if fp.lib_ref.endswith("LED_THT_3mm"))  # type: ignore[union-attr]
    assert next(p for p in d1b.pads if p.number == "1").layers[:4] == ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def test_diff_pair_reported() -> None:
    d = blink()
    d.add(DiffPair(Net("USB_P"), Net("USB_N")))
    found = [i for i in build(d).issues if i.code == "build.interface-not-lowered"]
    assert len(found) == 1 and "USB_P/USB_N" in found[0].message
