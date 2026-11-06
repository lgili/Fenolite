# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Flow B, an Altium PCB document converted to KiCad and back to Altium, is ``equivalent`` to its source
when the source holds a footprint name with ``/`` and free holes (change c0435). The source is written by
Fenolite from the committed ``tests/data/kicad/board/two_layer.kicad_pcb``, its resistor renamed
``R/0603`` and two authored mounting holes added: footprints without a reference whose one pad is unplated
and unnumbered, which the Altium document holds as free holes."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from fenolite.api import convert, run
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.checks.equivalence import norm
from fenolite.core.libnames import library_name

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
LED = '\t(footprint "Fenolite_Test:LED_THT_3mm"'


def _hole(k: int, x: int) -> str:
    uuid = f"{k}0000000-0435-4000-8000-00000000000"
    font = "(effects (font (size 1 1) (thickness 0.15)))"
    return (
        '\t(footprint "Fenolite_Test:MountingHole_3.2mm"\n\t\t(layer "F.Cu")\n'
        f'\t\t(uuid "{uuid}1")\n\t\t(at {x} 25)\n'
        f'\t\t(property "Reference" "" (at 0 -4 0) (layer "F.SilkS") (uuid "{uuid}2") {font})\n'
        f'\t\t(property "Value" "MountingHole" (at 0 4 0) (layer "F.Fab") (uuid "{uuid}3") {font})\n'
        "\t\t(attr exclude_from_pos_files exclude_from_bom)\n"
        '\t\t(pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2) (layers "*.Cu" "*.Mask") '
        f'(uuid "{uuid}5"))\n\t)\n'
    )


def _write(files: Mapping[str, bytes], folder: Path) -> None:
    for name, data in files.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def _source(tmp_path: Path) -> Path:
    text = BOARD.read_text(encoding="utf-8").replace(
        '(footprint "Fenolite_Test:R_0603"', '(footprint "Fenolite_Test:R/0603"', 1
    )
    at = text.index(LED)
    board = tmp_path / "kicad" / "flow.kicad_pcb"
    board.parent.mkdir()
    board.write_text(text[:at] + _hole(1, 5) + _hole(2, 45) + text[at:], encoding="utf-8")
    _write(convert(board, to="altium", allow_lossy=True).conversion.files, tmp_path / "source")
    return tmp_path / "source" / "flow.PcbDoc"


def _flow_b(source: Path, tmp_path: Path) -> Path:
    _write(convert(source, to="kicad", allow_lossy=True).conversion.files, tmp_path / "kicad2")
    (board,) = (tmp_path / "kicad2").glob("*.kicad_pcb")
    _write(convert(board, to="altium", allow_lossy=True).conversion.files, tmp_path / "result")
    (document,) = (tmp_path / "result").glob("*.PcbDoc")
    return document


def test_the_source_holds_the_cases(tmp_path: Path) -> None:
    design = AltiumBackend().read(_source(tmp_path)).design
    assert design.board is not None and len(design.board.holes) == 2
    assert "R/0603" in {fp.lib_ref.rpartition(":")[2] for fp in design.board.footprints}


def test_flow_b_is_equivalent_to_its_source(tmp_path: Path) -> None:
    source = _source(tmp_path)
    result = _flow_b(source, tmp_path)
    back = AltiumBackend().read(result).design
    assert back.board is not None and len(back.board.holes) == 2
    refs = sorted(c.ref for c in back.circuit.components)
    assert refs == ["", "", "D1", "R1"]  # the mounting holes; no component for a free hole
    reply = run("equivalent", str(source), str(result), "--json", cwd=tmp_path)
    assert reply.exit_code == 0, (reply.error, (reply.result or {}).get("differences"))


def test_footprint_names_compare_after_the_library_rewrite() -> None:
    assert library_name("R/0603", allow_space=True) == "R_0603"
    assert norm.same_footprint_name("R/0603", "R_0603")
    assert not norm.same_footprint_name("R_0603", "R_0805")
    assert not norm.same_footprint_name("R/0603", "R_0603_2")
