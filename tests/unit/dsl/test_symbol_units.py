# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Multi-unit, derived and generated symbols in the DSL (change c0261, capability design-dsl, "Multi-unit
authored symbols", "Derived symbols in the DSL" and "Symbols from pin tables in the DSL")."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import blink, resolver
from _schbuild import sheet_of

from fenolite.backends.kicad.sym import read_symbol_library, write_symbol_library
from fenolite.catalog.generate.symbol import generate_symbol
from fenolite.catalog.pins import read_pins
from fenolite.dsl import Design, DslError, Symbol, mm, placements, to_model
from fenolite.lens.build import BuildOutput, build_design

PINS = Path(__file__).resolve().parents[2] / "data" / "pins"


def _dual() -> Symbol:
    q = Symbol("Example", "DUAL_OPAMP", reference="U")
    q.unit(1, "A")
    q.unit(2, "B")
    for unit, base in ((1, 0), (2, 4)):
        q.pin(
            str(base + 1),
            f"OUT{unit}",
            etype="output",
            at=(mm(7.62), mm(0)),
            length=mm(2.54),
            rotation=180,
            unit=unit,
        )
        q.pin(
            str(base + 2), f"IN{unit}-", etype="input", at=(mm(-7.62), mm(2.54)), length=mm(2.54), unit=unit
        )
        q.pin(
            str(base + 3), f"IN{unit}+", etype="input", at=(mm(-7.62), mm(-2.54)), length=mm(2.54), unit=unit
        )
    q.pin("8", "V+", etype="power_in", at=(mm(0), mm(7.62)), length=mm(2.54), rotation=270, unit=0)
    q.pin("4", "V-", etype="power_in", at=(mm(0), mm(-7.62)), length=mm(2.54), rotation=90, unit=0)
    q.rect((mm(-5.08), mm(-5.08)), (mm(5.08), mm(5.08)), unit=1)
    q.rect((mm(-5.08), mm(-5.08)), (mm(5.08), mm(5.08)), unit=2)
    return q


def test_dual_unit_with_common_supply() -> None:
    definition = _dual().definition
    assert [(u.unit, u.name) for u in definition.units] == [(1, "A"), (2, "B")]
    assert definition.unit_count == 2
    assert sorted(p.number for p in definition.pins_of(2)) == ["4", "5", "6", "7", "8"]
    assert [(g.unit, g.body_style) for g in definition.graphics] == [(1, 1), (2, 1)]
    back = read_symbol_library(write_symbol_library([definition]), library="Example")[0]
    key = lambda p: (p.unit, p.number)  # noqa: E731 - the writer groups the pins by unit
    assert (
        sorted(back.pins, key=key) == sorted(definition.pins, key=key)
        and back.graphics == definition.graphics
    )


def test_one_unit_definition_is_unchanged() -> None:
    plain = Symbol("Local", "R", reference="R")
    plain.pin("1", "A", at=(mm(-2.54), mm(0)), length=mm(1.27))
    plain.rect((mm(-1), mm(-1)), (mm(1), mm(1)))
    definition = plain.definition
    assert [(u.unit, u.body_style, u.name) for u in definition.units] == [(1, 1, "")]
    assert (definition.pins[0].unit, definition.pins[0].body_style) == (1, 1)
    assert (definition.graphics[0].unit, definition.graphics[0].body_style) == (0, 0)


def test_hidden_alternates_and_refusals() -> None:
    s = Symbol("Local", "IO", reference="U")
    with pytest.raises(DslError, match="power input"):
        s.pin("8", "VCC", etype="power_in", hidden=True, at=(mm(0), mm(0)), length=mm(2.54))
    s.pin("1", "PA0", etype="bidirectional", at=(mm(0), mm(0)), length=mm(2.54),
          alternates=(("TX", "output"), ("CLK", "input", "clock")))  # fmt: skip
    s.pin("2", "NC", etype="no_connect", hidden=True, at=(mm(0), mm(2.54)), length=mm(2.54))
    pins = s.definition.pins
    assert [p.number for p in pins] == ["1", "2"]  # the refused pin was not recorded
    assert [(a.name, a.etype, a.shape) for a in pins[0].alternates] == [
        ("TX", "output", "line"),
        ("CLK", "input", "clock"),
    ]
    assert pins[1].hidden
    for bad in (
        {"unit": -1},
        {"unit": True},
        {"hidden": "yes"},
        {"alternates": (("X",),)},
        {"alternates": (("X", "bogus"),)},
    ):
        with pytest.raises(DslError):
            s.pin("9", "X", at=(mm(0), mm(5)), length=mm(2.54), **bad)  # type: ignore[arg-type]
    with pytest.raises(DslError):
        s.unit(0)
    s.unit(1, "A")
    with pytest.raises(DslError, match="twice"):
        s.unit(1)
    gap = Symbol("Local", "Gap", reference="U")
    gap.pin("1", "A", at=(mm(0), mm(0)), length=mm(2.54), unit=3)
    with pytest.raises(DslError, match="without a gap"):
        _ = gap.definition


