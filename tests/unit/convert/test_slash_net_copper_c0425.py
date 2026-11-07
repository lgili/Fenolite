# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper graphics on a net whose name holds a slash keep their net through KiCad (change c0425).

A KiCad 10 board names the net of a graphic in its ``(net "…")`` slot in the spelling the board stores, with
``{slash}`` for a slash; the reader names the net with the slash. The copies of an Altium embedded board
array name their nets ``B<k>/<net>``, so every copy's netted free region read back without a net and the
conversion was refused with level 5 ``copper-no-net`` differences. The boards are the committed two-layer
board, edited.
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path

import pytest
from _convert import two_layer
from _panels import run as cli

from fenolite.api import run
from fenolite.api.equivalence import equivalent
from fenolite.backends.altium import lower
from fenolite.backends.kicad import fpitems, pcb
from fenolite.core.coords import Point
from fenolite.model.board import Graphic
from fenolite.model.design import Design

MM = 1_000_000
RING = (Point(5 * MM, 5 * MM), Point(8 * MM, 5 * MM), Point(8 * MM, 8 * MM), Point(6 * MM, 8 * MM),
        Point(5 * MM, 7 * MM))  # fmt: skip
STAMP = "2026-11-06T00:00:00Z"


def _with_region(net: str = "A1/GND") -> Design:
    """The two-layer board with its net ``GND`` renamed ``net`` and a filled ``F.Cu`` polygon on it."""
    design = two_layer()
    gnd = next(n for n in design.circuit.nets if n.name == "GND")
    nets = tuple(dataclasses.replace(n, name=net) if n.id == gnd.id else n for n in design.circuit.nets)
    design = dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, nets=nets))
    board = design.board
    assert board is not None
    region = Graphic(id="gra-region", kind="polygon", layer="F.Cu", points=RING, width=0, filled=True,
                     net_id=gnd.id)  # fmt: skip
    return dataclasses.replace(design, board=dataclasses.replace(board, graphics=(*board.graphics, region)))


@pytest.mark.parametrize("target", [10, 9])
def test_a_region_on_a_slash_net_keeps_its_net(tmp_path: Path, target: int) -> None:
    """The written slot names the net ``A1{slash}GND``; read back, the region holds the net ``A1/GND``, and
    the board is equivalent to the design at every level, with no ``copper-no-net``."""
    design = _with_region()
    text = pcb.write_board(design, target=target).text
    assert "A1{slash}GND" in text
    path = tmp_path / "slash.kicad_pcb"
    path.write_text(text, encoding="utf-8")
    read = fpitems.with_graphic_nets(pcb.read_board(path))
    assert read.board is not None
    names = {net.id: net.name for net in read.circuit.nets}
    (region,) = [g for g in read.board.graphics if g.layer == "F.Cu" and g.filled]
    assert names.get(region.net_id or "") == "A1/GND"
    found = equivalent(design, path)
    assert found.report is not None and found.report.equivalent, found.report


def test_import_names_the_slash_net(tmp_path: Path) -> None:
    """``import --to python`` of the KiCad 10 board declares ``Net("A1/GND")``, never the stored spelling,
    and is equivalent; before change c0425 it declared a second net and the self-check refused it."""
    source = tmp_path / "src" / "slash.kicad_pcb"
    source.parent.mkdir()
    source.write_text(pcb.write_board(_with_region(), target=10).text, encoding="utf-8")
    reply = run("import", str(source), "--to", "python", "--out", "out", "--confirm", cwd=tmp_path,
                timestamp=STAMP)  # fmt: skip
    assert reply.exit_code == 0, reply.error
    assert reply.result["unexpressed"] == []
    assert reply.result["equivalence"]["equivalent"] is True
    script = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert 'Net("A1/GND")' in script and "{slash}" not in script


def test_the_copies_of_an_array_keep_their_region_nets(tmp_path: Path) -> None:
    """Scenario "The copies of a netted region keep their nets": a board with a free region on ``GND``,
    placed 3 × 2 times by an embedded board array, converts to KiCad with no unexplained difference; before
    change c0425 each of the 6 copies gave one level 5 ``copper-no-net``."""
    design = _with_region("GND")
    written = lower.write_design(design, allow_lossy=True)
    folder = tmp_path / "board"
    folder.mkdir()
    for name, data in written.files.items():
        (folder / name).write_bytes(data)
    (child,) = folder.glob("*.PcbDoc")
    script = tmp_path / "S" / "panel.py"
    script.parent.mkdir()
    board = Path(os.path.relpath(child, script.parent)).as_posix()
    script.write_text(
        "from fenolite.dsl import Panel, mm\n\n"
        f'panel = Panel("panel", board="{board}")\n'
        "panel.grid(3, 2, gap=mm(2))\n"
        'panel.separate("tabs", between="columns")\n',
        encoding="utf-8",
    )
    code, envelope, err = cli("panel", str(script), "--out", str(tmp_path / "P"), "--target", "altium",
                              "--confirm", "--no-backup")  # fmt: skip
    assert code == 0, (envelope.get("issues"), err)
    panel = tmp_path / "P" / "panel.PcbDoc"
    out = str(tmp_path / "K")
    reply = run("convert", str(panel), "--to", "kicad", "--out", out, "--dry-run", "--allow-lossy")
    assert reply.exit_code == 0, reply.error
    assert reply.envelope is not None
    codes = [issue["code"] for issue in reply.envelope["issues"]]
    assert "convert.unexplained" not in codes
    assert reply.result["equivalence"]["equivalent"] is True
