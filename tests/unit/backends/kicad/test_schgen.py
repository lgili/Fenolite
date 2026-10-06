# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The generated sheet of a built design (capability kicad-schematic, "Generated sheet content", "Names of
unconnected-pin nets" and "Generated schematic issue codes"; change c0061)."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from _buildhelp import HEADER_SYM, blink, build, footprint_file, project
from _schbuild import SLASH_NET, blink_unmarked, built_units

from fenolite.backends.kicad import sch, schgen, schlayout, symembed
from fenolite.backends.kicad.pcb import kicad_uuid
from fenolite.backends.kicad.schgen import GeneratedSchematic
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, Net, Part, Power, connect, mm
from fenolite.lens import schplacements
from fenolite.lens.build import BuildOutput

ROOT = Path(__file__).resolve().parents[4]
FONT = "(effects (font (size 1.27 1.27)))"


def generated(output: BuildOutput) -> GeneratedSchematic:
    assert output.schematic is not None, [i.message for i in output.issues if i.severity == "error"]
    return output.schematic


def pin_points(output: BuildOutput, ref: str) -> dict[str, object]:
    """Pin number → connection point of the placed symbol(s) of ``ref``."""
    made = generated(output)
    found: dict[str, object] = {}
    for sheet in (made.sheet, *made.children.values()):
        definitions = {f"{d.library}:{d.name}": d for d in sheet.lib_symbols}
        for symbol in sheet.symbols:
            if symbol.ref != ref:
                continue
            for pin in definitions[symbol.lib_ref].pins_of(symbol.unit, 1):
                found[pin.number] = schlayout.pin_point(
                    symbol.position, pin.position, symbol.rotation // 1_000_000, symbol.mirror
                )
    return found


def test_blink() -> None:
    output = build(blink())
    made = generated(output)
    sheet = made.sheet
    assert [s.ref for s in sheet.symbols] == ["D1", "R1", "U1", "#FLG01", "#FLG02"]
    # R1 lies beside pin 1 of U1, joined to it by a wire: that pair has one LED_DRV label (c0070)
    assert Counter(label.name for label in sheet.labels) == {"GND": 3, "VIN": 2, "LED_DRV": 1, "LED_A": 2}
    assert len(sheet.wires) == 1 and made.satellites == 1 and made.children == {}
    assert {(label.kind, label.shape) for label in sheet.labels} == {("global", "passive")}
    points = pin_points(output, "U1")
    marked = sorted(set(points) - {"1", "9", "10"}, key=int)
    assert len(sheet.no_connects) == 29
    assert {flag.position for flag in sheet.no_connects} == {points[n] for n in marked}
    assert len(made.pad_nets) == 29 and {cid for cid, _ in made.pad_nets} == {
        c.id for c in output.design.circuit.components if c.ref == "U1"
    }
    names = set(made.pad_nets.values())
    assert {"unconnected-(U1-PA1-Pad2)", "unconnected-(U1-NRST-Pad11)"} <= names
    assert (sheet.paper.paper, sheet.pages[0].path, sheet.pages[0].page) == ("A4", "/", "1")
    assert not sheet.sheets and made.power_flags == 2
    assert sheet.title_block == output.design.board.title_block  # type: ignore[union-attr]


def test_labels_sit_on_the_pins_of_their_nets() -> None:
    output = build(blink())
    sheet = generated(output).sheet
    at = {(label.name, label.position) for label in sheet.labels}
    u1, r1, d1 = (pin_points(output, ref) for ref in ("U1", "R1", "D1"))
    assert {("VIN", u1["9"]), ("GND", u1["10"])} <= at
    assert {("LED_DRV", r1["1"]), ("LED_A", r1["2"]), ("GND", d1["1"]), ("LED_A", d1["2"])} <= at
    (wire,) = sheet.wires
    assert (wire.start, wire.end) == (u1["1"], r1["1"]) and ("LED_DRV", u1["1"]) not in at
    flags = {s.value: s for s in sheet.symbols if s.ref.startswith("#FLG")}
    assert set(flags) == {"PWR_FLAG"} and {s.lib_ref for s in sheet.symbols if s.ref.startswith("#")} == {
        "fenolite:PWR_FLAG"
    }
    flag_points = {s.position for s in sheet.symbols if s.ref.startswith("#FLG")}
    assert {(name, p) for name, p in at if p in flag_points} == {
        ("GND", sorted(flag_points, key=lambda p: p.x)[0]),
        ("VIN", sorted(flag_points, key=lambda p: p.x)[1]),
    }
    for symbol in sheet.symbols:
        if symbol.ref.startswith("#FLG"):
            assert not symbol.in_bom and not symbol.on_board


