# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The sheets of a hierarchical project (capability altium-schematic-writer, "Sheets of a hierarchical
project" and "Harness definition files"; change c0037)."""

from __future__ import annotations

import pytest
from _altium import HIER_PARTIAL, check_plan, hier_model, model_of, sample_model

from fenolite.backends.altium.hierarchy import crossings, plan_sheets, port_id, sheet_file, sheet_of
from fenolite.backends.altium.project import DEFAULT_SHEETS, component_path, plan_sheet
from fenolite.dsl import Design, Net, Part, connect

NESTED = ("mcu.add(u1, c1)", 'decoupling = Module("decoupling")\ndecoupling.add(c1)\nmcu.add(u1, decoupling)')


def _refs(plan: object) -> list[str]:
    return [part.spec.ref for part in plan.parts]  # type: ignore[attr-defined]


def test_sheets_of_the_components() -> None:
    model = hier_model()
    found = {c.ref: sheet_of(c) for c in model.circuit.components}
    assert found == {"J1": None, "U1": "mcu", "C1": "mcu", "U2": "flash", "C2": "flash", "R1": "flash"}


def test_sheets_default_is_flat() -> None:
    assert DEFAULT_SHEETS == "flat"


def test_sheets_file_names() -> None:
    assert sheet_file("altium_hier") == "altium_hier.SchDoc"
    assert sheet_file("altium_hier", "flash") == "altium_hier_flash.SchDoc"


def test_sheets_hold_their_parts() -> None:
    project = plan_sheets(hier_model(), name="altium_hier", sheets="modules", form="ascii")
    assert project.mode == "modules"
    assert [(s.file, s.module, _refs(s.plan)) for s in project.sheets] == [
        ("altium_hier.SchDoc", None, ["J1"]),
        ("altium_hier_flash.SchDoc", "flash", ["C2", "R1", "U2"]),
        ("altium_hier_mcu.SchDoc", "mcu", ["C1", "U1"]),
    ]
    assert project.top is project.sheets[0] and project.modules == project.sheets[1:]


def test_sheets_keep_the_component_records_of_the_flat_build() -> None:
    """Every component keeps its spec (unique id, pins and the way each pin joins its net) in both modes."""
    model = hier_model()
    flat = {p.spec.key: p.spec for p in plan_sheet(model, name="altium_hier").parts}
    project = plan_sheets(model, name="altium_hier", sheets="modules", form="binary")
    split = {p.spec.key: p.spec for s in project.sheets for p in s.plan.parts}
    assert split == flat
    stubs = sorted((s.key, s.designator, s.net) for sheet in project.sheets for s in sheet.plan.stubs)
    assert stubs == sorted((s.key, s.designator, s.net) for s in plan_sheet(model, name="altium_hier").stubs)


def test_nested_module_is_flattened() -> None:
    model = hier_model(*NESTED)
    c1 = next(c for c in model.circuit.components if c.ref == "C1")
    assert component_path(c1) == "mcu/decoupling/C1" and sheet_of(c1) == "mcu"
    project = plan_sheets(model, name="altium_hier", sheets="modules", form="binary")
    assert [s.file for s in project.sheets] == [
        "altium_hier.SchDoc",
        "altium_hier_flash.SchDoc",
        "altium_hier_mcu.SchDoc",
    ]
    assert _refs(project.sheets[2].plan) == ["U1", "C1"]
    assert not any("decoupling" in s.file for s in project.sheets)


def test_harness_members_cross_as_nets_in_the_ascii_form() -> None:
    model = hier_model()
    found = crossings(model, form="ascii")
    assert list(found) == ["flash", "mcu"]
    assert [c.name for c in found["flash"]] == ["FLASH_WP", "SPI_CS", "SPI_MISO", "SPI_MOSI", "SPI_SCK"]
    assert [c.name for c in found["mcu"]] == [
        "FLASH_WP",
        "RESET_N",
        "SPI_CS",
        "SPI_MISO",
        "SPI_MOSI",
        "SPI_SCK",
    ]
    assert not any(c.harness for module in found.values() for c in module)
    project = plan_sheets(model, name="altium_hier", sheets="modules", form="ascii")
    assert all(not sheet.plan.harnesses for sheet in project.sheets)


def test_ascii_power_and_local_nets_cross_nothing() -> None:
    names = {c.name for module in crossings(hier_model(), form="ascii").values() for c in module}
    assert not names & {"VDD", "GND", "FLASH_HOLD_N"}


def test_flat_mode_is_the_single_sheet() -> None:
    model = hier_model()
    project = plan_sheets(model, name="altium_hier", sheets="flat", form="binary")
    assert project.mode == "flat" and len(project.sheets) == 1
    (sheet,) = project.sheets
    assert sheet.file == "altium_hier.SchDoc" and sheet.module is None and sheet.symbol_id is None
    assert sheet.plan == plan_sheet(model, name="altium_hier")


def test_flat_and_modules_agree_without_a_module() -> None:
    """A design without a module gives the same top-sheet plan in both modes."""
    design = Design("x")
    r1, r2 = Part("R1", "L.SchLib:RES"), Part("R2", "L.SchLib:RES")
    design.add(r1, r2)
    connect(Net("A"), r1[1], r2[1])
    connect(Net("B"), r1[2], r2[2])
    model = model_of(design)
    flat = plan_sheets(model, name="x", sheets="flat", form="binary")
    split = plan_sheets(model, name="x", sheets="modules", form="binary")
    assert split.sheets == flat.sheets and split.mode == "modules"


