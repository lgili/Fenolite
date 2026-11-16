# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Through-hole pads of a four-layer board converted and built for Altium (change c0488): the written
document holds every inner copper layer, its Multi-Layer pads read back on all of them, and the
conversion's verification gives no ``convert.unexplained``. The board and the script are authored for
Fenolite."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from fenolite.api.conversion import convert
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.kicad import boardcarrier
from fenolite.convert import altium_planes, read_source
from fenolite.model.board import Board

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "convert" / "four_layer_tht.kicad_pcb"
EXAMPLE = ROOT / "examples" / "blink_2layer"
FOUR = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def _carrier(carried: altium_planes.Carried) -> str:
    """The root property that carries ``carried`` through KiCad, as a conversion from Altium writes it."""
    value = boardcarrier.pack(altium_planes.carrier_text(carried).encode("utf-8"))
    return f'\t(property "{altium_planes.PROPERTY}" "{value}")\n'


PLANE = altium_planes.Carried(planes=(altium_planes.Plane("In1.Cu", "GND", 508_000),))
SKIPPED = altium_planes.Carried(planes=(), signals=(("In1.Cu", 3), ("In2.Cu", 5)))
CASES = {
    "signal": (),
    # In1.Cu a GND plane carried from an Altium source (change c0466); J2's pad is on GND
    "plane": (
        ('(net "SIG")\n\t\t\t(uuid "9a22', '(net "GND")\n\t\t\t(uuid "9a22'),
        ("(setup", _carrier(PLANE) + "\t(setup"),
        ('(4 "In1.Cu" signal)', '(4 "In1.Cu" power "Internal Plane 1")'),
    ),
    # carried Altium signal ids that skip Mid-Layer 1 (``lower._signal_ids``)
    "skipped-ids": (("(setup", _carrier(SKIPPED) + "\t(setup"),),
}


def _copper(board: Board) -> tuple[list[str], list[tuple[str, ...]]]:
    names = [layer.name for layer in board.layers if layer.kind == "copper"]
    return names, [pad.layers for footprint in board.footprints for pad in footprint.pads]


@pytest.mark.parametrize("case", sorted(CASES))
def test_four_layer_board_through_convert(tmp_path: Path, case: str) -> None:
    """Scenario "Four-layer board through convert"."""
    text = BOARD.read_text("utf-8")
    for old, new in CASES[case]:
        assert old in text
        text = text.replace(old, new, 1)
    source = tmp_path / "source" / BOARD.name
    source.parent.mkdir()
    source.write_text(text, "utf-8")
    result = convert(source, to="altium", allow_lossy=True)
    assert result.equivalence is not None
    assert result.unexplained == ()
    assert [i.code for i in result.issues if i.code == "convert.unexplained"] == []
    (name, written), *_ = [(n, d) for n, d in result.conversion.files.items() if n.endswith(".PcbDoc")]
    chain = read_pcbdoc(written).board.copper_chain
    assert len(chain) == 4
    back = tmp_path / "back" / Path(name).name
    back.parent.mkdir()
    back.write_bytes(written)
    board = read_source(back).design.board
    assert board is not None
    assert _copper(board) == (list(FOUR), [FOUR, FOUR])
    if case == "plane":
        assert chain == (1, 39, 3, 32)
    if case == "skipped-ids":
        assert chain == (1, 3, 5, 32)


def test_four_layer_board_through_build(tmp_path: Path) -> None:
    """Scenario "Four-layer board through build": the blink example on four copper layers; its LED is a
    through-hole part."""
    from fenolite.cli.main import main

    folder = tmp_path / "src"
    shutil.copytree(EXAMPLE, folder)
    script = folder / "design.py"
    text = script.read_text("utf-8")
    script.write_text(text.replace("design.board(mm(50), mm(30))", "design.board(mm(50), mm(30), copper=4)"))
    for table in ("fp-lib-table", "sym-lib-table"):
        path = folder / table
        path.write_text(path.read_text("utf-8").replace("${KIPRJMOD}/../..", ROOT.as_posix()), "utf-8")
    out = tmp_path / "out"
    code = main(["build", str(script), "--target", "altium", "--out", str(out), "--confirm", "--json"])
    assert code == 0
    written = out / "blink.PcbDoc"
    assert read_pcbdoc(written.read_bytes()).board.copper_chain == (1, 2, 3, 32)
    board = read_source(written).design.board
    assert board is not None
    held = [pad.layers for footprint in board.footprints for pad in footprint.pads if pad.kind == "thru_hole"]
    assert _copper(board)[0] == list(FOUR)
    assert held and all(layers == FOUR for layers in held)
