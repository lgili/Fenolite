# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Graphics and texts of a footprint instance, and the corner ratio of a rounded pad (capability
design-model, "Graphics and texts of a footprint instance", "Corner ratio of a rounded-rectangle pad";
``H-G-FPGFX-ADD``, ``H-G-CORNER-PPM``; change c0126).

The three fields are additive. The digests below were measured with the code of the commit before the
change (``f17b03e9``): a design without the fields gives the texts it gave. The fixture
``tests/data/model/v0.2.0/blink_2layer.board.json`` is the ``board.json`` that release 0.2.0 itself wrote.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from _buildhelp import BLINK_DIR, blink, build

from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.geometry.transform import Transform
from fenolite.model import canonical
from fenolite.model.board import (
    MAX_CORNER_RATIO,
    PPM_PER_PERCENT,
    Board,
    FootprintInstance,
    Graphic,
    Pad,
    Text,
)
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "data" / "model" / "v0.2.0" / "blink_2layer.board.json"
FIXTURE_SHA256 = "92d4403617820108b8c7dbe5e077b8b7d797ca0abf46ea8086a357916f57eaad"
TWO_LAYER = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
BLINK = {
    "board.json": "03c5e887a4c54cd5186aa4676fb554280a8167a5c2f90a2c7a32242e403ce4c6",
    "circuit.json": "705da4a0b455069c68bf620b8079af5b8becda9800ae71c1fe3633a77f2696a3",
    "findings.json": "ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356",
    "manufacturing.json": "2a4f17be347dc9e374fe86cb3576b7faf3d4d15113620b0578b6dfd8019fc358",
    "rules.json": "3b6c856c3b9cf3c2d078597ebdf90a177882f9272e8fea1cc152620561b9341a",
}
"""SHA-256 of each text of ``canonical.dump_texts`` of the built blink (KiCad 10), on ``f17b03e9``.
``meta.json`` holds the package version and is left out. ``board.json`` was taken again when v0.4 was
rebased onto 0.3.0: change c0102 writes the board outline from another corner, so the outline lines have
other ids, locators and points and the written board file has another SHA-256; no footprint item moves."""
BOARD_READ = {
    "board.json": "eb2899ac436e0d69bcda96553b5a8af9efd5b490e30f7ac19db20cf9ce1a1184",
    "circuit.json": "fa9b249147a3b2dc2852a127a8a3a7b19f55c6f7931c77e2d19a85f40addb02c",
    "findings.json": "ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356",
    "manufacturing.json": "8f33115c2a048b218fc144d7835f3860270fca753e0527b7f04cd86bfeae7c7a",
    "rules.json": "912552be89c0c58b5159a95c4c7608db1fcc374fa1344274eb548a7afb09386b",
}
"""The same for the board read from ``tests/data/kicad/board/two_layer.kicad_pcb``."""
MM = 1_000_000


def _digests(design: Design) -> dict[str, str]:
    return {
        name: hashlib.sha256(text.encode("utf-8")).hexdigest()
        for name, text in sorted(canonical.dump_texts(design).items())
        if name != "meta.json"
    }


def _ident(prefix: str, key: str) -> str:
    return derived_id(prefix, "test", key)


def _pad(key: str, shape: str, ratio: int | None) -> Pad:
    return Pad(
        id=_ident("pad", key),
        number=key,
        shape=shape,  # type: ignore[arg-type]
        size=Size(MM, 2 * MM),
        position=Point(0, 0),
        layers=("F.Cu",),
        corner_ratio=ratio,
    )


def _design(footprint: FootprintInstance) -> Design:
    board = Board(id=_ident("brd", "board"), footprints=(footprint,))
    return dataclasses.replace(Design.new("items", seed=1), board=board)


