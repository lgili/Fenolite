# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The scope of a conversion's verification (capability design-conversion, "Board comparison of placed
components" and "Several footprints of one component"; change c0371). Authored variants of the public
Altium blink, made in memory."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from fenolite.api.conversion import verify_conversion
from fenolite.convert import convert_project
from fenolite.convert.sources import SourceProject, read_source

BLINK = Path(__file__).resolve().parents[2] / "data" / "altium" / "blink" / "blink.PrjPcb"


def _source(change: str) -> tuple[SourceProject, str]:
    """The blink read, with the footprint of one part removed (``unplaced``) or placed twice (``twice``)."""
    source = read_source(BLINK)
    board = source.design.board
    assert board is not None
    refs = {c.id: c.ref for c in source.design.circuit.components}
    chosen = next(fp for fp in board.footprints if refs[fp.component_id].startswith("R"))
    if change == "unplaced":
        footprints = tuple(fp for fp in board.footprints if fp is not chosen)
    else:
        twin = dataclasses.replace(
            chosen,
            id=chosen.id + "-twin",
            position=dataclasses.replace(chosen.position, x=chosen.position.x + 5_000_000),
            pads=tuple(dataclasses.replace(pad, id=pad.id + "-twin") for pad in chosen.pads),
        )
        footprints = (*board.footprints, twin)
    design = dataclasses.replace(source.design, board=dataclasses.replace(board, footprints=footprints))
    return dataclasses.replace(source, design=design), refs[chosen.component_id]


def _unexplained(source: SourceProject) -> list[tuple[str, str]]:
    result = verify_conversion(convert_project(source, to="kicad", allow_lossy=True))
    return [(d.kind, d.where) for d in result.unexplained]


def test_schematic_only_component_is_left_to_the_schematic() -> None:
    source, ref = _source("unplaced")
    assert not [d for d in _unexplained(source) if d[1] == ref]


def test_one_component_of_two_footprints_is_explained() -> None:
    source, ref = _source("twice")
    assert not [d for d in _unexplained(source) if d == ("ref-ambiguous", ref)]


def test_embedded_board_array_is_a_refused_loss(monkeypatch: pytest.MonkeyPatch) -> None:
    """change c0374: a board that places other PCB documents is not called converted. The detector reads
    only the storage's record count (``holds_embedded_boards``); here it is made to answer yes."""
    import fenolite.backends.altium.read.cfb as cfb
    from fenolite.convert import LossyConversionError

    monkeypatch.setattr(cfb, "holds_embedded_boards", lambda _data: True)
    with pytest.raises(LossyConversionError):
        convert_project(read_source(BLINK), to="kicad")
    conversion = convert_project(read_source(BLINK), to="kicad", allow_lossy=True)
    row = next(row for row in conversion.report.rows if row.kind == "embedded-board")
    assert (row.source, row.lost) == (1, 1)


def test_each_embedded_array_is_a_named_item(monkeypatch: pytest.MonkeyPatch) -> None:
    """change c0374, task 2.2: the report names each array of the board, with its document and counts
    (``read.arrays``), and still refuses the loss."""
    from fractions import Fraction

    import fenolite.backends.altium.read.arrays as arrays
    import fenolite.backends.altium.read.cfb as cfb

    def two(_data: bytes) -> tuple[arrays.BoardArray, ...]:
        one = arrays.BoardArray(
            "board.PcbDoc", Fraction(0), Fraction(0), 0.0, False, 1, 1, Fraction(1), Fraction(1), False
        )
        return (one, dataclasses.replace(one, rows=2, cols=3))

    monkeypatch.setattr(cfb, "holds_embedded_boards", lambda _data: True)
    monkeypatch.setattr(arrays, "board_arrays", two)
    conversion = convert_project(read_source(BLINK), to="kicad", allow_lossy=True)
    row = next(row for row in conversion.report.rows if row.kind == "embedded-board")
    assert (row.source, row.lost) == (2, 2)
    assert row.ids() == ("blink.PcbDoc#1:board.PcbDoc 1x1", "blink.PcbDoc#2:board.PcbDoc 3x2")


