# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.library.coverage``: a design's footprints against a house library that the user names (change
c0175, task 10.4). Authored footprints and libraries written into a temporary folder; hermetic."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import pytest

from fenolite.backends.altium import pcblib
from fenolite.backends.kicad.mod import read_footprint, write_footprint
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import Footprint, nm
from fenolite.lens.altium import pad_extras
from fenolite.library.coverage import coverage, library_coverage, load_library, pad_shapes
from fenolite.model.board import Board, FootprintInstance
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

MM = 1_000_000


def footprint(name: str, pads: Mapping[str, tuple[float, float]]) -> FootprintDef:
    drawn = Footprint("House", name, kind="smd")
    for number, (x, y) in pads.items():
        drawn.pad(number, at=(nm(round(x * MM)), nm(round(y * MM))), size=(nm(MM), nm(MM // 2)))
    return drawn.definition


SOT = {"1": (-1, 1), "2": (1, 1), "3": (0, -1)}
CHIP = {"1": (-0.8, 0), "2": (0.8, 0)}


def design(*placed: tuple[str, FootprintDef]) -> Design:
    parts = tuple(
        FootprintInstance(
            id=derived_id("fp", "coverage", f"{lib_ref}.{index}"),
            component_id=derived_id("cmp", "coverage", f"{lib_ref}.{index}"),
            lib_ref=lib_ref,
            position=Point(10 * MM * index, 0),
            pads=definition.pads,
        )
        for index, (lib_ref, definition) in enumerate(placed)
    )
    base = Design.new("coverage", seed=1)
    return replace(base, board=Board(id=derived_id("brd", "coverage", "board"), footprints=parts))


LIBRARY = (footprint("SOT23", SOT), footprint("R0603", CHIP))


def test_statuses() -> None:
    moved = {n: (x + 5, y - 2) for n, (x, y) in SOT.items()}  # another origin: the same land pattern
    turned = {n: (y, -x) for n, (x, y) in CHIP.items()}  # a quarter turn of R0603
    wide = {n: (x * 2, y) for n, (x, y) in CHIP.items()}  # same name, other pads
    board = design(
        ("Board:SOT23", footprint("SOT23", moved)),
        ("Board:SOT23", footprint("SOT23", SOT)),
        ("Board:CHIP_V", footprint("CHIP_V", turned)),
        ("Board:R0603", footprint("R0603", wide)),
        ("Board:QFN8", footprint("QFN8", {str(n): (n, 0) for n in range(8)})),
    )
    report = coverage(board, LIBRARY, name="house")
    rows = {row.footprint: (row.status, row.match, row.parts) for row in report.rows}
    assert rows == {
        "Board:SOT23": ("same", "SOT23", 2),
        "Board:CHIP_V": ("renamed", "R0603", 1),
        "Board:R0603": ("differs", None, 1),
        "Board:QFN8": ("missing", None, 1),
    }
    assert report.counts == {"same": 1, "renamed": 1, "differs": 1, "missing": 1}
    assert report.footprints == 2 and report.library == "house"


def test_grid_absorbs_rounding() -> None:
    near = {n: (x + 0.0003, y) for n, (x, y) in SOT.items()}
    assert pad_shapes(footprint("A", near).pads)[0] == pad_shapes(footprint("A", SOT).pads)[0]


def test_library_read_from_folders_and_files(tmp_path: Path) -> None:
    house = tmp_path / "house"
    pretty = house / "Passive.pretty"
    pretty.mkdir(parents=True)
    chip = read_footprint(write_footprint(LIBRARY[1]), library="Passive")
    (pretty / "R0603.kicad_mod").write_text(write_footprint(chip), encoding="utf-8")
    sot = LIBRARY[0]
    (house / "Active.PcbLib").write_bytes(
        pcblib.write_pcblib([pcblib.LibFootprint(sot, pad_extras(sot))], filename="Active.PcbLib")
    )
    (house / "notes.txt").write_text("not a library", encoding="utf-8")
    names = sorted(found.name for found in load_library(house))
    assert names == ["R0603", "SOT23"]
    report = library_coverage(design(("Board:SOT23", LIBRARY[0]), ("Board:R0603", LIBRARY[1])), house)
    assert [row.status for row in report.rows] == ["same", "same"]
    text = json.dumps(report.to_json())
    assert str(tmp_path) not in text and report.library == "house"
    assert [found.name for found in load_library(pretty / "R0603.kicad_mod")] == ["R0603"]
    with pytest.raises(FileNotFoundError):
        load_library(tmp_path / "absent")


def test_board_less_design() -> None:
    report = coverage(Design.new("empty", seed=1), LIBRARY)
    assert report.rows == () and report.counts == {"same": 0, "renamed": 0, "differs": 0, "missing": 0}
