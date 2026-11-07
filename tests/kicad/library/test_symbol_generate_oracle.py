# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generated symbol libraries against kicad-cli (change c0261, capability symbol-generation, "KiCad oracle
for generated symbols"; hypothesis ``H-K-SYM-UNITS-WRITE``).

The pin tables of ``examples/symbols/pins/`` are generated and written for the running major as one
library: a single-unit symbol with a stacked pad, a three-unit symbol with alternates and a named unit,
and one derived symbol of each. ``sym export svg`` must plot every unit of every symbol, and the library
that ``sym upgrade --force`` saves must read back with the same units, pins and ``extends``. Every run uses
an isolated configuration folder.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from _kicad import cli, major
from _libs import isolated_kicad_env, kicad

from fenolite.backends.kicad.sym import read_symbol_library, resolve_extends, write_symbol_library
from fenolite.catalog.generate.symbol import generate_symbol
from fenolite.catalog.pins import read_pins
from fenolite.model.library import SymbolDef, SymbolPin

pytestmark = pytest.mark.needs_kicad

TABLES = Path(__file__).resolve().parents[3] / "examples" / "symbols" / "pins"


def _library() -> tuple[SymbolDef, ...]:
    found: list[SymbolDef] = []
    for path in sorted(TABLES.glob("*.toml")):
        base, derived, _ = generate_symbol(read_pins(path), library="Example")
        found += [base, *derived]
    return tuple(found)


def _pin_key(pin: SymbolPin) -> tuple[object, ...]:
    alternates = tuple(sorted((a.name, a.etype, a.shape) for a in pin.alternates))
    return (pin.unit, pin.number, pin.name, pin.etype, pin.shape, pin.position, pin.rotation, pin.length,
            pin.hidden, alternates)  # fmt: skip


def test_multi_unit_library_exports(tmp_path: Path) -> None:
    symbols = _library()
    assert {s.unit_count for s in symbols if not s.extends} == {1, 3}
    library = tmp_path / "in" / "Example.kicad_sym"
    library.parent.mkdir()
    library.write_text(write_symbol_library(symbols, target=major()), encoding="utf-8")
    env = isolated_kicad_env(tmp_path)

    out = tmp_path / "svg"
    out.mkdir()
    result = kicad(cli(), env, "sym", "export", "svg", library, "-o", out)
    assert result.returncode == 0, result.stdout + result.stderr
    flat = {s.name: s for s in resolve_extends(symbols)}
    # 10.0 names every file <symbol>_unit<n>.svg; a name without the suffix is one plot of a symbol
    plotted = Counter(p.stem.rsplit("_unit", 1)[0] for p in out.glob("*.svg"))
    assert plotted == {name: s.unit_count for name, s in flat.items()}, sorted(plotted.items())

    upgraded = tmp_path / "up" / "Example.kicad_sym"
    upgraded.parent.mkdir()
    result = kicad(cli(), env, "sym", "upgrade", "--force", library, "-o", upgraded)
    assert result.returncode == 0, result.stdout + result.stderr
    back = {s.name: s for s in read_symbol_library(upgraded, library="Example")}
    assert set(back) == {s.name for s in symbols}
    for symbol in symbols:
        got = back[symbol.name]
        assert got.extends == symbol.extends, symbol.name
        assert [(u.unit, u.name) for u in got.units if u.unit] == [(u.unit, u.name) for u in symbol.units]
        assert sorted(map(_pin_key, got.pins)) == sorted(map(_pin_key, symbol.pins)), symbol.name
        if not symbol.extends:
            assert {(g.unit, g.points) for g in got.graphics} == {(g.unit, g.points) for g in symbol.graphics}
