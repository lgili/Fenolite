# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.convert.arrays``: the copies of an Altium Embedded Board Array placed by the measured rule
(change c0386, task 2.2). The board is ``tests/data/panels/board.py`` built for Altium and the panel is
written by ``panel.altium.embedded_files``, both authored for Fenolite; the copies are compared with the
flattened panel of the same layout (``panel.altium.panel_design``), a placement computed independently.
With ``FENOLITE_ALTIUM_PANEL_OUTPUTS=<folder>`` (the folder of ``test_panel_placement.py``, outside the
repository) the panels that Altium saved are converted as well and their copies' holes compared with
Altium's drill files."""

from __future__ import annotations

import dataclasses
import os
import re
import shutil
from collections.abc import Iterable
from fractions import Fraction
from pathlib import Path

import pytest
from _panels import build_board

import fenolite.backends.altium.read.arrays as arrays_reader
from fenolite.backends.altium.read.pcbstack import OutlineVertex
from fenolite.convert import arrays, convert_project
from fenolite.convert.report import (
    EMBEDDED_BOARD_ANGLE,
    EMBEDDED_BOARD_CORNER,
    EMBEDDED_BOARD_LINKED,
    EMBEDDED_BOARD_MIRRORED,
    EMBEDDED_BOARD_PLACED,
    EMBEDDED_BOARD_TURNED,
)
from fenolite.convert.sources import read_source
from fenolite.core.coords import Point
from fenolite.dsl import Panel, mm, to_model
from fenolite.model.design import Design
from fenolite.panel import build as panel_build
from fenolite.panel.altium import embedded_files, panel_design
from fenolite.panel.layout import layout

MM = 1_000_000
QUARTER = 90_000_000
COPY = re.compile(r"_B(\d+)$")


@pytest.fixture(scope="module")
def kit(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Design]:
    """``board.PcbDoc`` and ``panel.PcbDoc`` (2 x 2 copies, 2 mm tabbed gaps) in one folder; the flattened
    panel's design."""
    folder = tmp_path_factory.mktemp("c0386-panel")
    board = build_board(folder, "altium")
    panel = Panel("panel", board=board.name)
    panel.grid(2, 2, gap=mm(2))
    panel.separate("tabs", between="columns")
    panel.separate("tabs", between="rows")
    model = to_model(panel)
    design, _ = panel_build.read_source(board)
    laid = layout(model, design)
    files, issues = embedded_files(model, laid, design, board.name)
    assert files and not [i for i in issues if i.severity == "error"], issues
    for name, data in files.items():
        (folder / name).write_bytes(data)
    flat, issues = panel_design(model, laid, design)
    assert not [i for i in issues if i.severity == "error"], issues
    return folder / "panel.PcbDoc", flat


def _places(design: Design, refs: Iterable[str] | None = None) -> list[tuple[int, int, int]]:
    """The footprints of ``design`` whose component's designator is in ``refs`` (every one when ``None``),
    as (x, y, rotation) taken from the least x and y of them, sorted."""
    board = design.board
    assert board is not None
    by_id = {c.id: c.ref for c in design.circuit.components}
    chosen = set(refs) if refs is not None else None
    found = [fp for fp in board.footprints if chosen is None or by_id.get(fp.component_id) in chosen]
    assert found
    x0 = min(fp.position.x for fp in found)
    y0 = min(fp.position.y for fp in found)
    return sorted((fp.position.x - x0, fp.position.y - y0, fp.rotation) for fp in found)


def _close(a: list[tuple[int, int, int]], b: list[tuple[int, int, int]], tolerance: int = 10) -> bool:
    return len(a) == len(b) and all(
        abs(p[0] - q[0]) <= tolerance and abs(p[1] - q[1]) <= tolerance and p[2] == q[2]
        for p, q in zip(a, b, strict=True)
    )


