# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The authored library of the net-role reference boards (change c0222; task 3.1): every footprint and
symbol of ``tests/data/libs/Roles.pretty`` and ``Roles.kicad_sym`` loads without an error, and each one opens
its description with the authored-for-Fenolite line. A KiCad file holds no comment, so the line is the first
text a reader meets in it: the footprint's ``descr`` and each symbol's ``Description``."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.sym import read_symbol_library
from fenolite.core.errors import Issue

LIBS = Path(__file__).resolve().parents[3] / "tests" / "data" / "libs"
AUTHORED = "Authored for Fenolite (CC0-1.0)"
FOOTPRINTS = sorted((LIBS / "Roles.pretty").glob("*.kicad_mod"))
SYMBOLS = (
    "Roles_Cell_Monitor",
    "Roles_HalfBridge_Driver",
    "Roles_NMOS",
    "Roles_NMOS_Kelvin",
    "Roles_Sense_Amplifier",
    "Roles_Shunt_4T",
)


def test_the_library_holds_every_part_of_the_design() -> None:
    assert [path.stem for path in FOOTPRINTS] == [
        "Roles_Inductor_7x7",
        "Roles_MOSFET_K4",
        "Roles_MOSFET_SO8",
        "Roles_Shunt_2512",
        "Roles_Shunt_4T",
        "Roles_Terminal_2P",
    ]


@pytest.mark.parametrize("path", FOOTPRINTS, ids=lambda path: path.stem)
def test_footprint_loads_and_is_authored(path: Path) -> None:
    issues: list[Issue] = []
    footprint = read_footprint(path, library="Roles", issues=issues)
    assert not [found for found in issues if found.severity == "error"], issues
    assert footprint.description.startswith(AUTHORED)
    text = path.read_text(encoding="utf-8")
    assert text.index('(descr "' + AUTHORED) < text.index("(property ")
    assert footprint.pads, path.stem


def test_symbols_load_and_are_authored() -> None:
    issues: list[Issue] = []
    symbols = {symbol.name: symbol for symbol in read_symbol_library(LIBS / "Roles.kicad_sym", issues=issues)}
    assert not [found for found in issues if found.severity == "error"], issues
    assert sorted(symbols) == list(SYMBOLS)
    for symbol in symbols.values():
        assert symbol.properties["Description"].startswith(AUTHORED), symbol.name


def test_symbol_pins_name_the_terminals() -> None:
    """The pin names that the classes of ``roles.classify`` read."""
    symbols = {symbol.name: symbol for symbol in read_symbol_library(LIBS / "Roles.kicad_sym")}

    def names(name: str) -> dict[str, str]:
        return {pin.number: pin.name for pin in symbols[name].pins}

    assert names("Roles_NMOS") == {"1": "S", "2": "G", "3": "D"}
    assert names("Roles_NMOS_Kelvin") == {"1": "G", "2": "KS", "3": "S", "4": "D"}
    assert names("Roles_Shunt_4T") == {"1": "F1", "2": "S1", "3": "S2", "4": "F2"}
    assert {"HO", "HS", "LO", "COM"} <= set(names("Roles_HalfBridge_Driver").values())
    assert {"IN+", "IN-", "OUT"} <= set(names("Roles_Sense_Amplifier").values())
    assert {"SRP", "SRN", "CHG", "DSG", "COM"} <= set(names("Roles_Cell_Monitor").values())
