# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Sheets of a module tree (capability altium-schematic-writer, "Sheets of a module tree"; change c0086):
one sheet per module at any depth, file and sheet names, crossings passed through the sheet between, and
the link of a PCB component through one sheet symbol per level. Read back with the product reader and
importer (``H-A-SCHX-READBACK``, INFERRED)."""

from __future__ import annotations

from pathlib import Path

from _altium_tree import (
    TREE_FILES,
    TREE_NETS,
    documents,
    nets_of,
    project_files,
    read_back,
    tree_build,
    tree_model,
)

from fenolite.backends.altium.hierarchy import (
    crossings,
    module_key,
    module_of,
    sheet_file,
    sheet_name,
    sheet_tree,
    symbol_id,
)
from fenolite.backends.altium.project import unique_id
from fenolite.backends.altium.read.sch import SheetEntry


def test_tree_order_and_names() -> None:
    model = tree_model()
    assert sheet_tree(model) == ("io", "io/leds", "power")
    assert [sheet_file("tree", m) for m in sheet_tree(model)] == [
        "tree_io.SchDoc",
        "tree_io.leds.SchDoc",
        "tree_power.SchDoc",
    ]
    assert sheet_file("tree") == "tree.SchDoc" and sheet_name("io/leds") == "leds"
    assert module_of("io/leds/D1") == "io/leds" and module_of("io") == "" and module_of("J1") == ""
    # a module before its sub-modules, siblings in natural order
    assert sorted(["m10", "m2", "m2/b", "m2/a10", "m2/a9"], key=module_key) == [
        "m2",
        "m2/a9",
        "m2/a10",
        "m2/b",
        "m10",
    ]


def test_two_levels(tmp_path: Path) -> None:
    """Scenario "Two levels": four documents, the sheet of ``io`` holds a sheet symbol for ``leds``, and
    the netlist read from the project equals the design's, in both forms."""
    for form in ("binary", "ascii"):
        output = tree_build(form=form)
        assert sorted(project_files(output)) == sorted(TREE_FILES)
        sheets = documents(output)
        assert len(sheets) == 4
        names = {file: [n.text for s in doc.sheet_symbols() for n in doc.children_of(s) if n.record_id == 32]
                 for file, doc in sheets.items()}  # fmt: skip
        assert names == {
            "tree.SchDoc": ["io", "power"],
            "tree_io.SchDoc": ["leds"],
            "tree_io.leds.SchDoc": [],
            "tree_power.SchDoc": [],
        }
        files = [n.text for s in sheets["tree_io.SchDoc"].sheet_symbols()
                 for n in sheets["tree_io.SchDoc"].children_of(s) if n.record_id == 33]  # fmt: skip
        assert files == ["tree_io.leds.SchDoc"]
        design = read_back(tmp_path / form, output)
        assert nets_of(design) == TREE_NETS
        assert sorted(m.path for m in design.circuit.modules) == ["io", "io/leds", "power"]


def test_project_file_lists_the_sheets_in_tree_order() -> None:
    text = project_files(tree_build())["tree.PrjPcb"].decode("ascii")
    listed = [line.split("=", 1)[1] for line in text.splitlines() if line.startswith("DocumentPath=")]
    assert listed == [
        "tree.SchDoc",
        "tree_io.SchDoc",
        "tree_io.leds.SchDoc",
        "tree_power.SchDoc",
        "tree.SchLib",
    ]


def test_a_net_that_crosses_two_levels_is_passed_through() -> None:
    """``D0`` to ``D3`` have pins on the top sheet and on ``io/leds`` only: they cross ``io`` too, so the
    sheet of ``io`` holds a port and, on the symbol of ``leds``, a sheet entry of the same name."""
    found = crossings(tree_model(), form="binary")
    assert list(found) == ["io", "io/leds", "power"]
    assert [c.name for c in found["io"]] == ["ALARM", "D[0..3]", "SENSE", "SENSE_IN"]
    assert [c.name for c in found["io/leds"]] == ["D[0..3]", "LED_K"]
    assert found["power"] == ()  # its nets are power nets or stay inside
    sheets = documents(tree_build())
    io = sheets["tree_io.SchDoc"]
    assert sorted(p.name for p in io.ports()) == ["ALARM", "D[0..3]", "SENSE", "SENSE_IN"]
    assert sorted(e.name for e in io.of_type(SheetEntry)) == ["D[0..3]", "LED_K"]
    assert sorted(p.name for p in sheets["tree_io.leds.SchDoc"].ports()) == ["D[0..3]", "LED_K"]
    assert sorted(e.name for e in sheets["tree.SchDoc"].of_type(SheetEntry)) == [
        "ALARM",
        "D[0..3]",
        "SENSE",
        "SENSE_IN",
    ]


def test_sheet_symbol_ids_are_stable() -> None:
    first, second = documents(tree_build()), documents(tree_build())
    for file, sheet in first.items():
        assert [s.unique_id for s in sheet.sheet_symbols()] == [
            s.unique_id for s in second[file].sheet_symbols()
        ]
    assert symbol_id("io/leds") == unique_id("sheet:io/leds")
    assert [s.unique_id for s in first["tree.SchDoc"].sheet_symbols()] == [
        symbol_id("io"),
        symbol_id("power"),
    ]
    assert [s.unique_id for s in first["tree_io.SchDoc"].sheet_symbols()] == [symbol_id("io/leds")]


def test_flat_stays_one_sheet() -> None:
    output = tree_build(sheets="flat")
    assert sorted(n for n in project_files(output) if n.endswith(".SchDoc")) == ["tree.SchDoc"]
    (sheet,) = documents(output).values()
    assert sheet.sheet_symbols() == () and sheet.ports() == ()