def test_shape_corner_takes_the_arcs() -> None:
    """The lower-left corner of a shape: its vertices', and the quarter points its arcs pass through."""
    zero = Fraction(0)

    def line(x: int, y: int) -> OutlineVertex:
        return OutlineVertex(0, Fraction(x), Fraction(y), zero, zero, 0.0, 0.0, zero)

    square = [line(0, 0), line(100, 0), line(100, 100), line(0, 100)]
    assert arrays.shape_corner(square) == (0, 0)
    # the left side bulges out: an arc about (0, 50) of radius 50 from 90 to 270 degrees
    bulge = OutlineVertex(1, zero, Fraction(100), zero, Fraction(50), 90.0, 270.0, Fraction(50))
    assert arrays.shape_corner([line(0, 0), line(100, 0), line(100, 100), bulge]) == (-50, 0)
    assert arrays.shape_corner(square[:2]) is None


def test_plain_array_copies_lie_as_the_flattened_panel(kit: tuple[Path, Design]) -> None:
    """Every copy's footprints lie where the flattened panel of the same layout puts them, within 10 nm;
    designators, nets and ids are kept apart per copy."""
    panel, flat = kit
    source = read_source(panel)
    placed, items = arrays.array_copies(panel, panel.read_bytes(), source.design)
    assert [(item.reason, item.placed) for item in items] == [(EMBEDDED_BOARD_PLACED, True)]
    assert items[0].item == "panel.PcbDoc#1:board.PcbDoc 2x2"
    copied = [c.ref for c in placed.circuit.components if COPY.search(c.ref)]
    assert {int(COPY.search(ref).group(1)) for ref in copied} == {1, 2, 3, 4}  # type: ignore[union-attr]
    refs = {c.ref for c in flat.circuit.components if c.ref}
    assert len(copied) == 4 * len({c.ref for c in flat.circuit.components if c.ref})
    assert _close(_places(placed, copied), _places(flat, refs))
    names = [n.name for n in placed.circuit.nets if n.name]
    assert len(names) == len(set(names)) and any(name.startswith("B4/") for name in names)
    board = placed.board
    assert board is not None
    ids = [fp.id for fp in board.footprints] + [t.id for t in board.tracks]
    assert len(ids) == len(set(ids))
    assert not [g for g in board.graphics if g.layer == "Edge.Cuts" and g.id not in _edge_ids(source.design)]


def _edge_ids(design: Design) -> set[str]:
    board = design.board
    assert board is not None
    return {g.id for g in board.graphics if g.layer == "Edge.Cuts"}


def test_conversion_writes_the_copies(kit: tuple[Path, Design]) -> None:
    """The conversion reports the array as changed, not lost, and writes every copy's footprints."""
    panel, flat = kit
    conversion = convert_project(read_source(panel), to="kicad", allow_lossy=True)
    row = next(row for row in conversion.report.rows if row.kind == "embedded-board")
    assert (row.source, row.changed, row.lost, row.loss) == (1, 1, 0, "report")
    text = conversion.files[conversion.read_back].decode("utf-8")
    refs = sorted({c.ref for c in flat.circuit.components if c.ref})
    for k in range(1, 5):
        for ref in refs:
            assert f'"{ref}_B{k}"' in text, (ref, k)


def _turned(
    found: tuple[arrays_reader.BoardArray, ...], degrees: float
) -> tuple[arrays_reader.BoardArray, ...]:
    return tuple(dataclasses.replace(a, rotation=degrees) for a in found)