def test_referenced_documents_are_read_beside_the_board(tmp_path: Path) -> None:
    """change c0386, task 2.1: each array's document is taken relative to the board's document; a present
    PCB document reads, and a missing, an unreadable and an absolute one are told apart."""
    from fenolite.convert.arrays import referenced_document

    panel = tmp_path / "panel.PcbDoc"
    panel.write_bytes(b"")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "board.PcbDoc").write_bytes(BLINK.with_suffix(".PcbDoc").read_bytes())
    (tmp_path / "notes.PcbDoc").write_bytes(b"not a compound file")
    assert referenced_document(panel, "sub\\board.PcbDoc") == (tmp_path / "sub" / "board.PcbDoc", "read")
    assert referenced_document(panel, "sub/board.PcbDoc")[1] == "read"
    assert referenced_document(panel, "absent.PcbDoc") == (None, "missing")
    assert referenced_document(panel, "notes.PcbDoc") == (tmp_path / "notes.PcbDoc", "unreadable")
    for absolute in ("C:\\work\\board.PcbDoc", "\\\\host\\share\\board.PcbDoc", "/work/board.PcbDoc", ""):
        assert referenced_document(panel, absolute) == (None, "absolute"), absolute


def test_each_array_names_how_its_document_reads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """change c0386, task 2.1: the report's reason says whether each array's document reads, and an absolute
    path is named by its file name only; the array whose document reads, unturned and unmirrored with its
    origin at its shape's lower-left corner, is placed (task 2.2), the others stay refused losses. Change
    c0428: the absolute path whose file is beside the board is read by its file name and placed."""
    import shutil
    from fractions import Fraction

    import fenolite.backends.altium.read.arrays as arrays
    import fenolite.backends.altium.read.cfb as cfb
    from fenolite.convert.arrays import FOUND
    from fenolite.convert.report import (
        EMBEDDED_BOARD_FOUND,
        EMBEDDED_BOARD_MISSING,
        EMBEDDED_BOARD_PLACED,
        EMBEDDED_BOARD_UNREADABLE,
    )

    for path in BLINK.parent.iterdir():
        shutil.copyfile(path, tmp_path / path.name)
    shutil.copyfile(BLINK.with_suffix(".PcbDoc"), tmp_path / "board.PcbDoc")
    (tmp_path / "broken.PcbDoc").write_bytes(b"not a compound file")
    one = arrays.BoardArray(
        "board.PcbDoc", Fraction(0), Fraction(0), 0.0, False, 1, 1, Fraction(1), Fraction(1), False
    )
    found = (
        one,
        dataclasses.replace(one, document="gone.PcbDoc"),
        dataclasses.replace(one, document="broken.PcbDoc"),
        dataclasses.replace(one, document="D:\\vm\\work\\board.PcbDoc"),
    )
    monkeypatch.setattr(cfb, "holds_embedded_boards", lambda _data: True)
    monkeypatch.setattr(arrays, "board_arrays", lambda _data: found)
    conversion = convert_project(read_source(tmp_path / BLINK.name), to="kicad", allow_lossy=True)
    row = next(row for row in conversion.report.rows if row.kind == "embedded-board")
    assert (row.source, row.changed, row.lost, row.loss) == (4, 2, 2, "refuse")
    reasons = {ident: reason.reason for reason in row.reasons for ident in reason.ids}
    found_by_name = EMBEDDED_BOARD_FOUND.format(how=FOUND["name"])
    assert reasons == {
        "blink.PcbDoc#1:board.PcbDoc 1x1": EMBEDDED_BOARD_PLACED,
        "blink.PcbDoc#2:gone.PcbDoc 1x1": EMBEDDED_BOARD_MISSING,
        "blink.PcbDoc#3:broken.PcbDoc 1x1": EMBEDDED_BOARD_UNREADABLE,
        "blink.PcbDoc#4:board.PcbDoc 1x1": f"{EMBEDDED_BOARD_PLACED}; {found_by_name}",
    }
    assert "vm" not in " ".join(reasons)


