# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Designs and helpers of the generated-schematic tests (change c0061): the blink without its no-connect
marks, an authored design with a three-unit part, a pin-pad map and a net with a slash, and the built
files written to a folder for the oracle tests."""

from __future__ import annotations

import shutil
from pathlib import Path

from _buildhelp import BLINK, LIBS, blink, build

from fenolite.backends.kicad import sch
from fenolite.backends.kicad.libs import LibRow, LibTable, write_lib_table
from fenolite.dsl import Design, Module, Net, Part, Power, connect, mm, no_connect
from fenolite.lens.build import BuildOutput
from fenolite.model.schematic import SchematicSheet

UNITS = "units"
SLASH_NET = "mod/LED_A"


def design_of(text: str) -> Design:
    """The design a variant of the blink script binds."""
    scope: dict[str, object] = {"__name__": "design"}
    exec(compile(text, str(BLINK), "exec"), scope)  # noqa: S102 - the repository's own example
    design = scope["design"]
    assert isinstance(design, Design)
    return design


def blink_unmarked() -> Design:
    """The blink without its no-connect marks: 29 pins on no net and no flag."""
    return blink(marks=False)


def blink_slash() -> Design:
    """The blink with its net ``LED_A`` named ``mod/LED_A``."""
    text = BLINK.read_text(encoding="utf-8")
    assert 'Net("LED_A")' in text
    return design_of(text.replace('Net("LED_A")', f'Net("{SLASH_NET}")'))


def units_design() -> Design:
    """One ``Mini_DualGate`` (two gates and a power unit) with marks, an LED whose pins are mapped to the
    other pads, and a net of the module ``mod`` whose name holds a slash."""
    design = Design(UNITS)
    design.board(mm(60), mm(40))
    gate = Part("U2", "Mini:Mini_DualGate", footprint="Mini:Mini_QFP-32_7x7mm_P0.8mm", value="GATE")
    led = Part(
        "D1", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm", value="LED", pad_map={"1": "2", "2": "1"}
    )
    r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330")
    module = Module("mod")
    module.add(led, r1)
    design.add(gate, module)
    vcc, gnd, out, led_a = Net("VCC"), Net("GND"), Net("OUT"), Net(SLASH_NET)
    connect(vcc, gate[14])
    connect(gnd, gate[7], led[1])
    connect(out, gate[3], r1[1])
    connect(led_a, r1[2], led[2])
    no_connect(gate[1], gate[2], gate[4], gate[5], gate[6])
    design.add(Power(vcc, gnd))
    gate.place(mm(20), mm(20))
    r1.place(mm(40), mm(12))
    led.place(mm(46), mm(26))
    return design


def sheet_of(output: BuildOutput) -> SchematicSheet:
    """The sheet read back from the schematic a build wrote."""
    name = next(path for path in output.files if path.endswith(".kicad_sch"))
    return sch.read_schematic(output.files[name].decode("utf-8"), file=name)


def write_files(output: BuildOutput, folder: Path) -> Path:
    """Every file of ``output`` under ``folder`` (LF line ends, as built)."""
    for rel, data in output.files.items():
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return folder


def global_build(tmp_path: Path, target: int = 10, **kwargs: object) -> BuildOutput:
    """The blink built from a folder without project tables: every symbol and footprint is served by the
    global tables of a configuration folder made under ``tmp_path``, whose rows ``Mini`` name copies of
    the CC0 ``Mini_v9`` library (the setup of design-dsl, "Global footprints vendored")."""
    pretty, symbols = tmp_path / "global" / "Mini.pretty", tmp_path / "global" / "Mini.kicad_sym"
    shutil.copytree(LIBS / "Mini_v9.pretty", pretty)
    shutil.copyfile(LIBS / "Mini_v9.kicad_sym", symbols)
    for major in (9, 10):
        sub = tmp_path / "config" / f"{major}.0"
        sub.mkdir(parents=True)
        tables = (
            ("fp-lib-table", LibTable("footprint", (LibRow("Mini", "KiCad", pretty.as_posix()),))),
            ("sym-lib-table", LibTable("symbol", (LibRow("Mini", "KiCad", symbols.as_posix()),))),
        )
        for name, table in tables:
            (sub / name).write_text(write_lib_table(table, target=major), encoding="utf-8")
    empty = tmp_path / "project"
    empty.mkdir()
    return build(blink(), target, project_dir=empty, config_home=tmp_path / "config", **kwargs)


def built_units(target: int = 10, **kwargs: object) -> BuildOutput:
    return build(units_design(), target, **kwargs)


__all__ = [
    "SLASH_NET",
    "UNITS",
    "blink_slash",
    "blink_unmarked",
    "design_of",
    "built_units",
    "global_build",
    "sheet_of",
    "units_design",
    "write_files",
]