@pytest.mark.parametrize("quarters", [1, 2, 3])
def test_turned_array_turns_each_copy(
    kit: tuple[Path, Design], monkeypatch: pytest.MonkeyPatch, quarters: int
) -> None:
    """ROTATION 90: copy (c, r) takes the board point p to (X, Y) + R((c * COLSPACING, r * ROWSPACING) + p -
    O), R a counter-clockwise quarter turn (S-1592); each footprint turns by 90 degrees. ROTATION 180 and 270
    turn so twice and three times, an inferred rule that the report names (change c0428)."""
    panel, _ = kit
    data = panel.read_bytes()
    (array,) = arrays_reader.board_arrays(data)
    source = read_source(panel)
    board_design = panel_build.read_source(panel.parent / "board.PcbDoc")[0]
    plain, _ = arrays.array_copies(panel, data, source.design)
    monkeypatch.setattr(arrays_reader, "board_arrays", lambda raw: _turned((array,), 90.0 * quarters))
    turned, items = arrays.array_copies(panel, data, source.design)
    assert items[0].placed
    assert (EMBEDDED_BOARD_TURNED in items[0].reason.split("; ")) == (quarters > 1)
    assert board_design.board is not None and turned.board is not None
    origin = Point(1000 * 25_400, -1000 * 25_400)  # pcbdoc.BOARD_OFFSET_MIL: the board's origin
    anchor = Point(arrays._nm(array.x), -arrays._nm(array.y))
    first = board_design.board.footprints[0]
    ref = next(c.ref for c in board_design.circuit.components if c.id == first.component_id)
    by_ref = {c.id: c.ref for c in turned.circuit.components}
    for k, (r, c) in enumerate(((r, c) for r in range(array.rows) for c in range(array.cols)), 1):
        dx = first.position.x + arrays._nm(c * array.col_pitch) - origin.x
        dy = first.position.y - arrays._nm(r * array.row_pitch) - origin.y
        for _ in range(quarters):
            dx, dy = dy, -dx
        expected = Point(anchor.x + dx, anchor.y + dy)
        (fp,) = [fp for fp in turned.board.footprints if by_ref.get(fp.component_id) == f"{ref}_B{k}"]
        assert abs(fp.position.x - expected.x) <= 2 and abs(fp.position.y - expected.y) <= 2, (k, fp.position)
        assert fp.rotation == (first.rotation + quarters * QUARTER) % (360 * 1_000_000)
    assert plain.board is not None and len(plain.board.footprints) == len(turned.board.footprints)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"mirrored": True}, EMBEDDED_BOARD_MIRRORED),
        ({"rotation": 45.0}, EMBEDDED_BOARD_ANGLE),
    ],
)
def test_unmeasured_variants_stay_refused(
    kit: tuple[Path, Design], monkeypatch: pytest.MonkeyPatch, change: dict[str, object], reason: str
) -> None:
    panel, _ = kit
    data = panel.read_bytes()
    (array,) = arrays_reader.board_arrays(data)
    monkeypatch.setattr(arrays_reader, "board_arrays", lambda raw: (dataclasses.replace(array, **change),))
    source = read_source(panel)
    placed, items = arrays.array_copies(panel, data, source.design)
    assert [(item.reason, item.placed) for item in items] == [(reason, False)]
    assert placed is source.design
    conversion = convert_project(source, to="kicad", allow_lossy=True)
    row = next(row for row in conversion.report.rows if row.kind == "embedded-board")
    assert (row.lost, row.loss) == (1, "refuse")


@pytest.mark.parametrize(
    ("linked", "reason", "shift"), [(False, EMBEDDED_BOARD_CORNER, -25_400), (True, EMBEDDED_BOARD_LINKED, 0)]
)
def test_origin_away_from_the_corner(
    kit: tuple[Path, Design], monkeypatch: pytest.MonkeyPatch, linked: bool, reason: str, shift: int
) -> None:
    """A referenced board whose origin is more than 1 µm from its shape's lower-left corner (here the
    corner is moved 1 mil right): an array that links its location to the origin places the copies by the
    origin, as before; one that does not, by the corner, so the copies move 1 mil left (change c0428, both
    inferred and named in the report)."""
    panel, _ = kit
    data = panel.read_bytes()
    (array,) = arrays_reader.board_arrays(data)
    source = read_source(panel)
    plain, _ = arrays.array_copies(panel, data, source.design)
    real = arrays.shape_corner

    def moved(vertices: object) -> tuple[Fraction, Fraction] | None:
        corner = real(vertices)  # type: ignore[arg-type]
        return None if corner is None else (corner[0] + 10_000, corner[1])

    monkeypatch.setattr(arrays, "shape_corner", moved)
    monkeypatch.setattr(
        arrays_reader, "board_arrays", lambda raw: (dataclasses.replace(array, linked=linked),)
    )
    placed, items = arrays.array_copies(panel, data, source.design)
    assert items[0].placed and reason in items[0].reason.split("; ")
    assert plain.board is not None and placed.board is not None
    before = {fp.id: fp.position for fp in plain.board.footprints}
    for fp in placed.board.footprints:
        assert fp.position == Point(before[fp.id].x + shift, before[fp.id].y), fp.id