def kicad_ppm(text: str) -> int:
    """A KiCad ``roundrect_rratio`` as ppm of the shorter side, rounded half to even to one ppm."""
    return int((Decimal(text) * 1_000_000).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def test_bytes_of_designs_without_footprint_items() -> None:
    """Scenario "A design without footprint items keeps its bytes": the built blink and a board read from
    a KiCad file give the texts that the commit before the change gave."""
    output = build(blink(), 10, project_dir=BLINK_DIR)
    assert output.layout is not None
    assert _digests(output.layout) == BLINK
    read = read_board(TWO_LAYER.read_text(encoding="utf-8"), file=TWO_LAYER.name)
    assert _digests(read) == BOARD_READ


def test_v020_document_loads_unchanged() -> None:
    """Scenario "A document of 0.2.0 loads unchanged"."""
    data = FIXTURE.read_bytes()
    assert hashlib.sha256(data).hexdigest() == FIXTURE_SHA256
    text = data.decode("utf-8")
    assert not {"graphics", "texts"} & {key for fp in json.loads(text)["footprints"] for key in fp}
    assert '"corner_ratio"' not in text
    board = canonical.loads(text, Board, file=FIXTURE.name)
    assert board.footprints
    for footprint in board.footprints:
        assert footprint.graphics == () and footprint.texts == ()
        assert all(pad.corner_ratio is None for pad in footprint.pads)
    assert canonical.dumps(board).encode("utf-8") == data


def test_bytes_grow_only_by_the_new_keys() -> None:
    """A footprint with items serialises the two keys in order, and loads to itself; without them the
    keys are absent."""
    line = Graphic(
        id=_ident("gfx", "a"), kind="line", layer="F.SilkS", points=(Point(0, 0), Point(MM, 0)), width=120_000
    )
    arc = dataclasses.replace(
        line, id=_ident("gfx", "b"), kind="arc", points=(Point(0, 0), Point(MM, MM), Point(0, MM))
    )
    text = Text(
        id=_ident("txt", "t"),
        text="X",
        layer="F.Fab",
        position=Point(0, 0),
        size=Size(MM, MM),
        thickness=150_000,
    )
    bare = FootprintInstance(id=_ident("fp", "f"), component_id="", lib_ref="L:N", position=Point(0, 0))
    full = dataclasses.replace(
        bare, graphics=(line, arc), texts=(text,), pads=(_pad("1", "roundrect", 250_000),)
    )
    data = json.loads(canonical.dumps(full))
    assert [g["kind"] for g in data["graphics"]] == ["line", "arc"]  # ordered: the order of the source
    assert len(data["texts"]) == 1 and data["pads"][0]["corner_ratio"] == 250_000
    assert canonical.loads(canonical.dumps(full), FootprintInstance) == full
    assert not {"graphics", "texts"} & set(json.loads(canonical.dumps(bare)))
    design = _design(full)
    assert {entity.id for entity in design.entities()} >= {line.id, arc.id, text.id}
    layers = design.by_layer
    assert line in layers["F.SilkS"] and arc in layers["F.SilkS"] and text in layers["F.Fab"]
    twice = _design(dataclasses.replace(full, graphics=(line, line)))
    assert [issue.code for issue in twice.validate() if issue.where == line.id] == ["model.duplicate-id"]


def test_line_of_a_bottom_footprint() -> None:
    """Scenario "A line of a bottom footprint": the pad frame, no further mirror."""
    line = Graphic(
        id=_ident("gfx", "l"), kind="line", layer="B.SilkS", points=(Point(0, 0), Point(MM, 0)), width=120_000
    )
    footprint = FootprintInstance(
        id=_ident("fp", "b"),
        component_id="",
        lib_ref="L:N",
        position=Point(10 * MM, 20 * MM),
        rotation=90_000_000,
        side="bottom",
        graphics=(line,),
    )
    placement = Transform.placement(footprint.position, footprint.rotation)
    ends = tuple(placement.apply(point) for point in footprint.graphics[0].points)
    assert ends == (Point(10 * MM, 20 * MM), Point(10 * MM, 19 * MM))
    pad = dataclasses.replace(_pad("1", "rect", None), position=Point(MM, 0))
    assert placement.apply(pad.position) == ends[1]  # where a pad at the same local point lies


def test_corner_percentages_are_exact() -> None:
    """Scenario "Percentages are exact" (``H-G-CORNER-PPM``)."""
    for percent in range(101):
        ppm = PPM_PER_PERCENT * percent
        assert (
            0 <= ppm <= MAX_CORNER_RATIO and ppm % PPM_PER_PERCENT == 0 and ppm // PPM_PER_PERCENT == percent
        )
    assert [kicad_ppm(text) for text in ("0.25", "0.1", "0.208333")] == [250_000, 100_000, 208_333]
    assert kicad_ppm("0.2083335") == 208_334 and kicad_ppm("0.2083325") == 208_332  # half to even
    assert kicad_ppm("0.5") == MAX_CORNER_RATIO


def test_corner_ratio_on_a_rectangle_is_reported() -> None:
    """Scenario "A ratio on a rectangle"."""
    wrong, outside, fine = (
        _pad("1", "rect", 250_000),
        _pad("2", "roundrect", 600_000),
        _pad("3", "roundrect", 0),
    )
    footprint = FootprintInstance(
        id=_ident("fp", "v"),
        component_id="",
        lib_ref="L:N",
        position=Point(0, 0),
        pads=(wrong, outside, fine),
    )
    found = [issue for issue in _design(footprint).validate() if issue.code == "model.corner-ratio"]
    assert [(issue.severity, issue.where) for issue in found] == [("error", wrong.id), ("error", outside.id)]
    negative = dataclasses.replace(outside, corner_ratio=-1)
    codes = [i.code for i in _design(dataclasses.replace(footprint, pads=(negative,))).validate()]
    assert codes.count("model.corner-ratio") == 1
