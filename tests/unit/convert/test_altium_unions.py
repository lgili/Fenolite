# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Union members keep their union through the Altium writer, the import and a trip through KiCad (change
c0460)."""

import dataclasses
import struct
from pathlib import Path

from _convert import two_layer

from fenolite.backends.altium import lower, unions
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.cfb import storage_from_paths, write_compound
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RawPrimitive, RegionRecord
from fenolite.backends.kicad import boardcarrier
from fenolite.convert import altium_storages as storages
from fenolite.convert import convert_project
from fenolite.convert.sources import read_source
from fenolite.core.coords import Point
from fenolite.model.board import Graphic
from fenolite.model.design import Design

UNION = 1048581
"""The index of an authored union (the form of row ``-04``'s via stitching union)."""
NAMES = struct.pack("<I", 1) + struct.pack("<I", UNION) + b"\x0e\x00\x00\x00" + "Union".encode("utf-16-le")
SMART = b"|UNIONINDEX=1048581|UNIONTYPE=2|PLACEHOLDERX=100mil|PLACEHOLDERY=100mil\x00"
MM = 1_000_000


def _record(text: bytes) -> bytes:
    return struct.pack("<I", len(text)) + text


def _members() -> Design:
    """The two-layer board whose first via, first footprint and a filled silkscreen polygon are members of
    ``UNION``, with one more via of no union."""
    design = two_layer()
    board = design.board
    assert board is not None and board.vias and board.footprints
    first, *vias = board.vias
    fp, *footprints = board.footprints
    logo = Graphic(
        id="gfx-logo",
        kind="polygon",
        layer="F.SilkS",
        points=(Point(MM, MM), Point(3 * MM, MM), Point(2 * MM, 3 * MM)),
        filled=True,
    )
    board = dataclasses.replace(
        board,
        vias=(
            unions.with_union(first, UNION),
            *vias,
            dataclasses.replace(
                first, id="via-plain", position=Point(first.position.x + 2 * MM, first.position.y)
            ),
        ),
        footprints=(unions.with_union(fp, UNION), *footprints),
        graphics=(*board.graphics, unions.with_union(logo, UNION)),
    )
    return dataclasses.replace(design, board=board)


def _written(design: Design) -> bytes:
    return lower.write_design(design, allow_lossy=True).files[f"{design.header.name}.PcbDoc"]


def _via_unions(document: bytes) -> list[int]:
    return sorted(
        struct.unpack_from("<I", via.raw, 5 + unions.VIA_UNION_OFFSET)[0]
        for via in read_pcbdoc(document).vias
        if not isinstance(via, RawPrimitive)
    )


def _region_unions(document: bytes) -> list[str]:
    return [
        dict(region.properties.fields)["UNIONINDEX"]
        for region in read_pcbdoc(document).regions
        if isinstance(region, RegionRecord) and dict(region.properties.fields).get("UNIONINDEX", "0") != "0"
    ]


def _component_unions(document: bytes) -> list[str]:
    found = [dict(c.record.fields).get("UNIONINDEX", "0") for c in read_pcbdoc(document).components]
    return [value for value in found if value != "0"]


def test_the_writer_writes_union_members() -> None:
    """Scenario "A via written with its union": the member via holds the index at 70, every other via 0;
    the polygon's region and the footprint's component hold it as ``UNIONINDEX``."""
    document = _written(_members())
    vias = _via_unions(document)
    assert vias.count(UNION) == 1 and set(vias) == {0, UNION}
    assert _region_unions(document) == [str(UNION)]
    assert _component_unions(document) == [str(UNION)]


def test_the_import_keeps_union_members(tmp_path: Path) -> None:
    """Scenario "A stitching via is a union member": read again, the via, the polygon and the footprint
    hold the index in their Altium bag."""
    path = tmp_path / "unions.PcbDoc"
    path.write_bytes(_written(_members()))
    board = AltiumBackend().read(path).design.board
    assert board is not None
    assert unions.members(board).values() and set(unions.members(board).values()) == {UNION}
    assert sum(1 for via in board.vias if unions.union_of(via)) == 1
    assert sum(1 for fp in board.footprints if unions.union_of(fp)) == 1
    assert sum(1 for g in board.graphics if unions.union_of(g)) == 1


def _source(tmp_path: Path) -> Path:
    """The members' document with an authored ``UnionNames`` record and an authored ``SmartUnions``
    record."""
    streams = open_compound(_written(_members())).as_dict()
    streams["UnionNames/Header"] = struct.pack("<I", 1)
    streams["UnionNames/Data"] = NAMES
    streams["SmartUnions/Header"] = struct.pack("<I", 1)
    streams["SmartUnions/Data"] = _record(SMART)
    path = tmp_path / "altium" / "unions.PcbDoc"
    path.parent.mkdir(parents=True)
    path.write_bytes(write_compound(storage_from_paths(streams)))
    return path


def test_union_members_travel_through_kicad(tmp_path: Path) -> None:
    """Scenarios "A stitching via comes back in its union" and "A smart union stays behind"."""
    conversion = convert_project(read_source(_source(tmp_path)), to="kicad", allow_lossy=True)
    text = conversion.files[conversion.read_back].decode()
    found = unions.read_map(boardcarrier.carried(text)[boardcarrier.PREFIX + unions.CARRIER])
    assert sorted(found.values()) == [UNION] * 3
    assert all(f'(uuid "{uuid}")' in text for uuid in found)
    row = next(row for row in conversion.report.rows if row.kind == storages.KIND)
    reasons = {reason.reason: reason.ids for reason in row.reasons}
    assert reasons[storages.SMART_UNION_REASON] == ("SmartUnions",)
    folder = tmp_path / "kicad"
    for name, data in conversion.files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
    back = convert_project(read_source(folder / conversion.read_back), to="altium", allow_lossy=True)
    document = next(data for name, data in back.files.items() if name.endswith(".PcbDoc"))
    streams = open_compound(document).as_dict()
    assert streams["UnionNames/Data"] == NAMES
    assert SMART not in streams.get("SmartUnions/Data", b"")
    vias = _via_unions(document)
    assert vias.count(UNION) == 1 and set(vias) == {0, UNION}
    assert _region_unions(document) == [str(UNION)]
    assert _component_unions(document) == [str(UNION)]


def test_a_map_line_that_is_not_a_member_is_left_out() -> None:
    uuid = unions.union_uuid("via-1")
    assert unions.read_map(f"{uuid} 5\nnot a line\n{uuid.upper()} 6\n{uuid} 0\n".encode()) == {uuid: 5}
    assert unions.carried_map({"via-1": 5}) == f"{uuid} 5\n".encode()
    assert int(uuid.replace("-", ""), 16) >> 80 == unions.UNION_MARKER
