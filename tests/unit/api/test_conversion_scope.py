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
