# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placed library fields and multi-point lines against kicad-cli (change c0419, capability
symbol-generation, "Library symbol fields" and "Symbol lines keep every point").

A resistor with its Reference and Value placed beside the body, Footprint, Datasheet and Description hidden,
and a three-point line is written for the running major. ``sym export svg`` must plot it, and the library
that ``sym upgrade --force`` saves must hold each property at its place with its hide flag and the polyline
with its three points. Every run uses an isolated configuration folder.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _kicad import cli, major
from _libs import isolated_kicad_env, kicad

from fenolite.backends.kicad.sexpr import parse
from fenolite.backends.kicad.sym import write_symbol_library
from fenolite.core.coords import Point
from fenolite.model.library import SymbolDef, SymbolField, SymbolGraphic, SymbolPin

pytestmark = pytest.mark.needs_kicad

FIELDS = (
    SymbolField("Reference", Point(2_540_000, 1_270_000), justify="left"),
    SymbolField("Value", Point(2_540_000, -1_270_000), justify="left"),
    SymbolField("Footprint", Point(-1_778_000, 0), rotation=90_000_000, hidden=True),
    SymbolField("Datasheet", Point(0, 0), hidden=True),
    SymbolField("Description", Point(0, 0), hidden=True),
)
ZIGZAG = (Point(0, 2_540_000), Point(1_016_000, 1_270_000), Point(0, 0))


def _symbol() -> SymbolDef:
    return SymbolDef(
        id="sym-test",
        name="R",
        library="Fields",
        properties={"Reference": "R", "Value": "R", "Description": "Resistor"},
        pins=(
            SymbolPin("1", "~", "passive", Point(0, 3_810_000), rotation=270_000_000, length=1_270_000),
            SymbolPin("2", "~", "passive", Point(0, -3_810_000), rotation=90_000_000, length=1_270_000),
        ),
        graphics=(
            SymbolGraphic("rect", (Point(-1_016_000, -2_540_000), Point(1_016_000, 2_540_000))),
            SymbolGraphic("line", ZIGZAG),
        ),
        fields=FIELDS,
    )


def _mm(value: int) -> float:
    return value / 1_000_000


def test_placed_fields_and_lines_survive_kicad(tmp_path: Path) -> None:
    library = tmp_path / "in" / "Fields.kicad_sym"
    library.parent.mkdir()
    library.write_text(write_symbol_library([_symbol()], target=major()), encoding="utf-8")
    env = isolated_kicad_env(tmp_path)

    out = tmp_path / "svg"
    out.mkdir()
    result = kicad(cli(), env, "sym", "export", "svg", library, "-o", out)
    assert result.returncode == 0, result.stdout + result.stderr
    assert list(out.glob("*.svg"))

    upgraded = tmp_path / "up" / "Fields.kicad_sym"
    upgraded.parent.mkdir()
    result = kicad(cli(), env, "sym", "upgrade", "--force", library, "-o", upgraded)
    assert result.returncode == 0, result.stdout + result.stderr
    root = parse(upgraded.read_text(encoding="utf-8"))
    (symbol,) = root.nodes("symbol")
    saved = {}
    for prop in symbol.nodes("property"):
        name = prop.atoms()[0].value
        at = [float(a.value) for a in prop.find("at").atoms()]  # type: ignore[union-attr]
        effects = prop.find("effects")
        assert effects is not None
        # KiCad 10 saves the flag as a child of the property, older files keep it in the effects
        hide = prop.find("hide") or effects.find("hide")
        justify = effects.find("justify")
        saved[name] = (
            at,
            hide is not None and [a.value for a in hide.atoms()] in ([], ["yes"]),
            [a.value for a in justify.atoms()] if justify is not None else [],
        )
    for field in FIELDS:
        at, hidden, justify = saved[field.name]
        assert at == [_mm(field.at.x), _mm(field.at.y), field.rotation // 1_000_000], field.name
        assert hidden == field.hidden, field.name
        assert justify == ([field.justify] if field.justify else []), field.name
    lines = [
        [(float(xy.atoms()[0].value), float(xy.atoms()[1].value)) for xy in poly.find("pts").nodes("xy")]  # type: ignore[union-attr]
        for unit in symbol.nodes("symbol")
        for poly in unit.nodes("polyline")
    ]
    assert [(_mm(p.x), _mm(p.y)) for p in ZIGZAG] in lines
