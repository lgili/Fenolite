# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Symbol folders and derived symbols (kicad-library-read: "Symbol library reading", "Derived symbols")."""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

import pytest
from _libs import MINI, make_symdir

from fenolite.backends.kicad.liberrors import LibraryError
from fenolite.backends.kicad.sym import read_symbol_library, resolve_extends
from fenolite.core.errors import FormatError
from fenolite.model.library import SymbolDef

V10 = MINI / "Mini.kicad_sym"


def _lib(body: str) -> str:
    return f'(kicad_symbol_lib (version 20251024) (generator "t") {body})'


def _strip(symbols: tuple[SymbolDef, ...]) -> dict[str, SymbolDef]:
    return {s.name: dataclasses.replace(s, provenance=None) for s in symbols}


def test_folder_and_file_give_the_same_symbols(tmp_path: Path) -> None:
    folder = make_symdir(V10, tmp_path / "Mini.kicad_symdir")
    assert sorted(p.name for p in folder.iterdir()) == sorted(
        f"{s.name}.kicad_sym" for s in read_symbol_library(V10)
    )
    from_file = resolve_extends(read_symbol_library(V10, library="Mini"))
    from_folder = resolve_extends(read_symbol_library(folder, library="Mini"))
    assert _strip(from_folder) == _strip(from_file)
    assert read_symbol_library(folder)[0].library == "Mini"


def test_folder_files_are_read_in_sorted_order(tmp_path: Path) -> None:
    folder = make_symdir(V10, tmp_path / "Mini.kicad_symdir")
    names = [s.name for s in read_symbol_library(folder)]
    assert names == sorted(names)
    provenance = read_symbol_library(folder)[0].provenance
    assert provenance is not None and provenance.file.endswith("Mini_DualGate.kicad_sym")


def test_dispatch_is_on_is_dir_not_on_the_suffix(tmp_path: Path) -> None:
    folder = make_symdir(V10, tmp_path / "Odd.kicad_sym")
    assert len(read_symbol_library(folder)) == 6 and read_symbol_library(folder)[0].library == "Odd"


def test_folder_with_a_foreign_file(tmp_path: Path) -> None:
    folder = tmp_path / "Bad.kicad_symdir"
    folder.mkdir()
    shutil.copyfile(MINI / "Mini.pretty" / "Mini_R_0603.kicad_mod", folder / "Intruder.kicad_sym")
    with pytest.raises(FormatError, match="Intruder.kicad_sym"):
        read_symbol_library(folder)


def test_empty_folder(tmp_path: Path) -> None:
    folder = tmp_path / "Empty.kicad_symdir"
    folder.mkdir()
    (folder / "notes.txt").write_text("not a library", encoding="utf-8")
    assert read_symbol_library(folder) == ()


def test_derived_led_inherits_pins() -> None:
    symbols = {s.name: s for s in resolve_extends(read_symbol_library(V10))}
    red, led = symbols["Mini_LED_Red"], symbols["Mini_LED"]
    assert red.pins == led.pins and red.units == led.units and len(red.pins) == 2
    assert red.value == "Mini_LED_Red" and red.footprint == "Mini:Mini_LED_THT_3mm"
    assert red.extends == "Mini_LED" and red.id != led.id
    assert red.pin_names_hidden == led.pin_names_hidden and red.pin_name_offset == led.pin_name_offset


def test_parent_properties_fill_the_gaps() -> None:
    text = _lib(
        '(symbol "P" (property "Footprint" "L:F") (property "Value" "P") (in_bom no)'
        ' (symbol "P_1_1" (pin input line (at 0 0 0) (length 1) (name "I") (number "1"))))'
        ' (symbol "C" (extends "P") (property "Value" "C"))'
    )
    child = {s.name: s for s in resolve_extends(read_symbol_library(text))}["C"]
    assert child.footprint == "L:F" and child.value == "C" and not child.in_bom and len(child.pins) == 1


def test_chains_are_followed() -> None:
    text = _lib(
        '(symbol "A" (extends "B")) (symbol "B" (extends "C") (property "Value" "B"))'
        ' (symbol "C" (symbol "C_1_1" (pin passive line (at 0 0 0) (length 1) (name "x") (number "1"))))'
    )
    flat = {s.name: s for s in resolve_extends(read_symbol_library(text))}
    assert len(flat["A"].pins) == 1 and flat["A"].value == "B" and flat["A"].extends == "B"
    assert [s.name for s in resolve_extends(read_symbol_library(text))] == ["A", "B", "C"]


def test_missing_parent() -> None:
    with pytest.raises(LibraryError) as caught:
        resolve_extends(read_symbol_library(_lib('(symbol "A" (extends "B"))')))
    assert caught.value.issue.code == "kicad.lib.missing-parent" and "'B'" in caught.value.issue.message
    assert caught.value.cli_code == "FEN-3001"


@pytest.mark.parametrize(
    "body",
    ['(symbol "A" (extends "B")) (symbol "B" (extends "A"))', '(symbol "A" (extends "A"))'],
    ids=["pair", "self"],
)
def test_cycle(body: str) -> None:
    with pytest.raises(LibraryError) as caught:
        resolve_extends(read_symbol_library(_lib(body)))
    assert caught.value.issue.code == "kicad.lib.extends-cycle"