def test_a_pin_without_a_mark_gets_neither_label_nor_flag() -> None:
    marked, plain = generated(build(blink())), generated(build(blink_unmarked()))
    assert not plain.sheet.no_connects and len(plain.sheet.labels) == len(marked.sheet.labels)
    assert dict(plain.pad_nets) == dict(marked.pad_nets)


def test_every_unit_is_placed() -> None:
    made = generated(built_units())
    gates = [(s.ref, s.unit) for s in made.sheet.symbols if s.ref == "U2"]
    assert gates == [("U2", 1), ("U2", 2), ("U2", 3)]
    root = f"/{kicad_uuid(made.sheet)}"
    for symbol in made.sheet.symbols:
        assert symbol.uses == (sch.SymbolUse("units", root, symbol.ref, symbol.unit),)  # type: ignore[attr-defined]
        assert symbol.body_style == 1
    assert sorted(made.pad_nets.values()) == [f"unconnected-(U2-Pad{n})" for n in (1, 2, 4, 5, 6)]
    assert len(made.sheet.no_connects) == 5


def test_pin_pad_map_and_slash_net() -> None:
    output = built_units()
    made = generated(output)
    (mod,) = made.children.values()  # D1 and R1 are parts of the module ``mod``, which has its own sheet
    led = next(s for s in mod.symbols if s.ref == "D1")
    assert led.lib_ref == f"Mini:{symembed.variant_name('Mini_LED', (('1', '2'), ('2', '1')))}"
    definition = next(d for d in mod.lib_symbols if f"{d.library}:{d.name}" == led.lib_ref)
    assert {p.name: p.number for p in definition.pins} == {"K": "2", "A": "1"}
    names = {label.name for label in mod.labels}
    assert "mod{slash}LED_A" in names and SLASH_NET not in names
    assert [n.name for n in output.design.circuit.nets if "LED_A" in n.name] == [SLASH_NET]
    # the labels of D1 sit on the pins that carry the mapped numbers
    points = pin_points(output, "D1")
    at = {(label.name, label.position) for label in mod.labels}
    assert ("GND", points["2"]) in at and ("mod{slash}LED_A", points["1"]) in at


def test_symbol_paths_and_ids() -> None:
    output = build(blink())
    made = generated(output)
    by_ref = {s.ref: s for s in made.sheet.symbols}
    components = {c.ref: c for c in output.design.circuit.components}
    assert made.sheet.id == derived_id("sch", "fenolite", "blink")
    assert by_ref["R1"].id == derived_id("sci", "fenolite", "blink:R1#1")
    assert by_ref["#FLG01"].id == derived_id("sci", "fenolite", "blink:flag:GND")
    assert made.paths[components["R1"].id] == f"/{kicad_uuid(by_ref['R1'])}"
    assert {label.id for label in made.sheet.labels} >= {
        derived_id("lbl", "fenolite", "blink:label:R1:1"),
        derived_id("lbl", "fenolite", "blink:label:flag:VIN"),
    }
    assert derived_id("ncf", "fenolite", "blink:nc:U1:2") in {f.id for f in made.sheet.no_connects}


def test_symbol_fields_equal_footprint_fields() -> None:
    design = blink()
    design.parts["R1"].properties = {"MPN": "RC0603-330"}  # type: ignore[misc]
    output = build(design)
    made = generated(output)
    r1 = next(s for s in made.sheet.symbols if s.ref == "R1")
    component = next(c for c in output.design.circuit.components if c.ref == "R1")
    assert r1.properties["MPN"] == "RC0603-330" and r1.properties["fenolite.path"] == "R1"
    assert {k: v for k, v in r1.properties.items() if k in component.properties} == component.properties
    assert r1.properties["Footprint"] == "Mini:Mini_R_0603" == r1.footprint


def test_deterministic() -> None:
    first, second = build(blink()), build(blink())
    assert generated(first) == generated(second)
    text = first.files["blink.kicad_sch"].decode("utf-8")
    assert text == second.files["blink.kicad_sch"].decode("utf-8")
    assert "(date" not in text and str(ROOT) not in text and str(ROOT.as_posix()) not in text