def test_referenced_document_is_looked_for(tmp_path: Path) -> None:
    """Change c0428: a referenced document that is not at its relative path is found without letter case,
    relative to the project's folder, or by its file name; one found nowhere is missing."""
    from fenolite.convert.arrays import find_document

    shutil.copyfile(
        Path(__file__).resolve().parents[2] / "data/altium/blink/blink.PcbDoc", tmp_path / "x.pcbdoc"
    )
    panel = tmp_path / "PCB" / "panel.PcbDoc"
    panel.parent.mkdir()
    sub = tmp_path / "boards"
    sub.mkdir()
    shutil.copyfile(tmp_path / "x.pcbdoc", sub / "Board.PcbDoc")
    assert find_document(panel, "..\\X.PcbDoc")[1:] == ("read", "relative")
    assert find_document(panel, "boards\\board.pcbdoc", tmp_path)[1:] == ("read", "project")
    assert find_document(panel, "elsewhere\\x.PcbDoc", tmp_path)[1:] == ("read", "name")
    assert find_document(panel, "C:\\Work\\x.PcbDoc", tmp_path)[1:] == ("read", "name")
    assert find_document(panel, "gone.PcbDoc", tmp_path)[1] == "missing"
    assert find_document(panel, "C:\\Work\\gone.PcbDoc", tmp_path)[1] == "absolute"


def test_copies_carry_the_cutouts(kit: tuple[Path, Design], monkeypatch: pytest.MonkeyPatch) -> None:
    """Change c0428: a closed ``Edge.Cuts`` polygon of the referenced board (a cut-out) is copied, moved, into
    each copy, and ``Copies.cutouts`` names the copies."""
    import fenolite.backends.altium.adapter as adapter
    from fenolite.model.board import Graphic

    panel, _ = kit
    real = adapter.import_board

    def with_cutout(*args: object, **kwargs: object) -> Design:
        design = real(*args, **kwargs)  # type: ignore[arg-type]
        assert design.board is not None
        x, y = 1010 * 25_400, -1010 * 25_400
        ring = (Point(x, y), Point(x + MM, y), Point(x + MM, y - MM), Point(x, y - MM))
        hole = Graphic(
            id="gra_c0428cut-0000-5000-8000-000000000000",
            kind="polygon",
            layer="Edge.Cuts",
            points=ring,
            width=0,
        )
        board = dataclasses.replace(design.board, graphics=(*design.board.graphics, hole))
        return dataclasses.replace(design, board=board)

    monkeypatch.setattr(adapter, "import_board", with_cutout)
    source = read_source(panel)
    found = arrays.copies(panel, panel.read_bytes(), source.design)
    assert found.items[0].placed and len(found.cutouts) == 4
    assert found.design.board is not None
    cut = [g for g in found.design.board.graphics if g.id in found.cutouts]
    assert len({g.points[0] for g in cut}) == 4