def test_documents_without_arrays_hold_none() -> None:
    from fenolite.backends.altium.read.cfb import holds_embedded_boards

    assert not holds_embedded_boards(BLINK.with_suffix(".PcbDoc").read_bytes())
    assert not holds_embedded_boards(b"not a compound file")


def test_board_in_a_project_subfolder_converts_as_beside(tmp_path: Path) -> None:
    """change c0371: the board document of a project that keeps it in ``PCB/`` is found (its rules,
    zone outlines, models and embedded-board check read it), so the conversion reports what it reports
    for the same board beside the project file."""
    import shutil

    from fenolite.convert.altium_to_kicad import board_document

    root = Path(shutil.copytree(BLINK.parent, tmp_path / "blink"))
    (root / "PCB").mkdir()
    (root / "blink.PcbDoc").rename(root / "PCB" / "blink.PcbDoc")
    project = root / "blink.PrjPcb"
    project.write_bytes(
        project.read_bytes().replace(b"DocumentPath=blink.PcbDoc", b"DocumentPath=PCB\\blink.PcbDoc")
    )
    moved = read_source(project)
    assert board_document(moved, moved.design) == root / "PCB" / "blink.PcbDoc"
    rows = {
        row.kind: (row.source, row.lost, row.changed)
        for row in convert_project(moved, to="kicad", allow_lossy=True).report.rows
    }
    beside = convert_project(read_source(BLINK), to="kicad", allow_lossy=True)
    assert rows == {row.kind: (row.source, row.lost, row.changed) for row in beside.report.rows}


def test_refused_generated_schematic_is_a_declared_loss(monkeypatch: pytest.MonkeyPatch) -> None:
    """change c0372: when the schematic generator cannot lay the circuit out (here: a page too small for
    the blink), the board is still converted and the schematic is a loss that needs --allow-lossy."""
    import fenolite.backends.kicad.schlayout as schlayout
    from fenolite.convert import LossyConversionError

    name, _, _ = schlayout.PAPERS[0]
    monkeypatch.setattr(schlayout, "PAPERS", ((name, 20_000_000, 20_000_000),))
    with pytest.raises(LossyConversionError):
        convert_project(read_source(BLINK), to="kicad")
    conversion = convert_project(read_source(BLINK), to="kicad", allow_lossy=True)
    assert not [i for i in conversion.issues if i.severity == "error"]
    assert conversion.schematic is None and conversion.read_back in conversion.files
    row = next(row for row in conversion.report.rows if row.kind == "schematic")
    assert row.lost == 1


def test_lost_schematic_explains_schematic_only_components(monkeypatch: pytest.MonkeyPatch) -> None:
    """change c0372: without a written schematic, a component that no footprint places is lost with it,
    and that loss explains its ``component-missing``."""
    import fenolite.backends.kicad.schlayout as schlayout

    name, _, _ = schlayout.PAPERS[0]
    monkeypatch.setattr(schlayout, "PAPERS", ((name, 20_000_000, 20_000_000),))
    source, ref = _source("unplaced")
    assert not [d for d in _unexplained(source) if d[1] == ref]


@pytest.mark.needs_corpus
def test_arc_zones_of_a_board_in_a_subfolder_keep_their_outline(tmp_path: Path) -> None:
    """change c0371: the zone outlines with an arc vertex are read from the board document in ``PCB/``
    (they were dropped as having no outline). A public board with two such zones, alone in a project."""
    import shutil

    from _corpus import manifest_items, require

    (item,) = [i for i in manifest_items("altium-pcbdoc") if i.id == "altium-third-party-pcbdoc-02"]
    document = require(item)
    (tmp_path / "PCB").mkdir()
    shutil.copy(document, tmp_path / "PCB" / document.name)
    project = tmp_path / "board.PrjPcb"
    project.write_text(f"[Design]\nVersion=1.0\n\n[Document1]\nDocumentPath=PCB\\{document.name}\n", "utf-8")
    rows = [
        convert_project(read_source(path), to="kicad", allow_lossy=True).report.row("zone")
        for path in (project, document)
    ]
    assert [(row.source, row.lost, row.changed) for row in rows] == [(12, 0, 2)] * 2


