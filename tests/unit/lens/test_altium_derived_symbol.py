# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A derived library symbol that the KiCad resolver returns is written flat to Altium.

``LibraryResolver.symbol`` gives a derived symbol its root's body (``resolve_extends``) and keeps the
``extends`` name. The Altium lens must not try to flatten it a second time without parents: that refused
every official KiCad 10.0.6 symbol defined by derivation (``altium.symbol-off-grid``, "cannot resolve the
symbol … it extends"). The library below is authored for this test."""

from __future__ import annotations

from fenolite.backends.kicad.sym import read_symbol_library, resolve_extends
from fenolite.core.errors import Issue
from fenolite.lens.altium import library_symbols, resolve_symbols
from fenolite.model import Design
from fenolite.model.library import SymbolDef

LIBRARY = """(kicad_symbol_lib (version 20241209) (generator "fenolite_test")
  (symbol "Base" (pin_names (offset 0.254)) (in_bom yes) (on_board yes)
    (property "Reference" "U" (at 0 5.08 0) (effects (font (size 1.27 1.27))))
    (property "Value" "Base" (at 0 -5.08 0) (effects (font (size 1.27 1.27))))
    (symbol "Base_0_1"
      (rectangle (start -2.54 2.54) (end 2.54 -2.54)
        (stroke (width 0.254) (type default)) (fill (type none))))
    (symbol "Base_1_1"
      (pin input line (at -5.08 0 0) (length 2.54) (name "IN" (effects (font (size 1.27 1.27))))
        (number "1" (effects (font (size 1.27 1.27)))))
      (pin output line (at 5.08 0 180) (length 2.54) (name "OUT" (effects (font (size 1.27 1.27))))
        (number "2" (effects (font (size 1.27 1.27)))))))
  (symbol "Child" (extends "Base")
    (property "Reference" "U" (at 0 5.08 0) (effects (font (size 1.27 1.27))))
    (property "Value" "Child" (at 0 -5.08 0) (effects (font (size 1.27 1.27))))))
"""


class _Resolver:
    """Returns what ``LibraryResolver.symbol`` returns: the flattened chain's first symbol."""

    def __init__(self) -> None:
        self.symbols = {s.name: s for s in read_symbol_library(LIBRARY, library="Authored")}

    def symbol(self, lib_id: str) -> SymbolDef:
        name = lib_id.partition(":")[2]
        chain = [self.symbols[name], *([self.symbols["Base"]] if name == "Child" else [])]
        return resolve_extends(chain)[0]


def test_resolved_derived_symbol_is_written_flat() -> None:
    resolver = _Resolver()
    assert resolver.symbol("Authored:Child").extends == "Base"  # the resolver keeps the name
    resolved = resolve_symbols(Design.new("derived"), resolver, extra=("Authored:Child",))  # type: ignore[arg-type]
    child = resolved["Authored:Child"]
    assert child.extends == ""
    assert [p.number for p in child.pins] == ["1", "2"]
    issues: list[Issue] = []
    written = library_symbols(resolved, issues)
    assert "Authored:Child" in written
    assert not [i for i in issues if i.code == "altium.symbol-off-grid"]
