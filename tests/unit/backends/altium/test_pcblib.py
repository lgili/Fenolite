# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint checks, graphics and the library file of the Altium PCB writer (change c0035, capability
altium-pcb-writer, "Footprint content checks", "Footprint line and arc records", "PCB library file")."""

from __future__ import annotations

import dataclasses
import math
from decimal import Decimal
from pathlib import Path

import pytest
from _altium_pcb_read import ArcRecord, PadRecord, Track, decode_primitives

from fenolite.backends.altium.pcblib import (
    LibFootprint,
    PadExtras,
    check_footprint,
    graphic_records,
)
from fenolite.backends.kicad.mod import read_footprint
from fenolite.core.coords import Point
from fenolite.model.board import Graphic
from fenolite.model.library import FootprintDef

MINI = Path(__file__).resolve().parents[3] / "data" / "libs" / "Mini_v9.pretty"
NAMES = ("Mini_LED_THT_3mm", "Mini_QFP-32_7x7mm_P0.8mm", "Mini_R_0603")
UNIT_NM = Decimal(127) / 50


def mini(name: str) -> FootprintDef:
    return read_footprint(MINI / f"{name}.kicad_mod", library="Mini")


def ratios(defn: FootprintDef) -> dict[str, PadExtras]:
    return {p.id: PadExtras(Decimal("0.25") if p.shape == "roundrect" else None) for p in defn.pads}


def lib_footprint(name: str) -> LibFootprint:
    defn = mini(name)
    return LibFootprint(defn, ratios(defn), texts=1 if name == "Mini_R_0603" else 0)


def decode(records: list[bytes]) -> list[object]:
    return list(decode_primitives(b"".join(records)))


# --- checks -----------------------------------------------------------------------------------------


def test_check_mini_footprints() -> None:
    for name in NAMES:
        defn = mini(name)
        check = check_footprint(defn, ratios(defn))
        assert check.refusal is None, name
        assert check.pads == defn.pads
    qfp = check_footprint(mini(NAMES[1]), ratios(mini(NAMES[1])))
    assert qfp.dropped == ("filled polygon on F.SilkS",)
    assert len(qfp.graphics) == len(mini(NAMES[1]).graphics) - 1
    led = check_footprint(mini(NAMES[0]), ratios(mini(NAMES[0])))
    assert led.dropped == () and led.extras == ("4 properties", "1 3D model link(s)")
    r = check_footprint(mini(NAMES[2]), ratios(mini(NAMES[2])), texts=1)
    assert r.extras[0] == "1 text(s)"


def _pad_variant(defn: FootprintDef, **changes: object) -> FootprintDef:
    pads = (dataclasses.replace(defn.pads[0], **changes), *defn.pads[1:])  # type: ignore[arg-type]
    return dataclasses.replace(defn, pads=pads)


@pytest.mark.parametrize(
    ("changes", "extras", "reason"),
    [
        ({"shape": "trapezoid"}, None, "pad '1' has the shape trapezoid"),
        ({"shape": "custom"}, None, "pad '1' has the shape custom"),
        ({"drill": None}, None, "pad '1' has no round drill"),
        ({"shape": "roundrect"}, PadExtras(), "pad '1' is a rounded rectangle without a corner ratio"),
        ({"kind": "connect"}, None, "pad '1' is a connector pad"),
        ({"layers": ("F.Cu", "F.Mask")}, None, "pad '1' is a through-hole pad with copper on one side"),
        ({"number": "a|b"}, None, "the pad number 'a|b'"),
        ({}, PadExtras(refusal="the drill has an offset"), "pad '1': the drill has an offset"),
    ],
)
def test_refused_pads(changes: dict[str, object], extras: PadExtras | None, reason: str) -> None:
    """Scenario "Refused pad shapes": each refusal names the pad."""
    defn = _pad_variant(mini(NAMES[0]), **changes)
    given = {defn.pads[0].id: extras} if extras is not None else {}
    check = check_footprint(defn, given)
    assert check.refusal is not None and check.refusal.startswith(reason)


def test_copper_graphic_refused() -> None:
    defn = mini(NAMES[2])
    graphic = dataclasses.replace(defn.graphics[0], layer="F.Cu")
    check = check_footprint(dataclasses.replace(defn, graphics=(graphic,)), ratios(defn))
    assert check.refusal == "a line lies on the copper layer F.Cu"


def test_dropped_polygon_and_unmapped_layer() -> None:
    """Scenario "Dropped polygon": a polygon on F.SilkS and a line on Dwgs.User are both dropped."""
    defn = mini(NAMES[2])
    polygon = Graphic(
        id=defn.graphics[0].id,
        kind="polygon",
        layer="F.SilkS",
        points=(Point(0, 0), Point(100_000, 0), Point(0, 100_000)),
        width=120_000,
    )
    user = dataclasses.replace(defn.graphics[0], layer="Dwgs.User")
    variant = dataclasses.replace(defn, graphics=(*defn.graphics, polygon, user))
    check = check_footprint(variant, ratios(defn))
    assert check.dropped == ("polygon on F.SilkS", "line on Dwgs.User")
    assert check.graphics == defn.graphics


def test_pad_settings_dropped() -> None:
    defn = mini(NAMES[2])
    extras = {p.id: PadExtras(Decimal("0.25"), dropped=("solder mask margin",)) for p in defn.pads}
    no_paste = _pad_variant(defn, layers=("F.Cu", "F.Mask"))
    check = check_footprint(no_paste, extras)
    assert check.dropped == ("pad 1 solder mask margin", "pad 1 without F.Paste", "pad 2 solder mask margin")


# --- graphics ---------------------------------------------------------------------------------------


def test_led_silkscreen_arcs() -> None:
    """Scenario "Silkscreen arcs of the mini LED"."""
    defn = mini(NAMES[0])
    arcs = [g for g in defn.graphics if g.kind == "arc"]
    assert len(arcs) == 2
    for graphic in arcs:
        (arc,) = decode(graphic_records(graphic))
        assert isinstance(arc, ArcRecord)
        assert arc.prefix.layer == 33 and arc.width == 47244  # 0.12 mm
        assert abs(Decimal(arc.cx) * UNIT_NM - 1_270_000) <= Decimal("2.54")
        for p in graphic.points:
            d = math.hypot(float(p.x - Decimal(arc.cx) * UNIT_NM), float(-p.y - Decimal(arc.cy) * UNIT_NM))
            assert abs(d - float(arc.radius * UNIT_NM)) <= 2.54
        mid = graphic.points[1]
        angle = (
            math.degrees(math.atan2(-mid.y - float(arc.cy * UNIT_NM), mid.x - float(arc.cx * UNIT_NM))) % 360
        )
        span = (arc.end - arc.start) % 360
        assert (angle - arc.start) % 360 <= span


def test_rectangle_and_circle() -> None:
    """Scenario "Rectangle and circle": four closing tracks on 71, one 0-360 arc on 69."""
    defn = mini(NAMES[0])
    (rect,) = [g for g in defn.graphics if g.kind == "rect"]
    tracks = decode(graphic_records(rect))
    assert len(tracks) == 4 and all(isinstance(t, Track) and t.prefix.layer == 71 for t in tracks)
    ends = [(t.x2, t.y2) for t in tracks if isinstance(t, Track)]
    starts = [(t.x1, t.y1) for t in tracks if isinstance(t, Track)]
    assert starts == [ends[-1], *ends[:-1]]
    (circle,) = [g for g in defn.graphics if g.kind == "circle"]
    (arc,) = decode(graphic_records(circle))
    assert isinstance(arc, ArcRecord) and arc.prefix.layer == 69 and (arc.start, arc.end) == (0.0, 360.0)
    assert arc.radius == 590551  # 1.5 mm


def test_graphic_flip() -> None:
    defn = mini(NAMES[2])
    (track,) = decode(graphic_records(defn.graphics[0], flip=True, component=2))
    assert isinstance(track, Track) and track.prefix.layer == 34 and track.prefix.component == 2


def test_pad_record_of_a_mini_pad() -> None:
    from fenolite.backends.altium.pcblib import library_frame, pad_bytes

    defn = mini(NAMES[2])
    pad = defn.pads[0]
    (decoded,) = decode(
        [pad_bytes(pad, PadExtras(Decimal("0.25")), at=library_frame(pad.position), rotation_udeg=0)]
    )
    assert isinstance(decoded, PadRecord)
    assert (decoded.x, decoded.y, decoded.prefix.layer, decoded.corners[0]) == (-314961, 0, 1, 50)