def test_arc_outlines_take_the_records() -> None:
    """``arc_outlines``: a zone without an outline takes its record's flattened ring; one whose record
    encloses no area (two vertices at one point, which the import keeps as a 1-point outline) or is missing
    is dropped with that reason (change c0428, shared by the copies and the conversion)."""
    from types import SimpleNamespace

    from _convert import two_layer

    from fenolite.backends.altium.read.pcbstack import OutlineVertex
    from fenolite.convert.altium_to_kicad import ZONE_NO_AREA, ZONE_NO_OUTLINE, arc_outlines
    from fenolite.core.provenance import Provenance
    from fenolite.model.board import Zone

    r = Fraction(10_000_000)
    zero = Fraction(0)
    vertices = (
        OutlineVertex(1, r, zero, zero, zero, 0.0, 180.0, r),
        OutlineVertex(0, -r, zero, zero, zero, 0.0, 0.0, zero),
    )
    point = OutlineVertex(0, r, r, zero, zero, 0.0, 0.0, zero)
    document = SimpleNamespace(
        polygons=[SimpleNamespace(vertices=vertices), SimpleNamespace(vertices=(point, point))]
    )
    design = two_layer()
    assert design.board is not None
    zones = tuple(
        Zone(
            id=f"zon_c0428{n:03d}-0000-5000-8000-000000000000",
            outline=(Point(10 * MM, 10 * MM),) if n == 1 else (),
            name="pour",
            layers=("F.Cu",),
            provenance=Provenance(
                backend="altium", file="b.PcbDoc", file_sha256="0" * 64, locator=f"Polygons6/Data#{n}"
            ),
        )
        for n in (0, 1, 5)
    )
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, zones=zones))
    outlined, done, dropped = arc_outlines(design, document)
    assert outlined.board is not None and len(outlined.board.zones) == 1
    assert len(outlined.board.zones[0].outline) > 8
    assert done == (zones[0].id,)
    assert dropped == ((zones[1].id, ZONE_NO_AREA), (zones[2].id, ZONE_NO_OUTLINE))


OUTPUTS = os.environ.get("FENOLITE_ALTIUM_PANEL_OUTPUTS")
"""The folder of ``tests/unit/backends/altium/test_panel_placement.py`` (outside the repository):
``board.PcbDoc``, the saved ``panel-<variant>.PcbDoc`` and Altium's drill file of each."""
MEASURED = {"a": True, "rot90": True, "link": True, "mirror": False}
"""Whether each variant of Part Q is placed (mirror is not measured: S-1592)."""


def _drill_hits() -> object | None:
    """``drill_hits`` of the measuring test of tasks 1.2 and 1.3, when it is in this tree."""
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "backends" / "altium" / "test_panel_placement.py"
    spec = importlib.util.spec_from_file_location("_c0386_measured", path) if path.is_file() else None
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.drill_hits


@pytest.mark.skipif(not OUTPUTS, reason="no folder of panels and drill files that Altium saved is given")
@pytest.mark.parametrize("variant", list(MEASURED))
def test_saved_panels(variant: str, capsys: pytest.CaptureFixture[str]) -> None:
    """Each saved panel converts with its array placed (refused when mirrored); every drilled hole of the
    copies lies within 1 µm of a hit of the drill file that Altium wrote for the panel."""
    from collections import Counter

    from fenolite.backends.altium.frame import board_pads

    folder = Path(str(OUTPUTS)).expanduser()
    panel = folder / f"panel-{variant}.PcbDoc"
    if not panel.is_file():
        pytest.skip(f"{panel.name} is not in the folder")
    source = read_source(panel)
    placed, items = arrays.array_copies(panel, panel.read_bytes(), source.design)
    assert [item.placed for item in items] == [MEASURED[variant]], [item.reason for item in items]
    drill = next(
        (p for p in (folder / f"panel-{variant}-Plated.TXT", folder / f"panel-{variant}.TXT") if p.is_file()),
        None,
    )
    reader = _drill_hits()
    if not MEASURED[variant] or drill is None or reader is None:
        return
    assert placed.board is not None
    points: Counter[tuple[int, int]] = Counter(
        (pad.hole[0].x, pad.hole[0].y) for pad in board_pads(placed) if len(pad.hole) == 1
    )
    points.update((via.position.x, via.position.y) for via in placed.board.vias)
    got = sorted((Fraction(x, MM), Fraction(-y, MM)) for (x, y), n in points.items() for _ in range(n))
    hits = reader(drill.read_text(encoding="ascii"))  # type: ignore[operator]
    want = sorted((x, y) for (_, x, y), n in hits.items() for _ in range(n))
    assert len(got) == len(want)
    worst = max(max(abs(a[0] - b[0]), abs(a[1] - b[1])) for a, b in zip(got, want, strict=True))
    with capsys.disabled():
        print(f"panel-{variant}: {len(got)} holes, worst {float(worst):.6f} mm from Altium's drill hits")
    assert worst <= Fraction(1, 1000)


