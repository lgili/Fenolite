# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Union members keep their union through the Altium writer, the import and a trip through KiCad (change
c0460)."""

import dataclasses
import struct
from collections import Counter
from pathlib import Path

import pytest
from _altium_board6 import read_document
from _convert import two_layer

from fenolite.backends.altium import lower, unions
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.cfb import storage_from_paths, write_compound
from fenolite.backends.altium.libboard import long_id
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RawPrimitive, RegionRecord
from fenolite.backends.kicad import boardcarrier
from fenolite.convert import altium_storages as storages
from fenolite.convert import convert_project
from fenolite.convert.sources import read_source
from fenolite.core.coords import Point
from fenolite.model.board import Graphic, Size, Text
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


TRACK_UNION, ARC_UNION = 17, 19
"""The indices of the authored track and arc members (the form of row ``-07``'s length tunings)."""


def _strokes() -> Design:
    """The two-layer board whose first track is a member of ``TRACK_UNION`` and whose arc is a member of
    ``ARC_UNION``."""
    design = two_layer()
    board = design.board
    assert board is not None and board.tracks and board.arcs
    first, *tracks = board.tracks
    arc, *arcs = board.arcs
    board = dataclasses.replace(
        board,
        tracks=(unions.with_union(first, TRACK_UNION), *tracks),
        arcs=(unions.with_union(arc, ARC_UNION), *arcs),
    )
    return dataclasses.replace(design, board=board)


def _stroke_unions(document: bytes) -> Counter[tuple[str, int]]:
    """The union members of a document's tracks (36), arcs (48) and vias (70), by kind and index."""
    read = read_pcbdoc(document)
    found: Counter[tuple[str, int]] = Counter()
    for kind, items, offset in (
        ("track", read.tracks, unions.TRACK_UNION_OFFSET),
        ("arc", read.arcs, unions.ARC_UNION_OFFSET),
        ("via", read.vias, unions.VIA_UNION_OFFSET),
    ):
        for item in items:
            body = bytes(item.raw)[5:]
            index = struct.unpack_from("<I", body, offset)[0] if len(body) >= offset + 4 else 0
            if index:
                found[kind, index] += 1
    return found


def _all_unions(document: bytes) -> Counter[tuple[str, int]]:
    """Every union member of a document by kind and index: tracks, arcs and vias (``_stroke_unions``), texts
    (119 of their first subrecord), regions of both storages and components (``UNIONINDEX``)."""
    found = _stroke_unions(document)
    read = read_pcbdoc(document)
    for item in read.texts:
        if isinstance(item, RawPrimitive):
            continue
        raw = bytes(item.raw)
        first = raw[5 : 5 + struct.unpack_from("<I", raw, 1)[0]]
        if len(first) >= unions.TEXT_UNION_OFFSET + 4 and (index := struct.unpack_from("<I", first, 119)[0]):
            found["text", index] += 1
    for kind, records in (("region", (*read.regions, *read.shape_regions)), ("component", read.components)):
        for record in records:
            if isinstance(record, RawPrimitive):
                continue
            fields = dict(record.properties.fields if kind == "region" else record.record.fields)
            value = fields.get("UNIONINDEX", "0")
            if value.isdigit() and int(value):
                found[kind, int(value)] += 1
    return found


def test_a_track_and_an_arc_are_written_in_their_union() -> None:
    """Scenario "A length tuning comes back in its union" (S-2190): the member track is written in the
    49-byte form with its index at 36, the member arc in the 60-byte form with its index at 48, each with
    its layer's long id and no restriction; the other tracks keep the 36-byte form, and the import reads
    both members again."""
    document = _written(_strokes())
    assert _stroke_unions(document) == Counter({("track", TRACK_UNION): 1, ("arc", ARC_UNION): 1})
    read = read_pcbdoc(document)
    tracks = [bytes(t.raw)[5:] for t in read.tracks if not isinstance(t, RawPrimitive)]
    (member,) = [body for body in tracks if len(body) == 49]
    assert struct.unpack_from("<IBIB", member, 36) == (TRACK_UNION, 0, long_id(1), 0)
    assert all(len(body) == 36 for body in tracks if body is not member)
    arcs = [bytes(a.raw)[5:] for a in read.arcs if not isinstance(a, RawPrimitive)]
    (arc,) = [body for body in arcs if len(body) == 60]
    assert struct.unpack_from("<BIIB", arc, 47) == (0, ARC_UNION, long_id(1), 0)
    _, imported = read_document(document, "strokes.PcbDoc")
    assert imported.board is not None
    assert sorted(unions.members(imported.board).values()) == [TRACK_UNION, ARC_UNION]


UNION_ROWS = ("02", "07")
"""The public rows whose union members are free tracks and arcs (S-2190): ``-02`` 16 tracks, ``-07`` 27
tracks and 20 arcs; every other member of theirs is a via."""


def _row(row: str) -> Path:
    from _corpus import manifest_items, require

    (item,) = [i for i in manifest_items("altium-pcbdoc") if i.id == f"altium-third-party-pcbdoc-{row}"]
    return require(item)


@pytest.mark.needs_corpus
@pytest.mark.parametrize("row", UNION_ROWS)
def test_row_union_strokes_survive_kicad(tmp_path: Path, row: str) -> None:
    """A conversion to KiCad and back writes every track, arc and via member of the row in its union."""
    source = _row(row)
    conversion = convert_project(read_source(source), to="kicad", allow_lossy=True)
    folder = tmp_path / "kicad"
    for name, data in conversion.files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
    back = convert_project(read_source(folder / conversion.read_back), to="altium", allow_lossy=True)
    document = next(data for name, data in back.files.items() if name.endswith(".PcbDoc"))
    before = _stroke_unions(source.read_bytes())
    assert sum(n for (kind, _), n in before.items() if kind != "via") == {"02": 16, "07": 47}[row]
    assert _stroke_unions(document) == before


FLOW_A_MEMBERS = {"01": 2, "04": 22, "07": 47}
"""The union members of the rows flow A is run on: ``-01``'s overlay region (one record in each region
storage), ``-04``'s 22 stitching vias, ``-07``'s 27 tracks and 20 arcs of five length-tuning unions."""


@pytest.mark.needs_corpus
@pytest.mark.parametrize("row", sorted(FLOW_A_MEMBERS))
def test_flow_a_keeps_row_unions(tmp_path: Path, row: str) -> None:
    """Scenario "Union members survive flow A" (``import --to python``, ``build``, ``convert --to altium``):
    the build gives each table row a uuid of its own, and the import names the members by those uuids in
    the carried map, so every member comes back with its index (the VM finding at 332b79837: ``-07``'s 47
    members became 0)."""
    from fenolite.api import run

    stamp = "2026-11-06T00:00:00Z"

    def go(*args: str) -> None:
        planned = run(*args, "--dry-run", cwd=tmp_path, timestamp=stamp)
        assert planned.exit_code == 0, planned.error
        plan = str(planned.result["plan_id"])
        done = run(*args, "--confirm", "--plan", plan, cwd=tmp_path, timestamp=stamp)
        assert done.exit_code == 0, done.error

    source = _row(row)
    go("import", str(source), "--to", "python", "--out", "py", "--licence", "CC0-1.0", "--copyright",
       "2026 Fenolite contributors", "--allow-lossy")  # fmt: skip
    go("build", str(tmp_path / "py" / "design.py"), "--out", "b")
    (built,) = (tmp_path / "b").glob("*.kicad_pcb")
    go("convert", str(built), "--to", "altium", "--out", "alt", "--allow-lossy")
    (path,) = (tmp_path / "alt").glob("*.PcbDoc")
    before = _all_unions(source.read_bytes())
    assert sum(before.values()) == FLOW_A_MEMBERS[row]
    assert _all_unions(path.read_bytes()) == before


TEXT_UNION = 77
"""The index of the authored text members (the form of row ``-08``'s union 77)."""


def _text_unions(document: bytes) -> list[tuple[str, int]]:
    """The non-zero union index at 119 of each text record's first subrecord, with the text's role."""
    found: list[tuple[str, int]] = []
    for item in read_pcbdoc(document).texts:
        if isinstance(item, RawPrimitive):
            continue
        raw = bytes(item.raw)
        first = raw[5 : 5 + struct.unpack_from("<I", raw, 1)[0]]
        index = struct.unpack_from("<I", first, unions.TEXT_UNION_OFFSET)[0]
        if index:
            role = "designator" if item.is_designator else "comment" if item.is_comment else "free"
            found.append((role, index))
    return sorted(found)


def _text_members() -> Design:
    """The two-layer board whose first footprint and a free silkscreen text are members of ``TEXT_UNION``."""
    design = two_layer()
    board = design.board
    assert board is not None and board.footprints
    fp, *footprints = board.footprints
    label = Text(
        id="txt-label",
        text="L",
        position=Point(4 * MM, 4 * MM),
        layer="F.SilkS",
        size=Size(MM, MM),
        thickness=MM // 10,
    )
    board = dataclasses.replace(
        board,
        footprints=(unions.with_union(fp, TEXT_UNION), *footprints),
        texts=(*board.texts, unions.with_union(label, TEXT_UNION)),
    )
    return dataclasses.replace(design, board=board)


def test_texts_are_written_in_their_union(tmp_path: Path) -> None:
    """Scenario "A text keeps its union" (S-2190): a free text member holds its index at 119, the
    designator and comment of a member component hold the component's, every other text 0; the import
    reads the free text's index again."""
    document = _written(_text_members())
    roles = [role for role, index in _text_unions(document) if index == TEXT_UNION]
    assert sorted(roles) == ["comment", "designator", "free"]
    assert {index for _, index in _text_unions(document)} == {TEXT_UNION}
    path = tmp_path / "texts.PcbDoc"
    path.write_bytes(document)
    read = AltiumBackend().read(path).design.board
    assert read is not None
    assert [unions.union_of(t) for t in read.texts if t.text == "L"] == [TEXT_UNION]


def test_flow_a_keeps_a_text_member(tmp_path: Path) -> None:
    """Flow A of an authored document with ``UnionNames`` whose free text is a member: the build gives the
    text a uuid of its own, and the import names it by that uuid in the carried map, so the written free
    text holds its index at 119 again. A member footprint is not carried through flow A yet (the build
    gives it a uuid the import does not map; c0460 task 2.4)."""
    from fenolite.api import run

    streams = open_compound(_written(_text_members())).as_dict()
    names = struct.pack("<I", 1) + struct.pack("<II", TEXT_UNION, 10) + "Texts".encode("utf-16-le")
    streams["UnionNames/Header"] = struct.pack("<I", 1)
    streams["UnionNames/Data"] = names
    source = tmp_path / "src" / "texts.PcbDoc"
    source.parent.mkdir()
    source.write_bytes(write_compound(storage_from_paths(streams)))
    stamp = "2026-11-06T00:00:00Z"

    def go(*args: str) -> None:
        planned = run(*args, "--dry-run", cwd=tmp_path, timestamp=stamp)
        assert planned.exit_code == 0, planned.error
        plan = str(planned.result["plan_id"])
        done = run(*args, "--confirm", "--plan", plan, cwd=tmp_path, timestamp=stamp)
        assert done.exit_code == 0, done.error

    go("import", str(source), "--to", "python", "--out", "py", "--licence", "CC0-1.0", "--copyright",
       "2026 Fenolite contributors", "--allow-lossy")  # fmt: skip
    go("build", str(tmp_path / "py" / "design.py"), "--out", "b")
    (built,) = (tmp_path / "b").glob("*.kicad_pcb")
    go("convert", str(built), "--to", "altium", "--out", "alt", "--allow-lossy")
    (path,) = (tmp_path / "alt").glob("*.PcbDoc")
    free = [found for found in _text_unions(path.read_bytes()) if found[0] == "free"]
    assert free == [("free", TEXT_UNION)]
