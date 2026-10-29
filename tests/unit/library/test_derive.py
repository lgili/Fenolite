# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A library made from a board and its drift (capability design-conversion, "Library made from a board";
change c0223). The boards are the authored two-layer board of the test data and copies edited here."""

from __future__ import annotations

from pathlib import Path

from fenolite.backends.kicad.mod import read_footprint
from fenolite.library import derive_library, drift

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
SILK = (
    '\n\t(fp_line (start -1.5 -0.9) (end 1.5 -0.9) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n)'
)


def board_text() -> str:
    return BOARD.read_text(encoding="utf-8")


def with_second_resistor(text: str, *, moved: bool) -> str:
    """The board with a copy of ``R1`` named ``R9`` at another place, its pad 2 moved by 0.1 mm when
    ``moved``."""
    start = text.index('\t(footprint "Fenolite_Test:R_0603"')
    end = text.index('\t(footprint "Fenolite_Test:LED_THT_3mm"')
    copy = text[start:end].replace('"R1"', '"R9"').replace("(at 20 15 90)", "(at 10 25 90)")
    copy = copy.replace("d75df7ee-5c1f-4a9f-9213-5cb13ccc38b7", "d75df7ee-5c1f-4a9f-9213-5cb13ccc38b8")
    if moved:
        copy = copy.replace("(at 0.8 0 90)", "(at 0.9 0 90)")
    return text[:end] + copy + text[end:]


def test_footprints_in_their_own_frame() -> None:
    """Each footprint comes back to its origin, rotation 0 and the top side, named after the board's
    name, with Reference ``REF**``."""
    derived = derive_library(board_text(), library="lib", target=10)
    names = [fp.name for fp in derived.footprints]
    assert names == ["LED_THT_3mm", "R_0603"] and derived.issues == ()
    resistor = next(fp for fp in derived.footprints if fp.name == "R_0603")
    assert resistor.refs == ("R1",)
    pads = {pad.number: pad for pad in resistor.definition.pads}
    assert pads["1"].position.x == -800_000 and pads["1"].rotation == 0
    assert "(at" not in resistor.text.split("(pad", 1)[0].split("(property", 1)[0]
    assert '"REF**"' in resistor.text and "(net " not in resistor.text
    led = next(fp for fp in derived.footprints if fp.name == "LED_THT_3mm")
    assert all(
        not layer.startswith("B.") or layer == "B.Cu" for pad in led.definition.pads for layer in pad.layers
    )


def test_two_instances_that_differ() -> None:
    """Scenario "Two instances that differ"."""
    derived = derive_library(with_second_resistor(board_text(), moved=True), library="lib", target=10)
    assert [fp.name for fp in derived.footprints] == ["LED_THT_3mm", "R_0603", "R_0603_2"]
    assert [i.code for i in derived.issues] == ["library.instances-differ"]
    same = derive_library(with_second_resistor(board_text(), moved=False), library="lib", target=10)
    resistor = next(fp for fp in same.footprints if fp.name == "R_0603")
    assert resistor.refs == ("R1", "R9") and same.issues == ()


def test_drift_of_a_library(tmp_path: Path) -> None:
    """Scenario "Silkscreen edited on the board": the library's footprint holds a silkscreen line that the
    board's instance lacks; a footprint the library lacks is ``missing``."""
    derived = derive_library(board_text(), library="lib", target=10)
    folder = tmp_path / "old.pretty"
    folder.mkdir()
    assert drift(derived, folder) == (("LED_THT_3mm", ("missing",)), ("R_0603", ("missing",)))
    for name, text in derived.files().items():
        (folder / name).write_text(text, encoding="utf-8")
    assert drift(derived, folder) == ()
    path = folder / "R_0603.kicad_mod"
    edited = path.read_text(encoding="utf-8").rstrip().removesuffix(")") + SILK
    path.write_text(edited, encoding="utf-8")
    assert len(read_footprint(path).graphics_on("F.SilkS")) == 1
    assert drift(derived, folder) == (("R_0603", ("silkscreen",)),)
