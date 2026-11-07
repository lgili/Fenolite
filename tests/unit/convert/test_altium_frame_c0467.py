# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The frame and origin of an Altium document through KiCad and back (change c0467): the board property
``Fenolite.Altium.Frame`` carries the document's origin and the edge's corner, and the conversion back
writes the board where KiCad holds it, with the origin moved with the board. The documents here are
authored for Fenolite with the writer; the public rows are read from the corpus cache."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _altium_board6 import OFFSET_NM, bare_spec
from _convert import two_layer

from fenolite.api import run
from fenolite.backends.altium import lower, pcbdoc
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.backends.kicad import boardcarrier
from fenolite.convert import altium_frame, convert_project
from fenolite.convert.altium_planes import edge_corner
from fenolite.convert.sources import read_source
from fenolite.core.coords import Point

MIL = 25_400
STAMP = "2026-11-06T00:00:00Z"
ABOVE = Point(OFFSET_NM, OFFSET_NM + 30 * MIL)
"""The authored origin: 30 mil above the outline's lower-left corner, which the writer puts at 1000 mil."""


def _document(tmp_path: Path) -> Path:
    path = tmp_path / "source" / "frame.PcbDoc"
    path.parent.mkdir(parents=True)
    path.write_bytes(pcbdoc.write_pcbdoc(bare_spec(origin=ABOVE), filename=path.name))
    return path


def _to_kicad(tmp_path: Path, source: Path) -> Path:
    kicad = convert_project(read_source(source), to="kicad", allow_lossy=True)
    folder = tmp_path / "kicad"
    for name, data in kicad.files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
    return folder / kicad.read_back


def _back(board: Path) -> tuple[PcbDocument, object]:
    back = convert_project(read_source(board), to="altium", allow_lossy=True)
    (written,) = [data for name, data in back.files.items() if name.endswith(".PcbDoc")]
    return read_pcbdoc(written), back.report


def _origin(document: PcbDocument) -> tuple[str | None, str | None]:
    fields = dict(document.board.record.fields)
    return fields.get("ORIGINX"), fields.get("ORIGINY")


def _vertices(document: PcbDocument) -> set[tuple[object, object]]:
    return {(v.x, v.y) for v in document.board.outline}


def _box(document: PcbDocument) -> tuple[object, ...]:
    xs, ys = [v.x for v in document.board.outline], [v.y for v in document.board.outline]
    return min(xs), min(ys), max(xs), max(ys)


def test_the_carrier_reads_what_it_writes() -> None:
    carried = altium_frame.Carried(Point(1, -2), Point(3, -4))
    data = altium_frame.carrier_text(carried).encode("utf-8")
    assert altium_frame.read_carrier(data) == carried
    assert altium_frame.read_carrier(None) is None
    assert altium_frame.read_carrier(b"{not json") is None
    assert altium_frame.read_carrier(b'{"schema": "other", "origin": [1, 2]}') is None
    assert altium_frame.read_carrier(b'{"schema": "fenolite.altium-frame.v0", "origin": [1]}') is None
    corner = b'{"schema": "fenolite.altium-frame.v0", "origin": [1, 2], "corner": null}'
    assert altium_frame.read_carrier(corner) == altium_frame.Carried(Point(1, 2))


def test_the_kicad_board_carries_the_origin(tmp_path: Path) -> None:
    """The conversion to KiCad writes the source's origin in the frame of the design, and the corner."""
    board = _to_kicad(tmp_path, _document(tmp_path))
    carried = altium_frame.read_carrier(boardcarrier.carried(board.read_text("utf-8"))[altium_frame.PROPERTY])
    assert carried is not None
    assert carried.origin == Point(ABOVE.x, -ABOVE.y)
    read = read_source(board).design.board
    assert read is not None
    assert carried.corner == edge_corner(read)
    assert carried.corner is not None and carried.corner.x == OFFSET_NM


def test_the_board_comes_back_where_it_was(tmp_path: Path) -> None:
    """Scenario "An origin above the corner": the written outline's lowest vertex stays at 1000 mil and the
    origin 30 mil above it, as in the source, and nothing is reported under ``outline``."""
    source = _document(tmp_path)
    written, report = _back(_to_kicad(tmp_path, source))
    original = read_pcbdoc(source.read_bytes())
    assert _origin(written) == _origin(original) == ("1000mil", "1030mil")
    assert _vertices(written) == _vertices(original)
    assert report.row("outline") is None  # type: ignore[attr-defined]