def _authored_build(*symbols: object, lib_id: str, by_name: bool = False) -> BuildOutput:
    if by_name:  # R1 connected by pin names of the generated regulator: BST and GND (pins 2 and 7)
        from _buildhelp import BLINK, blink_text

        scope: dict[str, object] = {"__name__": "design"}
        text = blink_text().replace("r1[1]", 'r1["BST"]').replace("r1[2]", 'r1["GND"]')
        text = text.replace(
            'footprint="Mini:Mini_R_0603", value="330"', 'footprint="Mini:Mini_QFP-32_7x7mm_P0.8mm"'
        )
        exec(compile(text, str(BLINK), "exec"), scope)  # noqa: S102 - our own example
        design = scope["design"]
        assert isinstance(design, Design)
    else:
        design = blink()
    design.add(*symbols)
    design.parts["R1"].lib_id = lib_id
    return build_design(
        to_model(design),
        placements(design),
        name=design.name,
        copper=2,
        resolver=resolver(10),
        authored_symbols={key: s.definition for key, s in design.symbols.items()},  # type: ignore[attr-defined]
    )


def _two_pin(name: str = "EXR") -> Symbol:
    base = Symbol("Example", name, reference="R", value=name, footprint="Mini:Mini_R_0603")
    base.pin("1", "A", etype="passive", at=(mm(-2.54), mm(0)), length=mm(1.27))
    base.pin("2", "B", etype="passive", at=(mm(2.54), mm(0)), length=mm(1.27), rotation=180)
    return base


def test_variant_built() -> None:
    base = _two_pin()
    dr = base.derive("EXRDR", value="EXRDR", description="tape and reel")
    assert dr.definition.extends == "EXR" and dr.definition.pins == () and dr.lib_id == "Example:EXRDR"
    assert dr.definition.properties == {"Value": "EXRDR", "Description": "tape and reel"}
    output = _authored_build(base, dr, lib_id="Example:EXRDR")
    library = output.files["lib/Example.kicad_sym"].decode("utf-8")
    assert '(symbol "EXRDR"\n\t\t(extends "EXR")' in library
    assert output.summary["libraries"]["Example:EXRDR"] == "authored"  # type: ignore[index]
    placed = [s for s in sheet_of(output).lib_symbols if s.name.startswith("EXRDR")]
    assert placed and {p.number for p in placed[0].pins} == {"1", "2"}  # the base's pins
    assert not [i for i in output.issues if i.severity == "error"], [i.message for i in output.issues]


def test_derived_needs_its_base_in_the_design() -> None:
    base = _two_pin()
    design = Design("d")
    with pytest.raises(DslError, match="add the base symbol"):
        design.add(base.derive("EXRDR"))
    design.add(base, base.derive("EXRDR"))
    with pytest.raises(DslError):
        base.derive("EXR")
    with pytest.raises(DslError):
        base.derive("bad name")


def test_generated_symbol_in_a_design() -> None:
    table = read_pins(PINS / "example_buck.toml")
    u = Symbol.from_pins(table, library="Example", footprint="Mini:Mini_R_0603")
    expected = generate_symbol(table, library="Example", footprint="Mini:Mini_R_0603")
    assert u.definition == expected[0]
    assert [v.definition for v in u.variants] == list(expected[1]) and u.generated and u.issues == ()
    for call in (
        lambda: u.pin("9", "X", at=(mm(0), mm(0)), length=mm(2.54)),
        lambda: u.unit(2),
        lambda: u.rect((mm(0), mm(0)), (mm(1), mm(1))),
    ):
        with pytest.raises(DslError, match="pin table"):
            call()
    with pytest.raises(DslError):
        Symbol.from_pins("pins/EXB6202.toml", library="Example")  # type: ignore[arg-type]
    output = _authored_build(u, *u.variants, lib_id="Example:EXB6202", by_name=True)
    assert not [i for i in output.issues if i.severity == "error"], [i.message for i in output.issues]
    assert not [i for i in output.issues if i.code == "build.unknown-pin"]
    library = output.files["lib/Example.kicad_sym"].decode("utf-8")
    assert library == write_symbol_library([u.definition, *(v.definition for v in u.variants)], target=10)
    assert output.summary["libraries"]["Example:EXB6202"] == "authored"  # type: ignore[index]