def power_out_project(folder: Path) -> Path:
    pins = (
        f'(pin power_out line (at 0 0 0) (length 2.54) (name "OUT" {FONT}) (number "1" {FONT}))'
        f'(pin power_in line (at 0 -2.54 0) (length 2.54) (name "IN" {FONT}) (number "2" {FONT}))'
        f'(pin passive line (at 0 -5.08 0) (length 2.54) (name "A(1)" {FONT}) (number "3" {FONT}))'
    )
    fields = "".join(
        f'(property "{k}" "{v}" (at 0 0 0) {FONT})' for k, v in (("Reference", "U"), ("Value", "Reg"))
    )
    lib = f'{HEADER_SYM}\t(symbol "Reg" (in_bom yes) (on_board yes) {fields} (symbol "Reg_1_1" {pins}))\n)\n'
    (folder / "T.pretty").mkdir(parents=True)
    (folder / "T.pretty" / "Three.kicad_mod").write_text(footprint_file("Three", ["1", "2", "3"]), "utf-8")
    (folder / "T.kicad_sym").write_text(lib, encoding="utf-8")
    return project(folder, {"T": "${KIPRJMOD}/T.pretty"}, {"T": "${KIPRJMOD}/T.kicad_sym"})


def regulator(dnp: bool = False) -> Design:
    design = Design("reg")
    design.board(mm(20), mm(20))
    first = Part("U1", "T:Reg", footprint="T:Three")
    second = Part("U2", "T:Reg", footprint="T:Three")
    design.add(first, second)
    vout, vin, gnd = Net("VOUT"), Net("VIN"), Net("GND")
    connect(vout, first[1], second[2])
    connect(vin, first[2])
    connect(gnd, second[1])
    design.add(Power(vout, gnd, name="out"), Power(vin, gnd, name="in"))
    return design


def test_a_power_output_needs_no_flag(tmp_path: Path) -> None:
    made = generated(build(regulator(), project_dir=power_out_project(tmp_path)))
    flags = {s.position for s in made.sheet.symbols if s.ref.startswith("#FLG")}
    assert {label.name for label in made.sheet.labels if label.position in flags} == {"VIN"}
    assert made.power_flags == 1


def test_an_unproved_character_keeps_the_pad_on_no_net(tmp_path: Path) -> None:
    output = build(regulator(), project_dir=power_out_project(tmp_path))
    made = generated(output)
    assert not [name for name in made.pad_nets.values() if "A(1)" in name]
    found = [i for i in output.issues if i.code == "kicad.sch.unconnected-name-unproven"]
    assert [(i.severity, i.where) for i in found] == [("warning", "U1"), ("warning", "U2")]
    assert sorted(made.pad_nets.values()) == []


def test_reserved_library(tmp_path: Path) -> None:
    folder = power_out_project(tmp_path)
    project(folder, {"T": "${KIPRJMOD}/T.pretty"}, {"fenolite": "${KIPRJMOD}/T.kicad_sym"})
    design = Design("reserved")
    design.board(mm(20), mm(20))
    design.add(Part("U1", "fenolite:Reg", footprint="T:Three"))
    output = build(design, project_dir=folder)
    assert output.files == {} and output.schematic is None
    assert [(i.code, i.severity) for i in output.issues if i.code.startswith("build.reserved")] == [
        ("build.reserved-library", "error")
    ]


def test_codes_are_a_closed_set() -> None:
    assert dict(schgen.ISSUE_CODES) == {
        "kicad.sch.pin-off-grid": "info",
        "kicad.sch.power-pin-shown": "info",
        "kicad.sch.unconnected-name-unproven": "warning",
        "build.schematic-too-large": "error",
        "build.symbol-overlap": "warning",
        "build.symbol-short": "error",
        "build.symbol-placement-unknown": "warning",
        "build.symbol-placement-invalid": "error",
        "build.reserved-library": "error",
        "build.schematic-replaced": "warning",
        "build.sheet-file-collision": "error",
        "build.sheet-stale": "warning",
    }
    assert dict(sch.WRITE_ISSUE_CODES) == {"kicad.sch.dropped-too-new": "warning"}
    known = set(schgen.ISSUE_CODES) | set(sch.WRITE_ISSUE_CODES)
    pattern = re.compile(r'"((?:kicad\.sch|build)\.[a-z0-9.-]+)"')
    for module in (schgen, schlayout, symembed, schplacements):
        literals = set(pattern.findall(Path(module.__file__).read_text(encoding="utf-8")))
        assert literals <= known, (module.__name__, literals - known)
    severities = {"build.symbol-short": "error", "kicad.sch.pin-off-grid": "info"}
    source = Path(schlayout.__file__).read_text(encoding="utf-8")
    for code, severity in severities.items():
        assert re.search(rf'"{re.escape(code)}",\s+"{severity}"', source), code


def test_codes_are_documented() -> None:
    contract = (ROOT / "docs" / "cli-contract.md").read_text(encoding="utf-8")
    for code in (*schgen.ISSUE_CODES, *sch.WRITE_ISSUE_CODES):
        assert f"`{code}`" in contract, code