def _model_nodes(conversion: object) -> dict[str, list[tuple[str, ...]]]:
    """Each footprint's models as (offset, rotate) atom tuples, by designator."""
    from fenolite.backends.kicad.sexpr import parse

    board = parse(conversion.files[conversion.read_back].decode())  # type: ignore[attr-defined]
    out: dict[str, list[tuple[str, ...]]] = {}
    for footprint in board.nodes("footprint"):
        refs = [p.atoms()[1].value for p in footprint.nodes("property") if p.atoms()[0].value == "Reference"]
        out[refs[0]] = [
            tuple(
                a.value
                for head in ("offset", "rotate")
                for xyz in m.nodes(head)
                for n in xyz.nodes("xyz")
                for a in n.atoms()
            )
            for m in footprint.nodes("model")
        ]
    return out


def test_copies_keep_their_models(kit: tuple[Path, Design], tmp_path: Path) -> None:
    """Change c0428: the copies of a referenced board that embeds models and has bodies (the authored
    document of change c0423) carry each model with the pose of the board converted alone, and lose none."""
    import _altium_models as am

    from fenolite.convert import convert_project

    panel, _ = kit
    shutil.copyfile(panel, tmp_path / "panel.PcbDoc")
    (tmp_path / "board.PcbDoc").write_bytes(am.write_document())
    alone = convert_project(tmp_path / "board.PcbDoc", to="kicad", allow_lossy=True)
    copied = convert_project(tmp_path / "panel.PcbDoc", to="kicad", allow_lossy=True)
    for kind in ("model", "body"):
        row = copied.report.row(kind)
        assert row is not None and row.lost == 0, (kind, row)
    expected = _model_nodes(alone)
    found = _model_nodes(copied)
    assert expected and all(expected.values())
    for ref, models in expected.items():
        for k in range(1, 5):
            assert found[f"{ref}_B{k}"] == models, (ref, k)


def _square(name: str, x: int, y: int, side: int) -> object:
    from fenolite.backends.base import EdgeRing

    return EdgeRing(name, (Point(x, y), Point(x + side, y), Point(x + side, y + side), Point(x, y + side)))


@pytest.mark.parametrize("copies", [0, 1])
def test_rings_merged_with_a_copys_cutout_are_explained(copies: int) -> None:
    """Change c0428: a source cut-out that the written board merged with a cut-out a copy carries is
    explained by the ``cutout`` row, and so is the merged ring; without copied cut-outs neither is."""
    from fenolite.convert.report import EMBEDDED_BOARD_CUTOUT_COPIED, ConversionReport, Reason, ReportRow
    from fenolite.convert.rings import compare_rings

    board = _square("board", 0, 0, 100 * MM)
    source = (board, _square("edge ring 1", 10 * MM, 10 * MM, 5 * MM))
    written = (board, _square("edge ring 1", 10 * MM, 10 * MM, 8 * MM))
    reasons = (Reason(EMBEDDED_BOARD_CUTOUT_COPIED, "changed", ("gfx_copied",)),) if copies else ()
    row = ReportRow(kind="cutout", source=1, written=0, changed=copies, lost=0, reasons=reasons)
    found = compare_rings(source, written, ConversionReport(rows=(row,)))  # type: ignore[arg-type]
    assert [(d.side, d.explained_by) for d in found] == [
        ("source", "cutout" if copies else None),
        ("written", "cutout" if copies else None),
    ]
