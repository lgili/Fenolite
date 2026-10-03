# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint checks, graphics and the library file of the Altium PCB writer (change c0035, capability
altium-pcb-writer, "Footprint content checks", "Footprint line and arc records", "PCB library file")."""

from __future__ import annotations

import dataclasses
import math
import struct
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


# --- the library file (task 3.3) --------------------------------------------------------------------


def _library(*footprints: LibFootprint) -> bytes:
    from fenolite.backends.altium.pcblib import write_pcblib

    return write_pcblib(list(footprints))


def test_library_of_the_mini_footprints() -> None:
    """Scenario "Library of the mini footprints"."""
    from _altium_pcb_read import read_pcblib

    lib = read_pcblib(_library(*(lib_footprint(n) for n in NAMES)))
    assert lib.names == sorted(NAMES, key=lambda n: (len(n), n.upper()))
    assert lib.library_fields["KIND"] == "Protel_Advanced_PCB_Library"
    assert lib.library_fields["FILENAME"] == "Fenolite.PcbLib"
    assert [row["Name"] for row in lib.toc] == lib.names
    assert {row["Name"]: row["Pad Count"] for row in lib.toc}[NAMES[1]] == "32"
    assert "SectionKeys" not in lib.streams
    for name in NAMES:
        footprint = lib.footprints[name]
        assert footprint.parameters["PATTERN"] == name and footprint.parameters["HEIGHT"] == "0mil"
        assert footprint.parameters["DESCRIPTION"] == mini(name).description
        assert footprint.header_count == len(footprint.primitives) == len(footprint.unique_ids)
        assert footprint.wide_strings == [{}]
    qfp = lib.footprints[NAMES[1]]
    assert sum(isinstance(p, PadRecord) for p in qfp.primitives) == 32
    kinds = [u["PRIMITIVEOBJECTID"] for u in lib.footprints["Mini_R_0603"].unique_ids]
    assert kinds == ["Pad"] * 2 + ["Track"] * 10


def test_library_streams_and_nothing_else() -> None:
    from _altium_pcb_read import LIBRARY_STREAMS, read_pcblib

    lib = read_pcblib(_library(lib_footprint("Mini_R_0603")))
    assert sorted(lib.streams) == sorted(
        [
            "FileHeader",
            *LIBRARY_STREAMS[1:],
            "Mini_R_0603/Header",
            "Mini_R_0603/Parameters",
            "Mini_R_0603/WideStrings",
            "Mini_R_0603/Data",
            "Mini_R_0603/UniqueIDPrimitiveInformation/Header",
            "Mini_R_0603/UniqueIDPrimitiveInformation/Data",
        ]
    )


def test_file_header_and_library_ids() -> None:
    """Scenario "Library header and side streams": 53 bytes, ids that follow the file name only."""
    from _altium_pcb_read import read_pcblib

    from fenolite.backends.altium.pcblib import write_pcblib

    footprint = lib_footprint("Mini_R_0603")
    first = read_pcblib(write_pcblib([footprint], filename="a.PcbLib"))
    again = read_pcblib(write_pcblib([footprint], filename="a.PcbLib"))
    other = read_pcblib(write_pcblib([footprint], filename="b.PcbLib"))
    assert len(first.streams["FileHeader"]) == 53
    assert first.unique_id == again.unique_id != other.unique_id
    assert first.library_fields["FILENAME"] == "a.PcbLib"
    pad_via = first.streams["Library/PadViaLibrary/Data"]
    assert (
        pad_via == again.streams["Library/PadViaLibrary/Data"] != other.streams["Library/PadViaLibrary/Data"]
    )
    assert b"PADVIALIBRARY.LIBRARYNAME=<Local>|PADVIALIBRARY.DISPLAYUNITS=1" in pad_via


def test_board_record_is_whole_and_marks_the_used_layers() -> None:
    """Scenario "Board record": the block is longer than 65 535 bytes and its length word has type 0."""
    from _altium_pcb_read import read_pcblib

    lib = read_pcblib(_library(lib_footprint("Mini_R_0603")))
    data = lib.streams["Library/Data"]
    (word,) = struct.unpack_from("<I", data, 0)
    assert 65_535 < word < 1 << 24 and len(lib.board) == 2044
    assert data[4 : 4 + word].count(b"\r") == 24 and b"\n" not in data[4 : 4 + word]
    assert "HEADER" not in lib.library_fields and "WEIGHT" not in lib.library_fields
    used = sorted(
        key for key, value in lib.board if key.startswith("V9_CACHE") and value == "TRUE" and "USED" in key
    )
    layers = {p.prefix.layer for p in lib.footprints["Mini_R_0603"].primitives}
    assert layers == {1, 33, 69, 71} and len(used) == len(layers)


def test_library_without_footprints() -> None:
    from _altium_pcb_read import read_pcblib

    lib = read_pcblib(_library())
    assert lib.names == [] and lib.toc == [] and lib.footprints == {}
    assert lib.streams["Library/ComponentParamsTOC/Data"] == struct.pack("<I", 1) + b"\0"
    assert not [key for key, value in lib.board if key.endswith("USEDBYPRIMS") and value == "TRUE"]


def test_library_file_name_with_a_folder_is_refused() -> None:
    from fenolite.backends.altium.pcblib import write_pcblib

    with pytest.raises(ValueError, match="holds a folder"):
        write_pcblib([], filename="lib/a.PcbLib")
    with pytest.raises(ValueError, match="the library file name"):
        write_pcblib([], filename="a|b.PcbLib")


def test_long_name() -> None:
    """Scenario "Long name": 43 characters stored under a 31-character key with SectionKeys."""
    from _altium_pcb_read import read_pcblib

    footprint = lib_footprint("Mini_R_0603")
    long_name = "Mini_R_0603_with_a_name_of_forty_three_char"
    assert len(long_name) == 43
    renamed = LibFootprint(dataclasses.replace(footprint.defn, name=long_name), footprint.extras)
    lib = read_pcblib(_library(renamed))
    assert lib.section_keys == {long_name: long_name[:31]}
    assert lib.footprints[long_name].storage == long_name[:31]
    assert lib.footprints[long_name].parameters["PATTERN"] == long_name


def test_storage_name_clash() -> None:
    footprint = lib_footprint("Mini_R_0603")
    other = LibFootprint(dataclasses.replace(footprint.defn, name="MINI_R_0603"), footprint.extras)
    with pytest.raises(ValueError, match="one storage name"):
        _library(footprint, other)


def test_refused_footprint_raises() -> None:
    footprint = lib_footprint("Mini_R_0603")
    refused = LibFootprint(_pad_variant(footprint.defn, shape="trapezoid"), footprint.extras)
    with pytest.raises(ValueError, match="trapezoid"):
        _library(refused)


def test_bytes_depend_only_on_the_footprints() -> None:
    first = _library(*(lib_footprint(n) for n in NAMES))
    second = _library(*(lib_footprint(n) for n in reversed(NAMES)))
    assert first == second
