# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad loading and DRC of converted public Altium boards (c0161 task 4.1)."""

from __future__ import annotations

import _a2kcases
import pytest
from _corpus import manifest_items, require
from _probes import runner

pytestmark = pytest.mark.needs_kicad


def test_sample_load() -> None:
    assert _a2kcases.load(_a2kcases.SAMPLE, runner())


@pytest.mark.needs_corpus
@pytest.mark.slow
@pytest.mark.parametrize("item", [i for i in manifest_items("rta") if "-pcbdoc-" in i.id], ids=lambda i: i.id)
def test_public_load(item) -> None:
    assert _a2kcases.load(require(item), runner())


def test_copper_shape_of_a_net_is_no_short_in_kicad_drc(tmp_path) -> None:
    """change c0376 task 2.2: an Altium copper region on the net of the pad it lies on is written on that
    net, and KiCad's DRC finds no short and no clearance violation that the board without it lacks."""
    import dataclasses
    from collections import Counter

    from fenolite.backends.altium.frame import board_pads
    from fenolite.convert import convert_project
    from fenolite.convert.sources import read_source
    from fenolite.core.coords import Point
    from fenolite.model.base import ExtBag
    from fenolite.model.board import Graphic

    source = read_source(_a2kcases.SAMPLE)
    board = source.design.board
    assert board is not None
    pad = next(p for p in board_pads(source.design) if p.net_id is not None and "F.Cu" in p.layers)
    names = {net.id: net.name for net in source.design.circuit.nets}
    half = 100_000  # a square of 0.2 mm on the pad's centre, inside the pad
    c = pad.position

    def drc(net_id, added=True):  # type: ignore[no-untyped-def]
        region = Graphic(
            id="gfx-c0376",
            ext={"altium": ExtBag(payload=(("net", names[pad.net_id]),))},
            kind="polygon",
            layer="F.Cu",
            points=(
                Point(c.x - half, c.y - half),
                Point(c.x + half, c.y - half),
                Point(c.x + half, c.y + half),
            ),
            filled=True,
            net_id=net_id,
        )
        changed = dataclasses.replace(board, graphics=(*board.graphics, region) if added else board.graphics)
        design = dataclasses.replace(source.design, board=changed)
        folder = tmp_path / ("with" if added else "without")
        folder.mkdir()
        cli = runner()
        conversion = convert_project(
            dataclasses.replace(source, design=design),
            to="kicad",
            kicad_version=cli.major(),
            allow_lossy=True,
        )
        for name, data in conversion.files.items():
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            (folder / name).write_bytes(data)
        files = {name: folder / name for name in conversion.files if name != conversion.read_back}
        run = cli.drc(folder / conversion.read_back, files=files)
        assert run.report is not None, run.run.stderr
        return Counter(v.type for v in run.report.violations)

    with_region, without = drc(pad.net_id), drc(pad.net_id, added=False)
    for kind in ("shorting_items", "clearance"):
        assert with_region[kind] == without[kind], kind


def test_outline_arc_off_its_circle_is_a_closed_edge_in_kicad(tmp_path) -> None:
    """change c0378 task 1.2: the blink's board outline replaced by one whose arc ends on a vertex 5.08 µm
    off the arc's circle. The written board loads, KiCad's DRC finds no ``invalid_outline``, and the edge
    ring read back equals the source's."""
    import dataclasses

    from _outline_arc import rounded

    from fenolite.backends import registry
    from fenolite.backends.altium import frame
    from fenolite.convert import convert_project
    from fenolite.convert.rings import compare_rings
    from fenolite.convert.sources import read_source

    source = read_source(_a2kcases.SAMPLE)
    board = source.design.board
    edges = rounded("800.2mil").board
    assert board is not None and edges is not None
    graphics = (
        *(g for g in board.graphics if g.layer != "Edge.Cuts"),
        *(dataclasses.replace(g, id=f"c0378-{g.id}") for g in edges.graphics if g.layer == "Edge.Cuts"),
    )
    design = dataclasses.replace(source.design, board=dataclasses.replace(board, graphics=graphics))
    cli = runner()
    conversion = convert_project(
        dataclasses.replace(source, design=design), to="kicad", kicad_version=cli.major(), allow_lossy=True
    )
    for name, data in conversion.files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(data)
    written = tmp_path / conversion.read_back
    files = {name: tmp_path / name for name in conversion.files if name != conversion.read_back}
    run = cli.drc(written, files=files)
    assert run.report is not None, run.run.stderr
    assert "invalid_outline" not in {v.type for v in run.report.violations}
    backend = registry.for_path(written)
    rings = backend.board_edges(backend.read(written).design)  # type: ignore[attr-defined]
    source_rings = frame.board_edges(design)
    assert source_rings is not None
    assert compare_rings(source_rings, rings, conversion.report) == ()
