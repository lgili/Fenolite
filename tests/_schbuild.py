# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Designs and helpers of the generated-schematic tests (changes c0061 and c0070): the blink without its
no-connect marks, an authored design with a three-unit part, a pin-pad map and a net with a slash, an
authored design with two modules of which one holds a third, and the built files written to a folder for
the oracle tests."""

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
NESTED = "nested"
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


def nested_design(marks: bool = True) -> Design:
    """``U1`` at the top, the module ``power`` with ``R1`` and the module ``ldo`` inside it with ``C1``, and
    the module ``io`` with ``R2`` (kicad-schematic, "Two modules, one nested"). ``C1`` is drawn with the
    resistor symbol: the mini library has no capacitor. The unused pins of ``U1`` are marked unless
    ``marks`` is false."""
    design = Design(NESTED)
    design.board(mm(60), mm(40))
    u1 = Part("U1", "Mini:Mini_QFP32_IC", value="MCU")
    r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="10k")
    c1 = Part("C1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="100n")
    r2 = Part("R2", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330")
    power, ldo, io = Module("power"), Module("ldo"), Module("io")
    power.add(r1)
    ldo.add(c1)
    power.add(ldo)
    io.add(r2)
    design.add(u1, power, io)
    vin, gnd, drv = Net("VIN"), Net("GND"), Net("DRV")
    feedback = Net("power/FB")
    connect(vin, u1[9], r1[1])
    connect(gnd, u1[10], c1[2], r2[2])
    connect(feedback, r1[2], c1[1], u1[2])
    connect(drv, u1[1], r2[1])
    if marks:
        no_connect(*(u1[pin] for pin in range(1, 33) if pin not in (1, 2, 9, 10)))
    design.add(Power(vin, gnd))
    u1.place(mm(30), mm(25))
    r1.place(mm(10), mm(8))
    c1.place(mm(18), mm(8))
    r2.place(mm(45), mm(8))
    return design


def snap_design(*, second: bool = False, adjacent: bool = False) -> Design:
    """``U1`` and ``R1``, whose pin 1 is on the net ``SIG`` of pin 1 of ``U1`` and whose pin 2 is on
    ``GND`` (kicad-schematic, "Resistor on an IC pin"); the pins beside pin 1 of ``U1`` are on no net.
    ``second`` adds ``R2`` on ``SIG`` and ``VIN``; ``adjacent`` adds ``R2`` on the next pin of ``U1``."""
    design = Design("snap")
    design.board(mm(60), mm(40))
    u1 = Part("U1", "Mini:Mini_QFP32_IC", value="MCU")
    r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k")
    design.add(u1, r1)
    sig, gnd, vin = Net("SIG"), Net("GND"), Net("VIN")
    connect(sig, u1[1], r1[1])
    connect(gnd, u1[10], r1[2])
    connect(vin, u1[9])
    u1.place(mm(30), mm(25))
    r1.place(mm(10), mm(8))
    if second or adjacent:
        r2 = Part("R2", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k")
        design.add(r2)
        r2.place(mm(18), mm(8))
        if second:
            connect(sig, r2[1])
            connect(vin, r2[2])
        else:
            connect(Net("SIG2"), u1[2], r2[1])
            connect(gnd, r2[2])
    design.add(Power(vin, gnd))
    return design


STACKED = "stacked"
QFP = "Mini:Mini_QFP-32_7x7mm_P0.8mm"


def stacked_design(first_pad_only: bool = False) -> Design:
    """Pins bonded to several pads (change c0123), from the mini library alone: ``U1`` has an output pin
    and two power inputs with two pads each on nets, and a marked, unnamed pin with three pads whose
    numbers sort before and after its own; ``R1`` has two pads per pin on nets; ``D2`` has its named pin
    ``K`` with two pads on no net and without a mark (the first pad is not the lowest); ``D1`` holds a map
    of one pad per pin. With ``first_pad_only`` every pin has the first of its pads alone, which is what
    the electrical rules check of the stacked design is compared with."""

    def pads(*numbers: str) -> str | tuple[str, ...]:
        return numbers[0] if first_pad_only or len(numbers) == 1 else numbers

    design = Design(STACKED)
    design.board(mm(70), mm(40))
    gate = Part(
        "U1",
        "Mini:Mini_DualGate",
        footprint=QFP,
        value="GATE",
        pad_map={
            "3": pads("3", "23"),
            "5": pads("5", "15", "9"),
            "7": pads("7", "27"),
            "14": pads("14", "24"),
        },
    )
    led = Part("D2", "Mini:Mini_LED", footprint=QFP, value="LED", pad_map={"1": pads("21", "17"), "2": "2"})
    r1 = Part(
        "R1", "Mini:Mini_R", footprint=QFP, value="330", pad_map={"1": pads("1", "2"), "2": pads("3", "4")}
    )
    d1 = Part(
        "D1", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm", value="LED", pad_map={"1": "2", "2": "1"}
    )
    design.add(gate, led, r1, d1)
    vcc, gnd, out, led_a = Net("VCC"), Net("GND"), Net("OUT"), Net("LED_A")
    connect(vcc, gate[14])
    connect(gnd, gate[7], d1[1])
    connect(out, gate[3], r1[1])
    connect(led_a, r1[2], led[2], d1[2])
    no_connect(gate[1], gate[2], gate[4], gate[5], gate[6])
    design.add(Power(vcc, gnd))
    gate.place(mm(12), mm(14))
    led.place(mm(30), mm(14))
    r1.place(mm(48), mm(14))
    d1.place(mm(62), mm(30))
    return design


def built_stacked(target: int = 10, *, first_pad_only: bool = False, **kwargs: object) -> BuildOutput:
    return build(stacked_design(first_pad_only), target, **kwargs)


def root_name(output: BuildOutput) -> str:
    """The root schematic file of a build: the one beside the board, not under ``sheets/``."""
    return next(path for path in output.files if path.endswith(".kicad_sch") and "/" not in path)


def sheet_of(output: BuildOutput) -> SchematicSheet:
    """The root sheet read back from the schematic a build wrote."""
    name = root_name(output)
    return sch.read_schematic(output.files[name].decode("utf-8"), file=name)


def children_of(output: BuildOutput) -> dict[str, SchematicSheet]:
    """The child sheets read back from the files a build wrote, by their path from the root's folder."""
    return {
        path: sch.read_schematic(data.decode("utf-8"), file=path)
        for path, data in output.files.items()
        if path.endswith(".kicad_sch") and "/" in path and not path.startswith(".fenolite/")
    }


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


def built_nested(target: int = 10, **kwargs: object) -> BuildOutput:
    return build(nested_design(), target, **kwargs)


__all__ = [
    "NESTED",
    "QFP",
    "STACKED",
    "SLASH_NET",
    "UNITS",
    "blink_slash",
    "blink_unmarked",
    "built_nested",
    "built_stacked",
    "built_units",
    "children_of",
    "design_of",
    "global_build",
    "nested_design",
    "root_name",
    "sheet_of",
    "snap_design",
    "stacked_design",
    "units_design",
    "write_files",
]