def test_a_board_moved_in_kicad_keeps_its_origin_with_it(tmp_path: Path) -> None:
    """Scenario "A board moved in KiCad keeps its origin with it": the edge moved by (10 mm, 5 mm) in
    KiCad's frame moves the origin by (10 mm, −5 mm) in Altium's."""
    board = _to_kicad(tmp_path, _document(tmp_path))
    carried = altium_frame.read_carrier(boardcarrier.carried(board.read_text("utf-8"))[altium_frame.PROPERTY])
    assert carried is not None
    design = read_source(board).design.board
    assert design is not None
    moved = dataclasses.replace(
        design,
        graphics=tuple(
            dataclasses.replace(g, points=tuple(Point(p.x + 10_000_000, p.y + 5_000_000) for p in g.points))
            if g.layer == "Edge.Cuts"
            else g
            for g in design.graphics
        ),
    )
    assert altium_frame.restored(design, carried) == ABOVE
    assert altium_frame.restored(moved, carried) == Point(ABOVE.x + 10_000_000, ABOVE.y - 5_000_000)


def test_a_board_at_a_negative_coordinate_is_anchored_and_reported() -> None:
    """The committed two-layer board lies below KiCad's X axis (Y > 0): written at its coordinates it would
    lie at negative Altium Y, so it is anchored at its corner and one ``outline`` change says so."""
    design = two_layer()
    written = lower.write_design(design, allow_lossy=True, frame_origin=Point(0, 0))
    document = read_pcbdoc(written.files[f"{design.header.name}.PcbDoc"])
    assert _origin(document) == ("1000mil", "1000mil")
    reasons = written.inputs.changed.get("outline", {})
    assert list(reasons) == [lower.FRAME_ANCHORED]


ROWS = ("01", "02", "03", "04", "05", "06", "07")


def _row(row: str) -> Path:
    from _corpus import manifest_items, require

    (item,) = [i for i in manifest_items("altium-pcbdoc") if i.id == f"altium-third-party-pcbdoc-{row}"]
    return require(item)


@pytest.mark.needs_corpus
@pytest.mark.parametrize("row", ROWS)
def test_row_frame_survives_kicad(tmp_path: Path, row: str) -> None:
    """Scenario "Row -04 comes back where it was", on every public row (S-2262): the written origin and the
    outline's box equal the source's; on row -04 the outline's vertices too."""
    source = _row(row)
    written, _ = _back(_to_kicad(tmp_path, source))
    original = read_pcbdoc(source.read_bytes())
    assert _origin(written) == _origin(original)
    assert _box(written) == _box(original)
    if row == "04":
        assert _vertices(written) == _vertices(original)


def _components(document: PcbDocument) -> list[tuple[str, object, object]]:
    return sorted((c.source_designator or "", c.x, c.y) for c in document.components)


@pytest.mark.needs_corpus
def test_flow_a_keeps_the_frame(tmp_path: Path) -> None:
    """Scenario "Flow A keeps the frame" (S-2262): ``import --to python``, ``build`` and ``convert --to
    altium`` of row -04 write its origin, its outline vertices and each component's X and Y as the source
    holds them."""
    source = _row("04")

    def go(*args: str) -> None:
        planned = run(*args, "--dry-run", cwd=tmp_path, timestamp=STAMP)
        assert planned.exit_code == 0, planned.error
        done = run(
            *args, "--confirm", "--plan", str(planned.result["plan_id"]), cwd=tmp_path, timestamp=STAMP
        )
        assert done.exit_code == 0, done.error

    go("import", str(source), "--to", "python", "--out", "py", "--licence", "CC0-1.0", "--copyright",
       "2026 Fenolite contributors", "--allow-lossy")  # fmt: skip
    go("build", str(tmp_path / "py" / "design.py"), "--out", "b")
    (built,) = (tmp_path / "b").glob("*.kicad_pcb")
    go("convert", str(built), "--to", "altium", "--out", "alt", "--allow-lossy")
    (path,) = (tmp_path / "alt").glob("*.PcbDoc")
    written, original = read_pcbdoc(path.read_bytes()), read_pcbdoc(source.read_bytes())
    assert _origin(written) == _origin(original) == ("12731.9892mil", "8796.6702mil")
    assert _vertices(written) == _vertices(original)
    assert _components(written) == _components(original)
