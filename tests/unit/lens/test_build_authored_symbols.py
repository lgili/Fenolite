# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Custom symbols resolve from the DSL and are emitted as project-local build artifacts."""

from dataclasses import replace

from _buildhelp import blink, resolver

from fenolite.backends.kicad.sym import read_symbol_library
from fenolite.dsl import Symbol, mm
from fenolite.dsl.convert import placements, to_model
from fenolite.lens.build import build_design


def test_authored_symbol_resolves_and_is_written(tmp_path) -> None:
    d = blink()
    symbol = Symbol("LocalParts", "Resistor", reference="R", value="Resistor", footprint="Mini:Mini_R_0603")
    symbol.pin("1", "A", etype="passive", at=(mm(-2.54), mm(0)), length=mm(2.54), rotation=180)
    symbol.pin("2", "B", etype="passive", at=(mm(2.54), mm(0)), length=mm(2.54))
    d.add(symbol)
    model = to_model(d)
    components = tuple(
        replace(c, lib_symbol_ref=symbol.lib_id) if c.ref == "R1" else c for c in model.circuit.components
    )
    model = replace(model, circuit=replace(model.circuit, components=components))
    out = build_design(
        model,
        placements(d),
        name=d.name,
        copper=2,
        resolver=resolver(10),
        target=10,
        authored_symbols={symbol.lib_id: symbol.definition},
    )
    assert out.files["lib/LocalParts.kicad_sym"]
    table = out.files["sym-lib-table"].decode()
    assert "LocalParts" in table and "${KIPRJMOD}/lib/LocalParts.kicad_sym" in table
    assert out.summary["libraries"][symbol.lib_id] == "authored"  # type: ignore[index]
    parsed = read_symbol_library(out.files["lib/LocalParts.kicad_sym"].decode(), library="LocalParts")
    assert [p.number for p in parsed[0].pins] == ["1", "2"]
