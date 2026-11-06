# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Keep-out fills of copper come back from KiCad as keep-out fills, not regions (change c0455)."""

import dataclasses
import struct
from collections import Counter
from pathlib import Path

import pytest
from _convert import two_layer

from fenolite.backends.altium import keepout_lines, lower
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RegionRecord
from fenolite.convert import convert_project
from fenolite.convert.altium_to_kicad import stroke_names
from fenolite.convert.sources import read_source
from fenolite.core.coords import Point
from fenolite.model.board import Keepout
from fenolite.model.design import Design

MM = 1_000_000
KEEPOUT_FLAG = 2
TOP, BOTTOM = 1, 32
"""The Altium ids of the two layers of ``two_layer``."""
FREE = (Point(2 * MM, 2 * MM), Point(6 * MM, 2 * MM), Point(6 * MM, 3 * MM), Point(2 * MM, 3 * MM))
OWN = (Point(-MM, -MM // 2), Point(MM, -MM // 2), Point(MM, MM // 2), Point(-MM, MM // 2))
"""The corners of a free keep-out fill and of a keep-out fill of a footprint (its pad frame)."""


def _area(ident: str, corners: tuple[Point, ...], layer: str, restrictions: int) -> Keepout:
    """The rule area that the import makes of a keep-out fill of copper, with its marker as its name, as a
    conversion to KiCad gives it."""
    return Keepout(
        id=ident,
        outline=corners,
        layers=(layer,),
        no_vias=bool(restrictions & 1),
        no_tracks=bool(restrictions & 2),
        no_copper_pour=bool(restrictions & 4),
        no_pads=restrictions & 0x18 == 0x18,
        name=keepout_lines.fill_marker(corners, restrictions) or "",
    )


def _filled() -> Design:
    """The two-layer board with a free keep-out fill of ``F.Cu`` that keeps out poured copper alone (4) and
    a keep-out fill of ``B.Cu`` in its first footprint that keeps out pads alone (24, as row ``-08``)."""
    design = two_layer()
    assert design.board is not None
    first, *rest = design.board.footprints
    first = dataclasses.replace(first, keepouts=(*first.keepouts, _area("kpo-own", OWN, "B.Cu", 24)))
    board = dataclasses.replace(
        design.board,
        keepouts=(*design.board.keepouts, _area("kpo-free", FREE, "F.Cu", 4)),
        footprints=(first, *rest),
    )
    return dataclasses.replace(design, board=board)


def _written(design: Design) -> bytes:
    written = lower.write_design(design, allow_lossy=True)
    return written.files[f"{design.header.name}.PcbDoc"]


def _keepout_fills(document: bytes) -> Counter[tuple[int, str, int, int]]:
    """(layer, owner, subrecord length, restriction byte) of each keep-out fill."""
    found: Counter[tuple[int, str, int, int]] = Counter()
    for record in read_pcbdoc(document).fills:
        prefix = getattr(record, "prefix", None)
        if prefix is None or prefix.flags2 != KEEPOUT_FLAG:
            continue
        body = record.raw[5:]
        owner = "free" if prefix.component is None else "component"
        found[(prefix.layer, owner, len(body), body[46] if len(body) > 46 else -1)] += 1
    return found


def _keepout_regions(document: bytes) -> Counter[tuple[int, str, str]]:
    """(layer, owner, restrictions) of each keep-out region of ``Regions6``."""
    found: Counter[tuple[int, str, str]] = Counter()
    for record in read_pcbdoc(document).regions:
        if isinstance(record, RegionRecord) and record.prefix.flags2 == KEEPOUT_FLAG:
            prefix = record.prefix
            owner = "free" if prefix.component is None else "component"
            found[(prefix.layer, owner, dict(record.properties.fields).get("KEEPOUTRESTRICTIONS", ""))] += 1
    return found


def test_a_keepout_fill_marker_carries_its_corners_and_byte() -> None:
    name = keepout_lines.fill_marker(FREE, 24) or ""
    assert (
        name
        == keepout_lines.PREFIX
        + "flag24/fill/2000000/2000000/6000000/2000000/6000000/3000000/2000000/3000000"
    )
    assert keepout_lines.parse(name) == (keepout_lines.FILL, FREE, 0, False)
    assert keepout_lines.flag(name) == 24 and keepout_lines.band(*(keepout_lines.parse(name) or ())) == FREE
    assert keepout_lines.fill_marker(FREE, 32) is None and keepout_lines.fill_marker(FREE[:3], 0) is None
    assert keepout_lines.parse(name.replace("flag24", "flag40")) is None
    assert keepout_lines.parse(name.rsplit("/", 1)[0]) is None  # seven numbers are no fill
    assert keepout_lines.read_fill("fill/" + "/".join(str(n) for p in FREE for n in (p.x, p.y)) + "/24") == (
        FREE,
        24,
    )
    assert keepout_lines.read_fill("line/0/0/1/1/2/31") is None


def test_a_keepout_fill_area_is_intact_only_as_a_rectangle() -> None:
    area = _area("kpo", FREE, "F.Cu", 24)
    assert keepout_lines.intact(area)
    skewed = (FREE[0], FREE[1], Point(7 * MM, 3 * MM), FREE[3])
    assert not keepout_lines.intact(dataclasses.replace(area, outline=skewed))  # another outline
    lying = _area("kpo", skewed, "F.Cu", 24)
    assert not keepout_lines.intact(lying)  # its own corners, but no rectangle
    assert not keepout_lines.intact(dataclasses.replace(area, layers=("F.Cu", "B.Cu")))


def test_a_fill_record_holds_the_keepout_flag_and_byte() -> None:
    record = rec.fill_record(BOTTOM, 0x01000020, (0, 0), (10, 20), 0.0, keepout=24)
    body = record[5:]
    assert len(body) == 50 and body[2] == KEEPOUT_FLAG and body[46] == 24
    assert body[42:46] == struct.pack("<I", 0x01000020) and body[47:] == bytes(3)
    plain = rec.fill_record(BOTTOM, 0x01000020, (0, 0), (10, 20), 0.0)[5:]
    assert plain[2] != KEEPOUT_FLAG and plain[46] == 0
    with pytest.raises(ValueError, match="outside"):
        rec.fill_record(BOTTOM, 0x01000020, (0, 0), (10, 20), 0.0, keepout=32)


def test_keepout_fills_are_written_as_keepout_fills(tmp_path: Path) -> None:
    """Scenario "A keep-out fill comes back as a fill": the free area is a keep-out fill of the top layer
    with its byte, the footprint's a keep-out fill of its component on the bottom layer; no keep-out region is
    written beside the board's own rule area. Read again, each is the rule area it was, and the conversion
    names it after its fill."""
    design = _filled()
    document = _written(design)
    assert _keepout_fills(document) == Counter({(TOP, "free", 50, 4): 1, (BOTTOM, "component", 50, 24): 1})
    assert _keepout_regions(document) == _keepout_regions(_written(two_layer()))  # the board's own area
    path = tmp_path / "fills.PcbDoc"
    path.write_bytes(document)
    back = AltiumBackend().read(path).design.board
    assert back is not None
    every = [*back.keepouts, *(area for fp in back.footprints for area in fp.keepouts)]
    areas = [area for area in every if "altium" in area.ext]  # not the board's own area
    read = [keepout_lines.read_fill(dict(area.ext["altium"].payload)["stroke"]) for area in areas]
    assert sorted(found[1] for found in read if found is not None) == [4, 24]
    names = stroke_names(back)
    assert sorted(names) == sorted(area.id for area in areas)  # each area is still its fill's
    assert sorted(keepout_lines.flag(name) for name in names.values()) == [4, 24]


def test_a_conversion_to_kicad_names_keepout_fill_areas(tmp_path: Path) -> None:
    """Scenario "A keep-out fill names its rule area": a conversion to KiCad names the area of each keep-out
    fill with its marker, and the conversion back writes the fills again."""
    path = tmp_path / "altium" / "fills.PcbDoc"
    path.parent.mkdir()
    path.write_bytes(_written(_filled()))
    conversion = convert_project(read_source(path), to="kicad", allow_lossy=True)
    text = conversion.files[conversion.read_back].decode()
    assert text.count(f'(name "{keepout_lines.PREFIX}flag4/fill/') == 1
    assert text.count(f'(name "{keepout_lines.PREFIX}flag24/fill/') == 1
    folder = tmp_path / "kicad"
    for name, data in conversion.files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
    back = convert_project(read_source(folder / conversion.read_back), to="altium", allow_lossy=True)
    document = next(data for name, data in back.files.items() if name.endswith(".PcbDoc"))
    assert _keepout_fills(document) == Counter({(TOP, "free", 50, 4): 1, (BOTTOM, "component", 50, 24): 1})


def test_an_edited_keepout_fill_area_stays_a_region() -> None:
    """Scenario "An edited keep-out fill stays an area": the area of a keep-out fill that forbids vias too is
    written as a keep-out region, and no fill record is written for it."""
    design = _filled()
    assert design.board is not None
    free = dataclasses.replace(design.board.keepouts[-1], no_vias=True)
    edited = dataclasses.replace(design.board, keepouts=(*design.board.keepouts[:-1], free))
    document = _written(dataclasses.replace(design, board=edited))
    assert _keepout_fills(document) == Counter({(BOTTOM, "component", 50, 24): 1})
    assert _keepout_regions(document) - _keepout_regions(_written(two_layer())) == Counter(
        {(TOP, "free", "5"): 1}
    )