def test_flat_mode_of_a_design_with_modules() -> None:
    model = sample_model()
    project = plan_sheets(model, name="altium_sample", sheets="flat", form="ascii")
    assert [s.file for s in project.sheets] == ["altium_sample.SchDoc"]


def test_sheets_refuse_unknown_values() -> None:
    model = hier_model()
    with pytest.raises(ValueError, match="sheet mode"):
        plan_sheets(model, name="x", sheets="pages", form="binary")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="schematic form"):
        plan_sheets(model, name="x", sheets="modules", form="text")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="schematic form"):
        crossings(model, form="text")  # type: ignore[arg-type]


# --- harness crossings (binary form only) -----------------------------------------------------------

SPI = (("CS", "SPI_CS"), ("MISO", "SPI_MISO"), ("MOSI", "SPI_MOSI"), ("SCK", "SPI_SCK"))
DBG = '\ndesign.add(Harness("DBG", {"RST": reset_n}))\n'


def test_harness_sheets_of_the_hierarchy_sample() -> None:
    """Scenario "Sheets of the hierarchy sample" (binary form)."""
    model = hier_model()
    project = plan_sheets(model, name="altium_hier", sheets="modules", form="binary")
    assert [(s.file, _refs(s.plan)) for s in project.sheets] == [
        ("altium_hier.SchDoc", ["J1"]),
        ("altium_hier_flash.SchDoc", ["C2", "R1", "U2"]),
        ("altium_hier_mcu.SchDoc", ["C1", "U1"]),
    ]
    found = crossings(model, form="binary")
    assert [(c.name, c.harness) for c in found["flash"]] == [("FLASH_WP", False), ("SPI", True)]
    assert [(c.name, c.harness) for c in found["mcu"]] == [
        ("FLASH_WP", False),
        ("RESET_N", False),
        ("SPI", True),
    ]
    assert found["flash"][1].entries == found["mcu"][2].entries == SPI
    assert found["flash"][1].port_id == port_id("flash", "SPI") != found["mcu"][2].port_id
    crossing = {c.name for module in found.values() for c in module}
    carried = {net for module in found.values() for c in module for _, net in c.entries or ()}
    assert not (crossing | carried) & {"VDD", "GND", "FLASH_HOLD_N"}
    assert [[p.crossing.name for p in s.plan.ports] for s in project.modules] == [
        ["FLASH_WP", "SPI"],
        ["FLASH_WP", "RESET_N", "SPI"],
    ]
    assert [len(s.plan.harnesses) for s in project.sheets] == [2, 1, 1]
    for sheet in project.sheets:
        check_plan(sheet.plan)


def test_harness_entry_whose_net_does_not_cross_is_not_wired() -> None:
    """``partial.py``: the entry ``HOLD`` is in every block and wired in none."""
    model = hier_model(script=HIER_PARTIAL)
    found = crossings(model, form="binary")
    for module in ("flash", "mcu"):
        (spi,) = (c for c in found[module] if c.harness)
        assert spi.entries == (
            ("CS", "SPI_CS"),
            ("HOLD", None),
            ("MISO", "SPI_MISO"),
            ("MOSI", "SPI_MOSI"),
            ("SCK", "SPI_SCK"),
        )
    project = plan_sheets(model, name="altium_hier_partial", sheets="modules", form="binary")
    blocks = [block for sheet in project.sheets for block in sheet.plan.harnesses]
    assert len(blocks) == 4
    for block in blocks:
        assert [entry for entry, _ in block.entries] == ["CS", "HOLD", "MISO", "MOSI", "SCK"]
        assert [s.designator for s in block.stubs] == ["CS", "MISO", "MOSI", "SCK"]
        assert block.entry_point(2) not in {s.start for s in block.stubs}


def test_harness_that_crosses_no_module_gives_no_crossing() -> None:
    model = hier_model(append='\ndesign.add(Harness("LOCAL", {"HOLD": flash_hold_n}))\n')
    found = crossings(model, form="binary")
    assert [c.name for c in found["flash"]] == ["FLASH_WP", "SPI"]


def test_harness_crosses_only_the_modules_its_nets_cross() -> None:
    """``RESET_N`` runs between the top sheet and ``mcu``: the harness ``DBG`` crosses ``mcu`` only."""
    found = crossings(hier_model(append=DBG), form="binary")
    assert [c.name for c in found["mcu"]] == ["DBG", "FLASH_WP", "SPI"]
    assert [c.name for c in found["flash"]] == ["FLASH_WP", "SPI"]
    assert found["mcu"][0].entries == (("RST", "RESET_N"),)


def test_harness_net_listed_twice_travels_in_the_first_harness() -> None:
    """A net of two harnesses is refused by the build; the split still gives one owner, by type name."""
    model = hier_model(append='\ndesign.add(Harness("AUX", {"CLK": spi_sck}))\n')
    found = crossings(model, form="binary")
    aux, _wp, spi = found["flash"]
    assert aux.entries == (("CLK", "SPI_SCK"),) and dict(spi.entries or ())["SCK"] is None
