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


def test_embedded_array_copies_load_and_check_in_kicad(tmp_path) -> None:
    """change c0386 task 2.2: a panel that places 2 x 2 copies of an authored board as an Embedded Board
    Array converts with the copies placed; the converted panel loads, and KiCad's DRC finds per kind four
    times what it finds on the converted board alone: no copy shorts or crowds another."""
    from collections import Counter
    from pathlib import Path

    from _panels import build_board

    from fenolite.convert import convert_project
    from fenolite.convert.sources import read_source
    from fenolite.dsl import Panel, mm, to_model
    from fenolite.panel import build as panel_build
    from fenolite.panel.altium import embedded_files
    from fenolite.panel.layout import layout

    board = build_board(tmp_path / "src", "altium")
    panel = Panel("panel", board=board.name)
    panel.grid(2, 2, gap=mm(2))
    panel.separate("tabs", between="columns")
    model = to_model(panel)
    design, _ = panel_build.read_source(board)
    files, issues = embedded_files(model, layout(model, design), design, board.name)
    assert files and not [i for i in issues if i.severity == "error"], issues
    for name, data in files.items():
        (board.parent / name).write_bytes(data)
    cli = runner()

    def drc(source: Path) -> Counter[str]:
        folder = tmp_path / source.stem
        conversion = convert_project(
            read_source(source), to="kicad", kicad_version=cli.major(), allow_lossy=True
        )
        for name, data in conversion.files.items():
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            (folder / name).write_bytes(data)
        files = {name: folder / name for name in conversion.files if name != conversion.read_back}
        assert cli.load_board_svg(folder / conversion.read_back, files=files).ok
        run = cli.drc(folder / conversion.read_back, files=files)
        assert run.report is not None, run.run.stderr
        return Counter(v.type for v in run.report.violations)

    alone, copies = drc(board), drc(board.parent / "panel.PcbDoc")
    assert copies == Counter({kind: 4 * count for kind, count in alone.items()})
    assert not copies["shorting_items"] and not copies["clearance"]


def test_net_tie_footprint_copper_is_no_short_in_kicad_drc(tmp_path) -> None:
    """change c0420, N1: a converted footprint with net-tie groups is written with ``net_tie_pad_groups``
    after ``attr``; a copper line of the footprint joining its two pads of different nets then adds no
    violation to KiCad's DRC, and the same footprint without the groups adds clearance and solder mask
    bridge violations (10.0.6, 2026-11-05; 9.0.9 reports the copper bridge as ``shorting_items``)."""
    import dataclasses
    from collections import Counter

    from fenolite.backends.kicad.pcb import read_board
    from fenolite.convert import convert_project
    from fenolite.convert.sources import read_source
    from fenolite.model.board import Graphic

    source = read_source(_a2kcases.SAMPLE)
    board = source.design.board
    assert board is not None
    index, fp = next(
        (i, f)
        for i, f in enumerate(board.footprints)
        if len(f.pads) == 2 and len({p.net_id for p in f.pads} - {None}) == 2 and f.side == "top"
        and all("F.Cu" in p.layers for p in f.pads)
    )  # fmt: skip
    one, two = fp.pads
    bridge = Graphic(
        id="gfx-c0420-tie", kind="line", layer="F.Cu", points=(one.position, two.position), width=200_000
    )
    cli = runner()

    def drc(ties: tuple[tuple[str, ...], ...], bridged: bool = True) -> Counter[str]:
        graphics = (*fp.graphics, bridge) if bridged else fp.graphics
        tied = dataclasses.replace(fp, net_ties=ties, graphics=graphics)
        footprints = (*board.footprints[:index], tied, *board.footprints[index + 1 :])
        design = dataclasses.replace(source.design, board=dataclasses.replace(board, footprints=footprints))
        folder = tmp_path / f"{len(ties)}{int(bridged)}"
        folder.mkdir()
        changed = dataclasses.replace(source, design=design)
        conversion = convert_project(changed, to="kicad", kicad_version=cli.major(), allow_lossy=True)
        for name, data in conversion.files.items():
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            (folder / name).write_bytes(data)
        text = conversion.files[conversion.read_back].decode()
        if ties:
            assert text.count("(net_tie_pad_groups") == 1
            read = read_board(text)
            assert read.board is not None
            assert [f.net_ties for f in read.board.footprints if f.net_ties] == [ties]
        files = {name: folder / name for name in conversion.files if name != conversion.read_back}
        run = cli.drc(folder / conversion.read_back, files=files)
        assert run.report is not None, run.run.stderr
        return Counter(v.type for v in run.report.violations)

    group = ((one.number, two.number),)
    baseline, tied, untied = drc(group, bridged=False), drc(group), drc(())
    assert tied == baseline
    copper = ("clearance", "shorting_items")  # 10.0.6 reports the bridge as clearance, 9.0.9 as shorting
    assert sum(untied[k] for k in copper) > sum(baseline[k] for k in copper)
    assert untied["solder_mask_bridge"] > baseline["solder_mask_bridge"]
