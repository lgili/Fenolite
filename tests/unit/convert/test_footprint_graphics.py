# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The footprints' own graphics of an Altium source (capability design-conversion, "Footprint graphics of
an imported footprint"; change c0409, B8): ``convert --to kicad`` and ``import --to python`` write each
footprint's lines, arcs, circles and regions on the layer the conversion maps them to, and a footprint text
that no target writes is reported and warned, never dropped in silence.

The source is the committed Fenolite blink sample (``tests/data/altium/blink``), with one region and one
text authored here and added to a footprint in memory."""

from __future__ import annotations

import dataclasses
from collections import Counter
from pathlib import Path

from _importcode import imported

from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.convert import convert_project
from fenolite.convert.sources import read_source
from fenolite.core.coords import Point, Size
from fenolite.model.board import Graphic, Text

ROOT = Path(__file__).resolve().parents[3]
BLINK = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PrjPcb"
HEADS = ("fp_line", "fp_arc", "fp_circle", "fp_rect", "fp_poly")
REGION_ID = "gfx_0c409000-0000-4000-8000-000000000001"
TEXT_ID = "txt_0c409000-0000-4000-8000-000000000002"


def _heads(footprint: Node) -> Counter[str]:
    return Counter(child.name for child in footprint.nodes() if child.name in HEADS)


def _layers(footprint: Node, head: str) -> set[str]:
    found: set[str] = set()
    for child in footprint.nodes(head):
        layer = child.find("layer")
        assert layer is not None
        found.add(layer.atoms()[0].value)
    return found


def _user_layer(pcb: Node, source_name: str) -> str:
    """The board layer whose user name is ``source_name`` (an Altium mechanical layer)."""
    table = pcb.find("layers")
    assert table is not None
    for row in table.nodes():
        values = [atom.value for atom in row.atoms()]
        if source_name in values:
            return values[0]
    raise AssertionError(f"no layer named {source_name}")


def _source():  # noqa: ANN202  (a SourceProject)
    """The blink sample with an authored filled region on Mech.13 and an authored text on the top overlay,
    both in the second footprint."""
    source = read_source(BLINK)
    board = source.design.board
    assert board is not None
    target = board.footprints[1]
    region = Graphic(
        id=REGION_ID,
        kind="polygon",
        layer="Mech.13",
        points=(Point(-300_000, -300_000), Point(300_000, -300_000), Point(0, 300_000)),
        width=0,
        filled=True,
    )
    note = Text(
        id=TEXT_ID, text="NOTE", position=Point(0, 800_000), layer="F.SilkS", size=Size(800_000, 800_000),
        thickness=120_000,
    )  # fmt: skip
    changed = dataclasses.replace(target, graphics=(*target.graphics, region), texts=(*target.texts, note))
    footprints = (*board.footprints[:1], changed, *board.footprints[2:])
    design = dataclasses.replace(source.design, board=dataclasses.replace(board, footprints=footprints))
    return dataclasses.replace(source, design=design)


def test_convert_writes_footprint_graphics() -> None:
    source = _source()
    board = source.design.board
    assert board is not None
    expected = Counter(g.kind for fp in board.footprints for g in fp.graphics)
    assert expected == {"line": 24, "arc": 2, "circle": 1, "polygon": 1}
    conversion = convert_project(source, to="kicad", allow_lossy=True)
    pcb = parse(conversion.files[conversion.read_back].decode())
    written: Counter[str] = Counter()
    footprints = pcb.nodes("footprint")
    for footprint in footprints:
        written += _heads(footprint)
    assert written == {"fp_line": 24, "fp_arc": 2, "fp_circle": 1, "fp_poly": 1}
    libraries = [
        parse(data.decode()) for name, data in sorted(conversion.files.items()) if name.endswith(".kicad_mod")
    ]
    assert sum((_heads(mod) for mod in libraries), Counter[str]()) == written
    # the region keeps its fill and lands on the user layer Mech.13 maps to; silkscreen stays silkscreen
    region = next(child for footprint in footprints for child in footprint.nodes("fp_poly"))
    fill = region.find("fill")
    assert fill is not None and fill.atoms()[0].value in {"yes", "solid"}
    assert set().union(*(_layers(fp, "fp_poly") for fp in footprints)) == {_user_layer(pcb, "Mech.13")}
    assert any("F.SilkS" in _layers(fp, "fp_line") for fp in footprints)
    assert any("B.SilkS" in _layers(fp, "fp_arc") for fp in footprints)
    rows = {row.kind: row for row in conversion.report.rows}
    graphic = rows["footprint-graphic"]
    assert (graphic.source, graphic.written, graphic.lost) == (28, 28, 0)
    text = rows["footprint-text"]
    assert (text.source, text.lost) == (1, 1)
    warned = [i for i in conversion.issues if i.code == "convert.lossy" and i.where == "footprint-text"]
    assert len(warned) == 1 and "not written" in warned[0].message


def test_import_to_python_keeps_footprint_graphics(tmp_path: Path) -> None:
    reply = imported(tmp_path, BLINK, "--confirm", "--allow-lossy")
    assert reply.exit_code == 0, reply.error
    mods = sorted((tmp_path / "out").rglob("*.kicad_mod"))
    assert mods, "the import vendors the footprints it derives"
    written = sum((_heads(parse(path.read_text(encoding="utf-8"))) for path in mods), Counter[str]())
    assert written == {"fp_line": 24, "fp_arc": 2, "fp_circle": 1}
