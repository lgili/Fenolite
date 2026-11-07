# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pads on no net stay on no net (capability board-to-code, "Pads on no net in the vendored symbols";
change c0281, issue 2 of the board library's conversion report). The authored two-sheet board with two
shield pads ``0`` on no net added to ``J1``, made in the test's temporary folder."""

from __future__ import annotations

from pathlib import Path

from _importcode import BOARD, build, built_board, imported

from fenolite.api import read_board
from fenolite.backends.kicad.sym import read_symbol_library
from fenolite.checks.equivalence import compare_designs

SHIELD = """		(pad "0" thru_hole circle
			(at {x} 0 90)
			(size 1.8 1.8)
			(drill 0.9)
			(layers "*.Cu" "*.Mask")
			(remove_unused_layers no)
			(uuid "c0281000-0000-4000-8000-00000000000{n}")
		)
"""


def shielded(tmp: Path) -> Path:
    text = BOARD.read_text(encoding="utf-8")
    start = text.rindex("(footprint ", 0, text.index('"J1"'))
    at = text.index("\t\t(embedded_fonts no)", start)
    pads = SHIELD.format(x="-2.54", n=1) + SHIELD.format(x="5.08", n=2)
    folder = tmp / "shielded"
    folder.mkdir()
    target = folder / "shielded.kicad_pcb"
    target.write_text(text[:at] + pads + text[at:], encoding="utf-8")
    return target


def test_shield_pads_stay_on_no_net(tmp_path: Path) -> None:
    """Scenario "Shield pads stay on no net"."""
    source = shielded(tmp_path)
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    out = tmp_path / "out"
    symbols = [
        symbol
        for library in sorted((out / "lib").glob("*.kicad_sym"))
        for symbol in read_symbol_library(library.read_text(encoding="utf-8"))
    ]
    j1 = [s for s in symbols if {p.number for p in s.pins} >= {"1", "2"} and len(s.pins) == 2]
    assert j1 and all("0" not in {p.number for p in s.pins} for s in symbols)
    built = build(out)
    assert built.exit_code == 0, built.error
    assert (out / "built" / "shielded.kicad_sch").is_file()  # built with its schematic
    design = built_board(out, "shielded").design
    refs = {c.id: c.ref for c in design.circuit.components}
    (footprint,) = [fp for fp in design.board.footprints if refs[fp.component_id] == "J1"]  # type: ignore[union-attr]
    assert [pad.net_id for pad in footprint.pads if pad.number == "0"] == [None, None]
    original = read_board(source).design
    report = compare_designs(original, design, level=2)
    assert report.levels[1].differences == ()
