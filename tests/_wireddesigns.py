# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Designs authored for the wired schematic layout (change c0406, capability kicad-schematic, "Wired sheet
layout").

Each design is a small circuit drawn the way a schematic is usually read: an op-amp stage, a controller
with its reset, clock, indicator and connector, a linear supply, a transistor switch and a design of two
modules. Every part comes from the built-in catalog (``Fenolite:`` lib ids), so the builds need no library
table. Values, names and topologies are authored for these tests from textbook circuits; no file, value,
name or layout comes from any other project.
"""

from __future__ import annotations

from collections.abc import Callable

from _buildhelp import build

from fenolite.cli.cmd_build import _catalog_definitions  # pyright: ignore[reportPrivateUsage]
from fenolite.dsl import Design, Module, Net, Part, Power, connect, mm, to_model
from fenolite.lens.build import BuildOutput

R = ("Fenolite:Resistor", "Fenolite:Chip_0603")
C = ("Fenolite:Capacitor", "Fenolite:Chip_0603")


def _r(ref: str, value: str) -> Part:
    return Part(ref, R[0], footprint=R[1], value=value)


def _c(ref: str, value: str) -> Part:
    return Part(ref, C[0], footprint=C[1], value=value)


def _led(ref: str) -> Part:
    return Part(
        ref,
        "Fenolite:LED",
        footprint="Fenolite:LED0603_Kingbright_APT1608SURCK",
        value="LED",
        pad_map={"1": "2", "2": "1"},
    )


def _opamp(ref: str, value: str = "OPAMP") -> Part:
    return Part(
        ref,
        "Fenolite:Operational_Amplifier",
        footprint="Fenolite:SOT23_5",
        value=value,
        pad_map={"1": "1", "2": "3", "3": "4", "4": "5", "5": "2"},
    )


def _connector(ref: str, pins: int, value: str) -> Part:
    return Part(ref, f"Fenolite:Connector_{pins}", footprint=f"Fenolite:Header_1x{pins}_P2.54", value=value)


def _place(design: Design, parts: list[Part]) -> None:
    """Board positions on a grid of 8 mm: the schematic does not read them."""
    columns = 6
    for index, part in enumerate(parts):
        part.place(mm(6 + 8 * (index % columns)), mm(6 + 8 * (index // columns)))
    rows = -(-len(parts) // columns)
    design.board(mm(8 * columns + 6), mm(8 * rows + 6))


def opamp_stage() -> Design:
    """A non-inverting amplifier: an RC low-pass at the input, a feedback divider, a series output
    resistor, a decoupling capacitor at the supply pin, input and output connectors."""
    design = Design("opamp")
    j1 = _connector("J1", 2, "IN")
    j2 = _connector("J2", 2, "OUT")
    u1 = _opamp("U1")
    r1, c1 = _r("R1", "1k"), _c("C1", "100n")
    r2, r3 = _r("R2", "10k"), _r("R3", "1k")
    r4 = _r("R4", "100")
    c2 = _c("C2", "100n")
    parts = [j1, r1, c1, u1, r2, r3, r4, c2, j2]
    design.add(*parts)
    sig, flt, fb, out, buf = Net("SIG_IN"), Net("SIG_F"), Net("FB"), Net("AMP_OUT"), Net("OUT")
    vcc, gnd = Net("+5V"), Net("GND")
    connect(sig, j1[1], r1[1])
    connect(flt, r1[2], c1[1], u1[2])
    connect(fb, u1[3], r2[1], r3[1])
    connect(out, u1[1], r2[2], r4[1])
    connect(buf, r4[2], j2[1])
    connect(vcc, u1[4], c2[1])
    connect(gnd, u1[5], c1[2], r3[2], c2[2], j1[2], j2[2])
    design.add(Power(vcc, gnd))
    _place(design, parts)
    return design


def controller() -> Design:
    """A controller with a reset pull-up, capacitor and button, a crystal with load capacitors, an LED on
    an output, a divider into its ADC input, a serial connector and a decoupling capacitor."""
    design = Design("controller")
    u1 = Part(
        "U1",
        "Fenolite:Microcontroller",
        footprint="Fenolite:LQFP32_P0.8",
        value="MCU",
        pad_map={str(n): str(n) for n in range(1, 9)},
    )
    r1, c1 = _r("R1", "10k"), _c("C1", "100n")
    sw1 = Part(
        "SW1", "Fenolite:Pushbutton_NO", footprint="Fenolite:SW_Tact_Wurth_430181038816", value="RESET"
    )
    y1 = Part(
        "Y1",
        "Fenolite:Crystal",
        footprint="Fenolite:Crystal_3225_Abracon_ABM8",
        value="8MHz",
        pad_map={"1": "1", "2": "3"},
    )
    c3, c4 = _c("C3", "18p"), _c("C4", "18p")
    r2, d1 = _r("R2", "330"), _led("D1")
    r3, r4 = _r("R3", "47k"), _r("R4", "10k")
    j1 = _connector("J1", 3, "UART")
    c2 = _c("C2", "100n")
    parts = [u1, r1, c1, sw1, y1, c3, c4, r2, d1, r3, r4, j1, c2]
    design.add(*parts)
    vdd, gnd = Net("+3V3"), Net("GND")
    rst, clk, xo, led, led_a = Net("RESET"), Net("CLK"), Net("XOUT"), Net("LED"), Net("LED_A")
    sense, adc, uart = Net("VSENSE"), Net("ADC"), Net("TX")
    connect(vdd, u1[1], r1[1], c2[1])
    connect(gnd, u1[2], c1[2], sw1[3], sw1[4], c3[2], c4[2], d1["K"], r4[2], j1[3], c2[2])
    connect(rst, u1[3], r1[2], c1[1], sw1[1], sw1[2])
    connect(clk, u1[6], y1[1], c3[1])
    connect(xo, y1[2], c4[1])
    connect(led, u1[4], r2[1])
    connect(led_a, r2[2], d1["A"])
    connect(adc, u1[7], r3[2], r4[1])
    connect(sense, r3[1], j1[2])
    connect(uart, u1[8], j1[1])
    design.add(Power(vdd, gnd))
    u1.unused_no_connect()
    _place(design, parts)
    return design


def linear_supply() -> Design:
    """A 12 V input with a fuse, a reverse diode and an input capacitor, a 3.3 V linear regulator with an
    output capacitor, and an indicator LED on the output."""
    design = Design("supply")
    j1 = _connector("J1", 2, "12V")
    f1 = Part("F1", "Fenolite:Fuse", footprint="Fenolite:Chip_1206", value="500mA")
    d1 = Part("D1", "Fenolite:Diode", footprint="Fenolite:SOD123_Diodes", value="1N4148")
    c1 = Part(
        "C1",
        "Fenolite:Capacitor_Polarized",
        footprint="Fenolite:C_Electrolytic_Panasonic_FR_D5_P2",
        value="47u",
    )
    u1 = Part(
        "U1",
        "Fenolite:Linear_Regulator",
        footprint="Fenolite:SOT23_3",
        value="3V3",
        pad_map={"1": "3", "2": "1", "3": "2"},
    )
    c2 = _c("C2", "10u")
    r1, d2 = _r("R1", "1k"), _led("D2")
    parts = [j1, f1, d1, c1, u1, c2, r1, d2]
    design.add(*parts)
    raw, fused, vin, v33, gnd = Net("VIN_RAW"), Net("VIN_F"), Net("VIN"), Net("+3V3"), Net("GND")
    led = Net("PWR_LED")
    connect(raw, j1[1], f1[1])
    connect(fused, f1[2], d1["A"])
    connect(vin, d1["K"], c1[1], u1["IN"])
    connect(v33, u1["OUT"], c2[1], r1[1])
    connect(led, r1[2], d2["A"])
    connect(gnd, j1[2], c1[2], u1["GND"], c2[2], d2["K"])
    design.add(Power(vin, gnd), Power(v33, gnd))
    _place(design, parts)
    return design


def transistor_switch() -> Design:
    """A low-side NPN switch: base resistor and pull-down, a load connector on 12 V and a flyback diode."""
    design = Design("switch")
    j1 = _connector("J1", 2, "CTRL")
    r1, r2 = _r("R1", "1k"), _r("R2", "10k")
    q1 = Part(
        "Q1",
        "Fenolite:BJT_NPN",
        footprint="Fenolite:SOT23_3",
        value="NPN",
        pad_map={"1": "1", "2": "3", "3": "2"},
    )
    d1 = Part("D1", "Fenolite:Diode", footprint="Fenolite:SOD123_Diodes", value="1N4148")
    j2 = _connector("J2", 2, "LOAD")
    parts = [j1, r1, r2, q1, d1, j2]
    design.add(*parts)
    ctrl, base, load, v12, gnd = Net("CTRL"), Net("BASE"), Net("LOAD_N"), Net("+12V"), Net("GND")
    connect(ctrl, j1[1], r1[1])
    connect(base, r1[2], r2[1], q1[1])
    connect(load, q1[2], d1["A"], j2[2])
    connect(v12, d1["K"], j2[1])
    connect(gnd, q1[3], r2[2], j1[2])
    design.add(Power(v12, gnd))
    _place(design, parts)
    return design


def two_modules() -> Design:
    """A supply module and a sensor module: the module sheets share the rails and one signal."""
    design = Design("modules")
    psu, amp = Module("psu"), Module("amp")
    u1 = Part(
        "U1",
        "Fenolite:Linear_Regulator",
        footprint="Fenolite:SOT23_3",
        value="3V3",
        pad_map={"1": "3", "2": "1", "3": "2"},
    )
    c1, c2 = _c("C1", "10u"), _c("C2", "10u")
    psu.add(u1, c1, c2)
    u2 = _opamp("U2")
    r1, r2, r3 = _r("R1", "10k"), _r("R2", "10k"), _r("R3", "100k")
    c3 = _c("C3", "100n")
    amp.add(u2, r1, r2, r3, c3)
    j1 = _connector("J1", 3, "IO")
    design.add(j1, psu, amp)
    vin, v33, gnd, sense, mid, out = (
        Net("VIN"),
        Net("+3V3"),
        Net("GND"),
        Net("SENSE"),
        Net("MID"),
        Net("AMP_OUT"),
    )
    connect(vin, j1[1], u1["IN"], c1[1])
    connect(v33, u1["OUT"], c2[1], u2[4], c3[1], r1[1])
    connect(gnd, j1[3], u1["GND"], c1[2], c2[2], u2[5], c3[2], r2[2])
    connect(mid, r1[2], r2[1], u2[2])
    connect(sense, u2[3], r3[1], j1[2])
    connect(out, u2[1], r3[2])
    design.add(Power(vin, gnd), Power(v33, gnd))
    _place(design, [j1, u1, c1, c2, u2, r1, r2, r3, c3])
    return design


DESIGNS: dict[str, Callable[[], Design]] = {
    "opamp": opamp_stage,
    "controller": controller,
    "supply": linear_supply,
    "switch": transistor_switch,
    "modules": two_modules,
}
"""Every authored design by its name."""


def build_authored(design: Design, layout: str = "wired", target: int = 10) -> BuildOutput:
    """The build of an authored design with the catalog definitions it uses, as ``fenolite build`` passes
    them, drawn with ``layout``."""
    footprints, symbols, _ = _catalog_definitions(to_model(design), {}, {})
    return build(
        design,
        target,
        schematic_layout=layout,
        authored_footprints=footprints,
        authored_symbols=symbols,
    )