def test_a_copper_shape_keeps_its_net_in_kicad() -> None:
    """change c0376: an Altium region on copper (here added to the blink, on the net of a pad) is written
    to KiCad on its net, not as copper of no net."""
    from fenolite.backends.kicad.sexpr import parse
    from fenolite.core.coords import Point
    from fenolite.model.base import ExtBag
    from fenolite.model.board import Graphic

    source = read_source(BLINK)
    board = source.design.board
    assert board is not None
    net = source.design.circuit.nets[0]
    region = Graphic(
        id="gfx-c0376",
        ext={"altium": ExtBag(payload=(("net", net.name),))},
        kind="polygon",
        layer="F.Cu",
        points=(Point(0, 0), Point(1_000_000, 0), Point(0, 1_000_000)),
        filled=True,
        net_id=net.id,
    )
    design = dataclasses.replace(
        source.design, board=dataclasses.replace(board, graphics=(*board.graphics, region))
    )
    conversion = convert_project(dataclasses.replace(source, design=design), to="kicad", allow_lossy=True)
    root = parse(conversion.files[conversion.read_back].decode("utf-8"))
    polygons = [node for node in root.nodes() if node.name == "gr_poly"]
    named = [p for p in polygons if (found := p.find("net")) is not None and found.atoms()]
    assert [p.find("net").atoms()[0].value for p in named] == [net.name]  # type: ignore[union-attr]
    assert not verify_conversion(conversion).unexplained


def test_a_copper_shape_of_a_project_takes_the_sheet_net(monkeypatch: pytest.MonkeyPatch) -> None:
    """change c0376: in a project the board's nets are joined to the nets of the sheets, and a copper region
    read on a net (here added to the blink's PCB document, on the net of its first pad) takes the sheet
    net's id as the pads and tracks do; the conversion writes it on that net (it failed with a ``KeyError``
    on a net id that the joined circuit does not hold)."""
    import _altium_records as rec

    import fenolite.backends.altium.read.pcb as pcb_reader
    from fenolite.backends.kicad.sexpr import parse

    original = pcb_reader.read_pcbdoc

    def with_region(data: bytes, **kwargs: object) -> object:
        document = original(data, **kwargs)  # type: ignore[arg-type]
        pad = document.pads[0]
        half = 50 * rec.MIL
        square = [(pad.x - half, pad.y - half), (pad.x + half, pad.y - half), (pad.x + half, pad.y + half)]
        region = rec.region(square, layer=1, net=pad.prefix.net)
        return dataclasses.replace(document, regions=(*document.regions, region))

    monkeypatch.setattr(pcb_reader, "read_pcbdoc", with_region)
    source = read_source(BLINK)
    net_ids = {net.id for net in source.design.circuit.nets}
    board = source.design.board
    assert board is not None
    shaped = [g for g in board.graphics if g.net_id is not None]
    assert shaped and all(g.net_id in net_ids for g in shaped)
    conversion = convert_project(source, to="kicad", allow_lossy=True)
    root = parse(conversion.files[conversion.read_back].decode("utf-8"))
    polygons = [node for node in root.nodes() if node.name == "gr_poly"]
    named = [p.find("net").atoms()[0].value for p in polygons if p.find("net") is not None]  # type: ignore[union-attr]
    pad_net = next(net.name for net in source.design.circuit.nets if net.id == shaped[0].net_id)
    assert named == [pad_net]
