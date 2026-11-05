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
    EMBEDDED_BOARD_MIRRORED,
    EMBEDDED_BOARD_ORIGIN,
    EMBEDDED_BOARD_PLACED,
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


def _turned(found: tuple[arrays_reader.BoardArray, ...]) -> tuple[arrays_reader.BoardArray, ...]:
    return tuple(dataclasses.replace(a, rotation=90.0) for a in found)


def test_turned_array_turns_each_copy(kit: tuple[Path, Design], monkeypatch: pytest.MonkeyPatch) -> None:
    """ROTATION 90: copy (c, r) takes the board point p to (X, Y) + R((c * COLSPACING, r * ROWSPACING) + p -
    O), R a counter-clockwise quarter turn (S-1592); each footprint turns by 90 degrees."""
    panel, _ = kit
    data = panel.read_bytes()
    (array,) = arrays_reader.board_arrays(data)
    source = read_source(panel)
    board_design = panel_build.read_source(panel.parent / "board.PcbDoc")[0]
    plain, _ = arrays.array_copies(panel, data, source.design)
    monkeypatch.setattr(arrays_reader, "board_arrays", lambda raw: _turned((array,)))
    turned, items = arrays.array_copies(panel, data, source.design)
    assert items[0].placed
    assert board_design.board is not None and turned.board is not None
    origin = Point(1000 * 25_400, -1000 * 25_400)  # pcbdoc.BOARD_OFFSET_MIL: the board's origin
    anchor = Point(arrays._nm(array.x), -arrays._nm(array.y))
    first = board_design.board.footprints[0]
    ref = next(c.ref for c in board_design.circuit.components if c.id == first.component_id)
    by_ref = {c.id: c.ref for c in turned.circuit.components}
    for k, (r, c) in enumerate(((r, c) for r in range(array.rows) for c in range(array.cols)), 1):
        dx = first.position.x + arrays._nm(c * array.col_pitch) - origin.x
        dy = first.position.y - arrays._nm(r * array.row_pitch) - origin.y
        expected = Point(anchor.x + dy, anchor.y - dx)
        (fp,) = [fp for fp in turned.board.footprints if by_ref.get(fp.component_id) == f"{ref}_B{k}"]
        assert abs(fp.position.x - expected.x) <= 2 and abs(fp.position.y - expected.y) <= 2, (k, fp.position)
        assert fp.rotation == (first.rotation + QUARTER) % (360 * 1_000_000)
    assert plain.board is not None and len(plain.board.footprints) == len(turned.board.footprints)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"mirrored": True}, EMBEDDED_BOARD_MIRRORED),
        ({"rotation": 45.0}, EMBEDDED_BOARD_ANGLE),
        ({"rotation": 180.0}, EMBEDDED_BOARD_ANGLE),
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


def test_origin_away_from_the_corner_stays_refused(
    kit: tuple[Path, Design], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A referenced board whose origin is more than 1 µm from its shape's lower-left corner (here the
    corner is moved 1 mil away) is not placed: S-1592 measured boards whose origin is that corner."""
    panel, _ = kit
    real = arrays.shape_corner

    def moved(vertices: object) -> tuple[Fraction, Fraction] | None:
        corner = real(vertices)  # type: ignore[arg-type]
        return None if corner is None else (corner[0] + 10_000, corner[1])

    monkeypatch.setattr(arrays, "shape_corner", moved)
    source = read_source(panel)
    _, items = arrays.array_copies(panel, panel.read_bytes(), source.design)
    assert [(item.reason, item.placed) for item in items] == [(EMBEDDED_BOARD_ORIGIN, False)]


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
