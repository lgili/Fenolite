# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A bottom footprint with pads off its X axis through ``--copper-from`` and back (change c0142; capability
altium-build, "Bottom-side footprints of a copper source"; ``H-G-BOTTOM-STORE``, ``H-A-PCB-CU-ROUNDTRIP``).

The blink with its controller (a QFP-32 of the authored mini library) on the bottom at 0 and 90 degrees is
built for KiCad, that board is handed to ``fenolite build --target altium --copper-from``, and
``kicad-cli pcb import --format altium`` turns the written document into a KiCad board again. Both boards
are read with ``backends.kicad.pcb.read_board``:

- every pad of the imported board is where the source board has it, relative to each board's outline
  corner, within 10 nm (``KicadBackend.board_pads``);
- the controller is on the bottom, at the source's rotation, and the pads KiCad stores for it are, once the
  mirror about local X is undone (``lens.altium_copper.library_pad_positions``), those of the source's
  definition: KiCad's own writer stores a bottom footprint as Fenolite's check reads it.

``pcb import`` exists from 10.0 only (S-0166). A pass checks only what KiCad's importer reads.
"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest
from _buildhelp import blink_variant
from _kicad import oracle_env
from _resources import kicad_cli, kicad_cli_major

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.lens.altium_copper import library_pad_positions
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad

TOLERANCE = 10
PLACE = "u1.place(mm(14), mm(15), locked=True)"


def build(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", io.StringIO())
        patch.setattr(sys, "stderr", io.StringIO())
        return cli_main.main(["build", *args, "--confirm", "--json"])


def corner(design: Design) -> Point:
    assert design.board is not None
    points = [p for g in design.board.graphics if g.layer == "Edge.Cuts" for p in g.points]
    assert points
    return Point(min(p.x for p in points), min(p.y for p in points))


def pads(design: Design) -> dict[tuple[str, str], tuple[int, int]]:
    origin = corner(design)
    return {
        (p.ref, p.number): (p.position.x - origin.x, p.position.y - origin.y)
        for p in KicadBackend().board_pads(design)
    }


def controller(design: Design) -> object:
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    (found,) = [f for f in design.board.footprints if refs[f.component_id] == "U1"]
    return found


@pytest.mark.parametrize("rot", [0, 90])
def test_bottom_footprint_to_altium_and_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, rot: int
) -> None:
    cli = kicad_cli()
    assert cli is not None
    if kicad_cli_major() == 9:
        pytest.skip("no `pcb import` before 10.0")
    config = tmp_path / "config"
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(config))
    script = blink_variant(
        tmp_path / "s", PLACE, f'u1.place(mm(14), mm(15), rot={rot}, side="bottom", locked=True)'
    )
    assert build(monkeypatch, str(script), "--out", str(tmp_path / "k")) == 0
    (board,) = (tmp_path / "k").glob("*.kicad_pcb")
    out = tmp_path / "a"
    assert (
        build(monkeypatch, str(script), "--out", str(out), "--target", "altium", "--copper-from", str(board))
        == 0
    )
    (document,) = out.glob("*.PcbDoc")
    target = tmp_path / "back.kicad_pcb"
    proc = subprocess.run(
        [cli, "pcb", "import", "--format", "altium", "-o", str(target), str(document)],
        capture_output=True, text=True, timeout=300, check=False,
        env=oracle_env(config),
    )  # fmt: skip
    assert target.is_file(), proc.stdout + proc.stderr
    source = read_board(board.read_text(encoding="utf-8"), file=board.name)
    back = read_board(target.read_text(encoding="utf-8"), file=target.name)
    here, there = pads(source), pads(back)
    assert ("U1", "1") in here and sorted(there) == sorted(here)
    for key, at in here.items():
        got = there[key]
        assert abs(got[0] - at[0]) <= TOLERANCE and abs(got[1] - at[1]) <= TOLERANCE, (key, at, got)
    stored, imported = controller(source), controller(back)
    assert imported.side == "bottom"  # type: ignore[attr-defined]
    assert imported.rotation % 360_000_000 == stored.rotation % 360_000_000  # type: ignore[attr-defined]
    wanted = sorted(library_pad_positions(stored))  # type: ignore[arg-type]
    got_pads = sorted(library_pad_positions(imported))  # type: ignore[arg-type]
    assert len(got_pads) == len(wanted)
    for (number, x, y), (want_number, want_x, want_y) in zip(got_pads, wanted, strict=True):
        assert number == want_number
        assert abs(x - want_x) <= TOLERANCE and abs(y - want_y) <= TOLERANCE, number
