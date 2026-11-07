# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A footprint variant whose ``<name>_2`` is the name of another footprint of the board (capability
board-to-code; change c0425). The variant takes the next free suffix, so the vendored library holds one
footprint and one symbol per name and the code builds. The authored two-sheet board, with ``D201``'s pad 2
moved (a variant of ``Mini_LED_THT_3mm``) and ``J1`` on a footprint named ``Mini_LED_THT_3mm_2``, made in
the test's temporary folder."""

from __future__ import annotations

from pathlib import Path

from _importcode import BOARD, imported

from fenolite.backends.kicad.sym import read_symbol_library


def colliding(tmp: Path) -> Path:
    text = BOARD.read_text(encoding="utf-8")
    j1 = text.rindex('(footprint "Mini:Mini_LED_THT_3mm"', 0, text.index('"J1"'))
    text = text[:j1] + text[j1:].replace('"Mini:Mini_LED_THT_3mm"', '"Mini:Mini_LED_THT_3mm_2"', 1)
    d201 = text.index('"D201"')
    pad = text.index('(pad "2"', d201)
    text = text[:pad] + text[pad:].replace("(at 2.54 0)", "(at 2.64 0)", 1)
    folder = tmp / "colliding"
    folder.mkdir()
    target = folder / "colliding.kicad_pcb"
    target.write_text(text, encoding="utf-8")
    return target


def test_a_variant_never_takes_a_footprint_name_of_the_board(tmp_path: Path) -> None:
    """Scenario "A variant name the board already holds"."""
    reply = imported(tmp_path, colliding(tmp_path), "--confirm")
    assert reply.exit_code == 0, reply.error
    issues = reply.envelope["issues"]  # type: ignore[index]
    assert not [i for i in issues if i["code"] == "import.unequal"], issues
    out = tmp_path / "out"
    names = sorted(path.stem for path in (out / "lib").glob("*.pretty/*.kicad_mod"))
    assert names == ["Mini_LED_THT_3mm", "Mini_LED_THT_3mm_2", "Mini_LED_THT_3mm_3", "Mini_R_0603"]
    symbols = [
        s.name for f in sorted((out / "lib").glob("*.kicad_sym")) for s in read_symbol_library(f.read_text())
    ]
    assert sorted(symbols) == sorted(set(symbols))
